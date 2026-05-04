#!/usr/bin/env python3
"""SRP Phase 1 Simulator — Streamlit entry point.

Run:
    pip install -r requirements.txt
    streamlit run app.py

Pulls hotels from the live Elastic index, applies the Phase 1 scoring
formula (Bayesian adjusted_rating × star-affinity^λ_s × distance-decay^λ_d),
and renders an SRP. All scoring knobs live in the sidebar and re-rank
instantly without re-querying Elastic.

Architecture
------------
- ``srp_simulator.config``       — env vars, factory defaults, presets
- ``srp_simulator.elastic``      — ES query builders + helpers
- ``srp_simulator.scoring``      — pure scoring (testable, no Streamlit)
- ``srp_simulator.persistence``  — load / save user-tuned defaults to JSON
- ``srp_simulator.theme``        — light + dark CSS strings
- ``app.py`` (this file)         — UI orchestration only
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
from typing import Any

import pandas as pd
import streamlit as st

from srp_simulator.config import (
    DEFAULT_GEO_KM,
    DEFAULTS_FILE,
    FACTORY_AFFINITIES,
    FACTORY_DEFAULTS,
    FLAT_CONTEXTS,
    LANDMARKS,
    SEARCH_CONTEXTS,
    is_flat_context,
)
from srp_simulator.elastic import (
    build_candidate_query,
    es_search,
    fetch_areas_for_city,
    fetch_hotel_by_code,
    fetch_location_geometry,
    fetch_places,
    hits_to_rows,
    hotel_lookup,
    source_to_row,
)
from srp_simulator.persistence import (
    coerce_affinity as _coerce_affinity,
    load_active_defaults,
    save_active_defaults,
)
from srp_simulator.scoring import (
    active_context,
    apply_sort,
    score_row,
)
from srp_simulator.auth import require_auth
from srp_simulator.theme import inject_theme

# UI helper: coerce a legacy single matrix (Hotel shape) from JSON.
def _coerce_matrix(raw):
    return _coerce_affinity("Hotel", raw)

ACTIVE_DEFAULTS = load_active_defaults()

# Feature flags — flip to True to re-enable.
SHOW_COMPETITOR_SECTION = False


# ─────────────────────────── UI ────────────────────────────────

st.set_page_config(
    page_title="Mirador",
    page_icon="⌖",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme(dark=st.session_state.get("theme_toggle", False))
require_auth(allowed_domain="onarrival.travel")

st.markdown(
    """
    <div class="app-header">
      <div class="brand">
        <svg class="brand-icon" viewBox="0 0 32 32" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
          <path d="M6 24 L11 10 L16 18 L21 10 L26 24"/>
        </svg>
        <div>
          <div class="app-title">Mirador</div>
          <div class="app-sub">SRP Phase 1 Simulator · adj_rating × affinity^λ_s × decay(d)^λ_d</div>
        </div>
      </div>
      <div class="app-meta">elastic · phase 1</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar: Inputs + Config ──────────────────────────────────
with st.sidebar:
    tcol, _ = st.columns([1, 1])
    tcol.toggle("Dark mode", key="theme_toggle")

    st.markdown("## Search Input")
    search_type = st.radio(
        "Search type", ["Hotel", "Location", "Landmark"],
        horizontal=True, label_visibility="collapsed",
    )

    params: dict[str, Any] = {}

    # ─── Hotel mode: search → autocomplete-style picker ───────
    if search_type == "Hotel":
        st.caption("Search by hotel name or hotelCode — pick the anchor. It will appear as #1 in Recommended.")
        with st.form("hotel_search_form", clear_on_submit=False, border=False):
            q = st.text_input(
                "Hotel name or ID",
                placeholder="e.g. Taj Mahal Palace or 123456",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Search hotels", use_container_width=True)
        if submitted and q.strip():
            try:
                with st.spinner("Looking up…"):
                    matches = hotel_lookup(q.strip(), size=15)
                st.session_state["hotel_options"] = matches
                if not matches:
                    st.warning("No hotels matched.")
            except Exception as e:
                st.error(f"Lookup failed: {e}")

        opts = st.session_state.get("hotel_options", [])
        if opts:
            def _fmt(o: dict) -> str:
                city = o.get("cityName") or ""
                state = o.get("stateName") or ""
                code = o.get("hotelCode") or ""
                hr = o.get("hotelRating")
                star = f"{int(hr)}★ · " if hr is not None else ""
                return f'{o.get("hotelName")} · {star}{city}, {state} ({code})'

            picked = st.selectbox(
                "Anchor hotel",
                options=opts,
                format_func=_fmt,
                key="hotel_pick",
            )
            if picked:
                loc = picked.get("location") or {}
                params["anchor"] = {
                    "lat": loc.get("lat"), "lon": loc.get("lon"),
                    "cityName": picked.get("cityName"),
                    "hotelName": picked.get("hotelName"),
                }
                params["anchor_hotelCode"] = picked.get("hotelCode")
                # Auto-match user's selected ★ to the picked hotel's star rating,
                # but only on hotel-change (so a manual override still sticks).
                new_code = picked.get("hotelCode")
                if st.session_state.get("last_picked_hotelCode") != new_code:
                    hr = picked.get("hotelRating")
                    if hr in (3, 4, 5):
                        st.session_state["selected_star"] = int(hr)
                    st.session_state["last_picked_hotelCode"] = new_code

        params["radius_km"] = st.number_input(
            "Search radius (km)", value=DEFAULT_GEO_KM["hotel"], min_value=0.5, step=0.5
        )
        st.session_state.setdefault("selected_star", 4)
        if st.toggle("Override star intent", key="override_star_hotel"):
            params["selected_star"] = st.radio(
                "Selected ★ (user intent)", [3, 4, 5],
                horizontal=True, key="selected_star",
                help="Defaults to the picked hotel's star rating. Override here to test a different intent.",
            )
        else:
            # Auto-from-hotel default (already in session_state).
            params["selected_star"] = st.session_state.get("selected_star", 4)

    # ─── Location mode: flat dropdown per level (one search → one click) ──
    elif search_type == "Location":
        loc_type = st.radio(
            "Location level", ["Area", "City", "State", "Country"], horizontal=True
        )
        params["loc_type"] = loc_type

        # Map level → fetch_places key; "Area" reuses city list as the parent picker.
        place_level = "city" if loc_type == "Area" else loc_type.lower()
        label_field = {"country": "Country", "state": "State", "city": "City"}[place_level]
        if loc_type == "Area":
            label_field = "City (parent)"

        try:
            with st.spinner(f"Loading {place_level}s…"):
                places = fetch_places(place_level)
        except Exception as e:
            places = []
            st.error(f"Failed to load {place_level} list: {e}")

        if places:
            options = [None] + places  # leading blank
            picked = st.selectbox(
                label_field,
                options=options,
                format_func=lambda p: "—" if p is None else p["label"],
                key=f"loc_pick_{place_level}",
            )
            if picked:
                # Surface the full hierarchy so build_candidate_query can apply
                # term filters at every level (matches production query shape).
                params["country"] = picked.get("country")
                params["state"]   = picked.get("state")
                params["city"]    = picked.get("city")
        else:
            st.caption(f"No {place_level}s available. Check ES connectivity.")

        if loc_type == "Area" and params.get("city"):
            try:
                with st.spinner("Loading areas in this city…"):
                    area_options = fetch_areas_for_city(
                        params.get("country"), params.get("state"), params.get("city"),
                    )
            except Exception:
                area_options = []

            CUSTOM_LBL = "— Custom (free text) —"
            if area_options:
                pick = st.selectbox(
                    "Area / locality",
                    options=[CUSTOM_LBL] + area_options,
                    key="area_pick",
                )
                if pick == CUSTOM_LBL:
                    params["area_text"] = st.text_input(
                        "Custom area / locality",
                        placeholder="e.g. Bandra West",
                        key="area_custom",
                    )
                else:
                    params["area_text"] = pick
            else:
                st.caption(
                    "Couldn't derive area names from address text in this city. "
                    "Type one manually below."
                )
                params["area_text"] = st.text_input(
                    "Area / locality (matches address text)",
                    placeholder="e.g. Bandra, Connaught Place",
                    key="area_custom_only",
                )

            with st.expander("Optional geo center for Area"):
                lat = st.number_input("Lat", value=0.0, step=0.0001, format="%.6f", key="area_lat")
                lon = st.number_input("Lon", value=0.0, step=0.0001, format="%.6f", key="area_lon")
                radius = st.number_input(
                    "Radius (km)", value=DEFAULT_GEO_KM["area"], min_value=0.5, step=0.5,
                    key="area_radius",
                )
                if lat != 0.0 and lon != 0.0:
                    params["anchor"] = {"lat": lat, "lon": lon}
                    params["radius_km"] = radius

        st.session_state.setdefault("selected_star", 4)
        if st.toggle("Override star intent", key="override_star_loc"):
            params["selected_star"] = st.radio(
                "Selected ★ (user intent)", [3, 4, 5],
                horizontal=True, key="selected_star",
                help="Override the default. Note: location contexts use flat per-hotel-★ weights, "
                     "so this only matters if you switch the matrix mode in code.",
            )
        else:
            # Flat-weights mode — selected_star is unused by the score, but kept in
            # session_state so a later toggle-on shows the prior choice.
            params["selected_star"] = None

    # ─── Landmark mode: dropdown of presets + custom ──────────
    elif search_type == "Landmark":
        labels = ["— Custom (enter coords) —"] + [lm["name"] for lm in LANDMARKS]
        choice = st.selectbox("Landmark", labels, index=1)

        if choice == labels[0]:
            name = st.text_input("Landmark name (label only)", placeholder="e.g. My Office HQ")
            lat = st.number_input("Latitude", value=18.9220, step=0.0001, format="%.6f")
            lon = st.number_input("Longitude", value=72.8347, step=0.0001, format="%.6f")
            params["anchor"] = {"lat": lat, "lon": lon, "name": name}
        else:
            lm = LANDMARKS[labels.index(choice) - 1]
            params["anchor"] = {"lat": lm["lat"], "lon": lm["lon"], "name": lm["name"]}
            st.caption(f"📍 {lm['lat']:.4f}, {lm['lon']:.4f}")

        params["radius_km"] = st.number_input(
            "Radius (km)", value=DEFAULT_GEO_KM["landmark"], min_value=0.5, step=0.5
        )
        st.session_state.setdefault("selected_star", 4)
        if st.toggle("Override star intent", key="override_star_landmark"):
            params["selected_star"] = st.radio(
                "Selected ★ (user intent)", [3, 4, 5],
                horizontal=True, key="selected_star",
                help="Override the default. Landmark uses flat per-hotel-★ weights by default; "
                     "this is here as an override hook.",
            )
        else:
            params["selected_star"] = None

    st.divider()
    st.markdown("## Scoring Knobs")

    # Persistent affinity state — one matrix per search context.
    if "current_affinities" not in st.session_state:
        st.session_state["current_affinities"] = copy.deepcopy(ACTIVE_DEFAULTS["affinities"])
    if "aff_version" not in st.session_state:
        st.session_state["aff_version"] = 0

    with st.expander("Bayesian dampening", expanded=True):
        m = st.slider("m (prior weight)", 0, 200, ACTIVE_DEFAULTS["m"], 5, key="m",
                      help="At n=m reviews, hotel and prior weigh equally. Higher m = more skeptical of low-review hotels.")
        global_avg = st.slider("global_avg (platform mean)", 1.0, 5.0, ACTIVE_DEFAULTS["global_avg"], 0.05, key="global_avg")

    with st.expander("Star affinity matrices (per search context)", expanded=False):
        lam_s = st.slider("λ_s (star strength)", 0.0, 3.0, ACTIVE_DEFAULTS["lambda_s"], 0.1, key="lam_s",
                          help="0 = ignore stars  •  1 = default  •  2 = strict tier match")

        active_ctx = active_context(search_type, params)
        st.caption(
            f"Active context for current search: **{active_ctx}** · "
            "rows = selected ★, columns = hotel ★."
        )

        # One editor per context — flat 1×3 vector for non-Hotel, full 3×3 for Hotel.
        # All tabs render so edits to inactive tabs are still captured.
        tabs = st.tabs(SEARCH_CONTEXTS)
        affinities: dict[str, Any] = {}
        for ctx, tab in zip(SEARCH_CONTEXTS, tabs):
            with tab:
                data = st.session_state["current_affinities"][ctx]

                if is_flat_context(ctx):
                    # Flat 1×3: just hotel-★ → weight (no selected-★ dimension).
                    flat_df = pd.DataFrame(
                        {f"Hotel {h}★": [float(data.get(h, 1.0))] for h in (5, 4, 3)},
                        index=["weight"],
                    )
                    edited = st.data_editor(
                        flat_df,
                        use_container_width=True,
                        hide_index=False,
                        column_config={
                            col: st.column_config.NumberColumn(
                                col, min_value=0.0, max_value=1.0, step=0.05, format="%.2f",
                            )
                            for col in flat_df.columns
                        },
                        key=f"aff_editor_{ctx}_v{st.session_state['aff_version']}",
                    )
                    flat_weights: dict[int, float] = {}
                    for col in edited.columns:
                        h = int(col.split("★")[0].replace("Hotel ", ""))
                        flat_weights[h] = float(edited.iloc[0][col])
                    affinities[ctx] = flat_weights

                else:
                    # 3×3 matrix: selected ★ × hotel ★.
                    ordered = {
                        sel: dict(sorted(data[sel].items(), reverse=True))
                        for sel in sorted(data.keys(), reverse=True)
                    }
                    aff_df = pd.DataFrame(ordered).T
                    aff_df.index = [f"{s}★ selected" for s in aff_df.index]
                    aff_df.columns = [f"Hotel {h}★" for h in aff_df.columns]

                    edited = st.data_editor(
                        aff_df,
                        use_container_width=True,
                        hide_index=False,
                        column_config={
                            col: st.column_config.NumberColumn(
                                col, min_value=0.0, max_value=1.0, step=0.05, format="%.2f",
                            )
                            for col in aff_df.columns
                        },
                        key=f"aff_editor_{ctx}_v{st.session_state['aff_version']}",
                    )
                    matrix: dict[int, dict[int, float]] = {}
                    for sel_label in edited.index:
                        sel = int(sel_label.split("★")[0])
                        matrix[sel] = {}
                        for h_label in edited.columns:
                            h = int(h_label.split("★")[0].replace("Hotel ", ""))
                            matrix[sel][h] = float(edited.loc[sel_label, h_label])
                    affinities[ctx] = matrix

        default_affinity = st.number_input(
            "Default affinity (hotel ★ outside 3–5)",
            value=ACTIVE_DEFAULTS["default_affinity"],
            min_value=0.0, max_value=1.0, step=0.05,
            key="default_affinity",
        )
        aff_floor = st.slider(
            "aff_floor (min star factor)", 0.0, 0.5,
            ACTIVE_DEFAULTS["aff_floor"], 0.05, key="aff_floor",
            help="Floor on affinity^λ_s so a single bad-tier match can't fully zero out a hotel.",
        )

    with st.expander("Distance decay", expanded=False):
        lam_d = st.slider("λ_d (distance strength)", 0.0, 3.0,
                          ACTIVE_DEFAULTS["lambda_d"], 0.1, key="lam_d",
                          help="0 = ignore distance  •  1 = default  •  2 = distance dominates")
        offset_km = st.slider("offset_km (free zone)", 0.0, 5.0,
                              ACTIVE_DEFAULTS["offset_km"], 0.1, key="offset_km",
                              help="Within this radius, distance doesn't penalize at all.")
        scale_km = st.slider("scale_km (decay = 0.5 at offset+scale)", 0.5, 30.0,
                             ACTIVE_DEFAULTS["scale_km"], 0.5, key="scale_km",
                             help="Tighter scale = stricter proximity. Past 3× scale, decay ≈ 0.")
        decay_floor = st.slider(
            "decay_floor (min distance factor)", 0.0, 0.5,
            ACTIVE_DEFAULTS["decay_floor"], 0.05, key="decay_floor",
            help="Floor on decay^λ_d so far-away-but-otherwise-great hotels still surface.",
        )
        st.caption(
            "Decay only applies when there's an anchor (Hotel/Landmark, or City/Area "
            "with optional geo center). State / Country searches skip this term."
        )

    with st.expander("Fetch settings", expanded=False):
        candidate_size = st.slider(
            "Candidate set size from Elastic",
            50, 1000, ACTIVE_DEFAULTS["candidate_size"], 50,
            key="candidate_size",
        )

    # ─── Save / load weights profile ──────────────────────────
    with st.expander("💾 Save / load weights", expanded=False):
        current_config = {
            "m": int(m),
            "global_avg": float(global_avg),
            "lambda_s": float(lam_s),
            "lambda_d": float(lam_d),
            "offset_km": float(offset_km),
            "scale_km": float(scale_km),
            "aff_floor": float(aff_floor),
            "decay_floor": float(decay_floor),
            "default_affinity": float(default_affinity),
            "candidate_size": int(candidate_size),
            "affinities": affinities,
            "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
        }

        if st.button(
            "Update defaults to current values",
            type="primary", use_container_width=True,
        ):
            try:
                save_active_defaults(current_config)
                st.success(f"Defaults saved → {os.path.basename(DEFAULTS_FILE)}. New sessions start with these values.")
            except Exception as e:
                st.error(f"Failed to save defaults: {e}")

        rcol1, rcol2 = st.columns(2)
        if rcol1.button("Reset to factory", use_container_width=True):
            try:
                if os.path.exists(DEFAULTS_FILE):
                    os.remove(DEFAULTS_FILE)
                for k in ("m", "global_avg", "default_affinity",
                          "aff_floor", "decay_floor", "offset_km", "scale_km",
                          "candidate_size"):
                    st.session_state[k] = FACTORY_DEFAULTS[k]
                st.session_state["lam_s"] = FACTORY_DEFAULTS["lambda_s"]
                st.session_state["lam_d"] = FACTORY_DEFAULTS["lambda_d"]
                st.session_state["current_affinities"] = copy.deepcopy(FACTORY_DEFAULTS["affinities"])
                st.session_state["aff_version"] += 1
                st.session_state.pop("last_loaded_sig", None)
                st.toast("Reset to factory defaults", icon="↩️")
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")

        rcol2.download_button(
            "Download as JSON",
            data=json.dumps(
                {
                    **current_config,
                    "affinities": {
                        ctx: (
                            {str(k): float(v) for k, v in data.items()}
                            if is_flat_context(ctx)
                            else {
                                str(k): {str(kk): float(vv) for kk, vv in row.items()}
                                for k, row in data.items()
                            }
                        )
                        for ctx, data in current_config["affinities"].items()
                    },
                },
                indent=2,
            ),
            file_name=f"srp-weights-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

        uploaded = st.file_uploader(
            "Load weights from JSON",
            type=["json"],
            key="weights_upload",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            sig = f"{uploaded.name}:{uploaded.size}"
            if st.session_state.get("last_loaded_sig") != sig:
                try:
                    cfg = json.loads(uploaded.getvalue().decode("utf-8"))
                    # Back-compat: legacy "lambda" → lambda_s.
                    if "lambda" in cfg and "lambda_s" not in cfg:
                        cfg["lambda_s"] = cfg["lambda"]
                    st.session_state["m"] = int(cfg.get("m", FACTORY_DEFAULTS["m"]))
                    st.session_state["global_avg"] = float(cfg.get("global_avg", FACTORY_DEFAULTS["global_avg"]))
                    st.session_state["lam_s"] = float(cfg.get("lambda_s", FACTORY_DEFAULTS["lambda_s"]))
                    st.session_state["lam_d"] = float(cfg.get("lambda_d", FACTORY_DEFAULTS["lambda_d"]))
                    st.session_state["offset_km"] = float(cfg.get("offset_km", FACTORY_DEFAULTS["offset_km"]))
                    st.session_state["scale_km"] = float(cfg.get("scale_km", FACTORY_DEFAULTS["scale_km"]))
                    st.session_state["aff_floor"] = float(cfg.get("aff_floor", FACTORY_DEFAULTS["aff_floor"]))
                    st.session_state["decay_floor"] = float(cfg.get("decay_floor", FACTORY_DEFAULTS["decay_floor"]))
                    st.session_state["default_affinity"] = float(cfg.get("default_affinity", FACTORY_DEFAULTS["default_affinity"]))
                    st.session_state["candidate_size"] = int(cfg.get("candidate_size", FACTORY_DEFAULTS["candidate_size"]))

                    # Per-context affinity (mixed shape) with back-compat for legacy "affinity".
                    new_affs = copy.deepcopy(FACTORY_AFFINITIES)
                    if isinstance(cfg.get("affinities"), dict):
                        for ctx, raw in cfg["affinities"].items():
                            if ctx not in SEARCH_CONTEXTS:
                                continue
                            coerced = _coerce_affinity(ctx, raw)
                            if coerced is not None:
                                new_affs[ctx] = coerced
                    elif isinstance(cfg.get("affinity"), dict):
                        legacy = _coerce_matrix(cfg["affinity"])
                        if legacy:
                            new_affs["Hotel"] = legacy
                    st.session_state["current_affinities"] = new_affs

                    st.session_state["aff_version"] += 1
                    st.session_state["last_loaded_sig"] = sig
                    st.success(f"Loaded weights from {uploaded.name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load: {e}")

        st.caption("File is plain JSON — keep one per tuning experiment to compare runs.")


# ─── Main: KPI strip ──────────────────────────────────────────
candidates = st.session_state.get("candidates", [])
last_total = st.session_state.get("last_total")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Candidates", f"{len(candidates):,}" if candidates else "—")
k2.metric("Total in ES", f"{last_total:,}" if last_total else "—")
k3.metric("Selected ★", params.get("selected_star") or "—")
k4.metric("λ_s · λ_d", f"{lam_s:.1f} · {lam_d:.1f}")
k5.metric("scale_km", f"{scale_km:.1f}")
k6.metric("Bayesian m", f"{m}")

# ─── Action bar: Search button + Sort selector ────────────────
ac1, ac2 = st.columns([1.4, 4])
with ac1:
    fetch = st.button("Search Hotels", type="primary", use_container_width=True)
with ac2:
    sort_type = st.segmented_control(
        "Sort",
        options=["Recommended", "Popularity", "Nearby", "Hotel Stars"],
        default="Recommended",
        label_visibility="collapsed",
    ) or "Recommended"

# ─── ES fetch on click ────────────────────────────────────────
if fetch:
    # ── Location mode: resolve bbox + centroid from ES (mirrors production
    # location resolver, which has NE/SW coords stored per location).
    if search_type == "Location":
        loc_type = (params.get("loc_type") or "").lower()
        try:
            with st.spinner("Resolving location geometry…"):
                geom = fetch_location_geometry(
                    params.get("country"), params.get("state"), params.get("city"),
                )
            if geom:
                params["bbox"] = geom["bbox"]
                # Use computed centroid as anchor only when user didn't override
                # AND the location level is meaningful for distance (City/Area).
                if not params.get("anchor") and loc_type in ("city", "area"):
                    params["anchor"] = geom["centroid"]
                if not params.get("radius_km") and loc_type in ("city", "area"):
                    params["radius_km"] = 25.0 if loc_type == "city" else 5.0
        except Exception as e:
            st.warning(f"Location geometry lookup failed: {e}. Falling back to term filters only.")

    body = build_candidate_query(search_type, params, size=candidate_size)
    try:
        with st.spinner("Querying Elastic…"):
            resp = es_search(body)
        rows = hits_to_rows(resp)

        # In Hotel mode, ensure the anchor hotel is in the candidate set.
        anchor_code = params.get("anchor_hotelCode")
        if search_type == "Hotel" and anchor_code:
            if not any(r.get("hotelCode") == anchor_code for r in rows):
                anchor_src = fetch_hotel_by_code(anchor_code)
                if anchor_src:
                    rows.insert(0, source_to_row(anchor_src))

        st.session_state["candidates"] = rows
        st.session_state["last_anchor"] = params.get("anchor")
        st.session_state["last_anchor_hotelCode"] = anchor_code
        st.session_state["last_search_type"] = search_type
        st.session_state["last_query"] = body
        st.session_state["last_bbox"] = params.get("bbox")
        st.session_state["last_centroid"] = (
            params.get("anchor") if search_type == "Location" else None
        )
        total = resp.get("hits", {}).get("total", {})
        st.session_state["last_total"] = total.get("value") if isinstance(total, dict) else total
        st.toast(f"Fetched {len(rows)} candidates", icon="✅")
        candidates = rows
        last_total = st.session_state["last_total"]
    except Exception as e:
        st.error(f"ES query failed: {e}")

# ─── Results ──────────────────────────────────────────────────
if candidates:
    scoring = {
        "m": m,
        "global_avg": global_avg,
        "selected_star": params.get("selected_star"),
        "lambda_s": lam_s,
        "lambda_d": lam_d,
        "offset_km": offset_km,
        "scale_km": scale_km,
        "aff_floor": aff_floor,
        "decay_floor": decay_floor,
        "affinities": affinities,
        "context": active_context(
            st.session_state.get("last_search_type", search_type),
            params,
        ),
        "default_affinity": default_affinity,
        "anchor": st.session_state.get("last_anchor"),
    }
    scored = [score_row(r, scoring) for r in candidates]
    ranked = apply_sort(
        scored, sort_type,
        anchor_hotel_code=st.session_state.get("last_anchor_hotelCode"),
    )

    df = pd.DataFrame(ranked)
    show_cols = [
        "hotelCode", "hotelName", "propertyType", "cityName", "hotelRating", "userAvgRating",
        "hotelTotalReviews", "adj_rating", "affinity", "decay",
        "distance_km", "final_score", "address",
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    df = df[show_cols].copy()
    df.index = range(1, len(df) + 1)
    df.index.name = "#"

    top_n = min(len(df), 50)

    st.dataframe(
        df.head(top_n),
        use_container_width=True,
        height=min(700, 60 + 35 * top_n),
        column_config={
            "hotelCode":         st.column_config.TextColumn("ID", width="small", help="Elastic hotelCode — useful for debugging / verifying against the index."),
            "hotelName":         st.column_config.TextColumn("Hotel", width="large"),
            "propertyType":      st.column_config.TextColumn("Type", width="small", help="Property type from the ES index (Hotel, Apartment, Villa, etc.)."),
            "cityName":          st.column_config.TextColumn("City", width="small"),
            "hotelRating":       st.column_config.NumberColumn("★", format="%d"),
            "userAvgRating":     st.column_config.NumberColumn("User ★", format="%.2f"),
            "hotelTotalReviews": st.column_config.NumberColumn("Reviews", format="%d"),
            "adj_rating":        st.column_config.ProgressColumn(
                "Adj. Rating", min_value=1.0, max_value=5.0, format="%.3f",
            ),
            "affinity":          st.column_config.NumberColumn("Affinity", format="%.2f"),
            "decay":             st.column_config.NumberColumn("Decay", format="%.2f"),
            "final_score":       st.column_config.ProgressColumn(
                "Final Score", min_value=0.0, max_value=5.0, format="%.3f",
            ),
            "distance_km":       st.column_config.NumberColumn("Dist (km)", format="%.2f"),
            "address":           st.column_config.TextColumn("Address", width="medium"),
        },
    )

    cap_l, cap_r = st.columns([4, 1])
    has_anchor = bool(scoring.get("anchor") and scoring["anchor"].get("lat") is not None)
    sel_repr = f"**{scoring['selected_star']}**" if scoring.get("selected_star") else "—"
    cap_l.caption(
        f"Sort: **{sort_type}** · Context **{scoring.get('context', '—')}** · "
        f"Selected ★ {sel_repr} · "
        f"λ_s {lam_s} · λ_d {lam_d if has_anchor else '—'} · "
        f"scale {scale_km}km · offset {offset_km}km · "
        f"m {m} · global_avg {global_avg} · "
        f"showing top {top_n} of {len(df):,}"
    )
    if len(df) > top_n:
        with cap_r:
            st.caption(f"+{len(df) - top_n:,} more")

    if st.session_state.get("last_anchor_hotelCode") and sort_type == "Recommended":
        st.caption(
            f"📌 Anchor hotel `{st.session_state['last_anchor_hotelCode']}` is pinned at #1 (user-selected)."
        )

    bbox = st.session_state.get("last_bbox")
    cen = st.session_state.get("last_centroid")
    if bbox or cen:
        bits = []
        if cen and cen.get("lat") is not None:
            bits.append(f"centroid `{cen['lat']:.4f}, {cen['lon']:.4f}`")
        if bbox:
            tl, br = bbox.get("top_left", {}), bbox.get("bottom_right", {})
            bits.append(
                f"bbox NW `{tl.get('lat'):.3f}, {tl.get('lon'):.3f}` → "
                f"SE `{br.get('lat'):.3f}, {br.get('lon'):.3f}`"
            )
        st.caption("📐 Resolved geometry · " + " · ".join(bits))

    with st.expander("Last ES query body (copy to Postman)"):
        st.json(st.session_state.get("last_query"))

    # ─── Competitor comparison: Booking.com (feature-flagged) ─
    if SHOW_COMPETITOR_SECTION:
      st.markdown("---")
      with st.expander("Compare with Booking.com", expanded=False):
        st.caption(
            "Run the same query on booking.com manually, then enter their top hotels "
            "below. We'll render Ours vs. Booking side-by-side. "
            "Note: Booking's user rating is on a **0–10** scale; ours is **0–5**."
        )

        from srp_simulator.competitors import (
            COMPETITOR_FIELDS,
            empty_template,
            normalise_rows,
        )

        if "competitor_booking_df" not in st.session_state:
            st.session_state["competitor_booking_df"] = pd.DataFrame(empty_template(20))

        col_a, col_b = st.columns([1, 4])
        if col_a.button("Reset table", use_container_width=True, key="reset_booking_table"):
            st.session_state["competitor_booking_df"] = pd.DataFrame(empty_template(20))
            st.rerun()
        col_b.caption(
            "Each row = one hotel from Booking's results. Add/remove rows freely. "
            "Empty rows are ignored."
        )

        edited_competitor = st.data_editor(
            st.session_state["competitor_booking_df"],
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "hotelName":         st.column_config.TextColumn("Hotel", width="large", required=False),
                "hotelRating":       st.column_config.NumberColumn("★", min_value=1, max_value=5, step=1, format="%d"),
                "userAvgRating":     st.column_config.NumberColumn("User rating (0-10)", min_value=0.0, max_value=10.0, step=0.1, format="%.1f"),
                "hotelTotalReviews": st.column_config.NumberColumn("Reviews", min_value=0, step=1, format="%d"),
                "price":             st.column_config.NumberColumn("Price (₹)", min_value=0, step=100, format="%d"),
                "url":               st.column_config.LinkColumn("URL", width="medium"),
            },
            key="competitor_booking_editor",
        )
        st.session_state["competitor_booking_df"] = edited_competitor

        booking_rows = normalise_rows(edited_competitor.to_dict("records"))

        if booking_rows:
            st.markdown("##### Side-by-side: top hotels")
            ours_col, theirs_col = st.columns(2)

            with ours_col:
                st.markdown("**Ours** (current sort)")
                ours_top = ranked[: min(len(ranked), 20)]
                ours_df = pd.DataFrame([
                    {
                        "Rank":         i,
                        "Hotel":        r.get("hotelName"),
                        "★":            r.get("hotelRating"),
                        "User ★ (0-5)": r.get("userAvgRating"),
                        "Reviews":      r.get("hotelTotalReviews"),
                        "Final":        round(r.get("final_score", 0), 3),
                    }
                    for i, r in enumerate(ours_top, start=1)
                ])
                st.dataframe(ours_df, use_container_width=True, hide_index=True, height=560)

            with theirs_col:
                st.markdown("**Booking.com** (manual entry)")
                theirs_df = pd.DataFrame([
                    {
                        "Rank":              r["rank"],
                        "Hotel":             r["hotelName"],
                        "★":                 r.get("hotelRating"),
                        "User ★ (0-10)":     r.get("userAvgRating"),
                        "Reviews":           r.get("hotelTotalReviews"),
                        "Price":             r.get("price"),
                    }
                    for r in booking_rows
                ])
                st.dataframe(theirs_df, use_container_width=True, hide_index=True, height=560)

            # Quick overlap analysis: hotels that appear on both lists.
            ours_names = {(r.get("hotelName") or "").strip().lower()
                          for r in ranked[: min(len(ranked), 20)] if r.get("hotelName")}
            their_names = {r["hotelName"].strip().lower() for r in booking_rows}
            overlap = sorted(ours_names & their_names)
            ours_only = len(ours_names - their_names)
            theirs_only = len(their_names - ours_names)

            ov_col1, ov_col2, ov_col3 = st.columns(3)
            ov_col1.metric("Overlap (top-20)", len(overlap))
            ov_col2.metric("Only in ours", ours_only)
            ov_col3.metric("Only in Booking", theirs_only)

            if overlap:
                st.caption(
                    "Hotels in both lists: "
                    + ", ".join(f"`{n}`" for n in overlap[:8])
                    + ("…" if len(overlap) > 8 else "")
                )
        else:
            st.caption("Add at least one Booking row above to enable side-by-side view.")

else:
    st.markdown(
        """
        <div class="empty-card">
          <div class="empty-icon">⌖</div>
          <div class="empty-title">Nothing to rank yet</div>
          <div class="empty-body">
            Set a search input in the sidebar — a hotel, a location, or a
            landmark — and run a query. Tweak any scoring knob afterwards
            and the ranking re-computes instantly.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
