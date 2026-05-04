# Release Notes: Mirador — SRP Phase 1 Simulator v0.1.0

**Product:** Mirador — **Status:** Initial internal release, local-only — **Date:** 2026-04-30 — **Entry:** `streamlit run app.py` → `http://localhost:8501`

Mirador is an internal dashboard for tuning the OnArrival hotel SRP ranking against live Elastic data. It pulls candidates from `search-master-hotel-details-test` using the production query shape, applies the Phase 1 scoring formula (`adjusted_rating × affinity^λ_s × distance_decay^λ_d`), and lets a PM/engineer change every knob — Bayesian prior, λ_s, λ_d, scale_km, offset_km, floors, per-context affinity weights — and watch the SRP re-rank instantly without re-querying Elastic. The v0.1.0 cut establishes the full Phase 1 formula, all three search intents, the production-parity candidate query, persisted weight profiles, light/dark themes, and a modular code layout that is ready to push to GitHub and deploy to Streamlit Community Cloud.

Repo target: `pranavoa/srp-vision`. Local layout: `app.py` (UI orchestration) + `srp_simulator/` package (`config`, `elastic`, `scoring`, `persistence`, `theme`, `competitors`).

---

## Naming

The product ships as **Mirador**. *Mirador* is Spanish for "lookout" — a vantage point you climb up to in order to see clearly. That is precisely the role of this dashboard: a vantage point onto the Phase 1 SRP, where you can see exactly how the formula behaves on live data, what each knob does, and where the ranking composition shifts under tuning. The name lives in the Streamlit page title, the dashboard header, the package metadata (`__product__ = "Mirador"`), and the GitHub repo description. The brand mark in the header is a minimal viewfinder-with-peak SVG — a circle (the sight) with a horizon line and a small summit inside, evoking the act of observing the landscape from an elevated platform.

---

## What's New

- **Phase 1 scoring formula end to end.** `final = adjusted_rating × max(aff_floor, affinity^λ_s) × max(decay_floor, distance_decay^λ_d)` is implemented in `srp_simulator/scoring.py` with conditional behaviour: distance term is skipped when there is no anchor; star term is skipped for flat contexts (Landmark/Area/City/State/Country) when the user has not overridden their star intent.
- **Bayesian-shrunk user rating.** `adjusted_rating = (n × r + m × global_avg) / (n + m)` pulls low-review hotels toward the platform mean. `m` and `global_avg` are sliders in the sidebar and persist to `user_defaults.json`.
- **Per-context affinity, mixed shape.** Hotel mode uses the full 3×3 matrix `affinity[selected_★][hotel_★]`. Landmark/Area/City/State/Country each use a flat 1×3 vector keyed by hotel star, since there is no selected-★ intent for "hotels in Mumbai" or "hotels near Gateway of India". Each context has its own editable tab in the sidebar.
- **Anchor-aware Gaussian distance decay.** `decay = exp(−max(0, d − offset_km)² / (2 × scale_km²))`. Within `offset_km` the distance has zero penalty; at `offset + scale` decay reaches 0.5; past 3× scale it goes effectively to zero. `decay_floor` and `aff_floor` prevent any single dimension from fully zeroing a hotel's score.
- **Three search intents.** Hotel mode resolves an anchor hotel via name autocomplete, auto-snaps `selected_★` to that hotel's tier, and pins the anchor at `#1` in the Recommended sort. Location mode supports Area / City / State / Country with cascading dropdowns built from `composite` aggregations, plus an Area-name dropdown derived heuristically from address text. Landmark mode ships with 20 curated presets across Mumbai/Delhi/Goa/Bangalore/Chennai/Hyderabad/Kolkata/Udaipur/Agra/Jaipur and a "Custom (enter coords)" fallback.
- **Production-parity candidate query.** Every Elastic query applies `hotelRating ≥ 3`, `hasImages = true`, and `providerCode.vervoTech` exists AND (`providerCode.CT` OR `providerCode.TBO`). Geo handling per intent: Hotel/Landmark use `geo_distance` from the anchor; Location/City and Location/Area add a `geo_bounding_box` filter and a tighter `geo_distance` from the city centroid; Location/State and Location/Country use `geo_bounding_box` only. Results are sorted by `_geo_distance` ascending when an anchor is present.
- **Auto-resolved location geometry.** Production stores NE/SW coords per location in a separate index. The simulator does not have access to that resolver, so it derives equivalent geometry from hotel positions in Elastic via a single `geo_bounds` + `geo_centroid` aggregation per location query, cached for one hour. The resolved bounding box and centroid are surfaced in a "📐 Resolved geometry" caption under the results so the PM can inspect what was used.
- **User-pinnable anchor hotel.** When the user picks a specific anchor hotel in Hotel mode, that hotel is fetched separately via `hotelCode.keyword` if it is not already in the candidate set, and pinned at `#1` in the Recommended sort regardless of how the formula would otherwise rank it. Other sort tabs do not pin.
- **Override star intent toggle.** Across all three search modes, the `Selected ★ (user intent)` radio is hidden behind a per-mode toggle. In Hotel mode the underlying state is auto-set from the picked hotel's `hotelRating`; in Landmark/Location modes it is `None` by default (so the flat per-hotel-★ vector applies without an intent dimension). Toggling the override exposes a 3/4/5 radio for explicit override.
- **Save / load / reset for weights.** `user_defaults.json` lives next to `app.py` and is read at session start by `load_active_defaults()`. The sidebar exposes "Update defaults to current values", "Reset to factory", and "Download as JSON". Upload of a previously-downloaded JSON profile restores every knob, including `candidate_size`. Backward-compat: a legacy single `"affinity"` matrix in an older JSON profile is auto-migrated into the Hotel-mode slot, and a legacy `"lambda"` key is mapped to `lambda_s`.
- **Sort tabs with consistent secondary keys.** Recommended sorts by `final_score` desc with anchor-hotel pin. Popularity sorts by `adj_rating` desc, secondary `final_score` desc. Nearby sorts by `distance_km` asc, secondary `final_score` desc. Hotel Stars sorts by `hotelRating` desc, secondary `adj_rating` desc.
- **Apple-inspired dark, Notion-inspired light.** Two complete CSS themes ship in `srp_simulator/theme.py`. Light uses Notion-style warm off-white surfaces with a single neutral accent; dark uses rich black with frosted-glass cards (`backdrop-filter: blur`), Apple system-blue accent, and ambient radial gradients. Toggle is a sidebar switch; the persisted theme choice survives reloads in the same session.
- **Inter + Ubuntu Sans Mono typography.** Inter for body and labels (loaded from Google Fonts). Ubuntu Sans Mono for KPIs, numerics, code blocks, and the dataframe headers (served locally from `static/fonts/` via Streamlit's `enableStaticServing`). Antialiased, slight letter-spacing tightening on display sizes.
- **Modular package layout.** `dashboard.py` (~2000-line single file) is replaced by `app.py` (UI orchestration only, ~730 lines) plus `srp_simulator/` modules for `config`, `elastic`, `scoring`, `persistence`, `theme`, and `competitors`. Pure logic (`scoring.py`, `persistence.py`) is import-free of Streamlit so it is trivially testable.
- **Hotel ID column in the results table.** The leftmost column shows each hotel's `hotelCode` so a PM can quickly verify a row against the index without round-tripping through hotel name.
- **Competitor comparison panel (feature-flagged off).** Side-by-side Ours vs. Booking.com top-20 viewer with an inline editable table, overlap metric, and a stub class for the future Booking Demand API integration. `SHOW_COMPETITOR_SECTION = False` in `app.py` hides it for now; flip to `True` to expose. The supporting module (`srp_simulator/competitors.py`) ships in the repo so the swap to a real provider is well-scoped.

---

## Why this release matters

The Phase 1 PRD defines an asymmetric-affinity, distance-aware ranking formula that replaces the previous superficial sort. Before this release, there was no way to feel the formula's behaviour against live Elastic data — every change required code edits and a fresh deploy. v0.1.0 closes that gap.

- A PM can now answer "how does my SRP look in Mumbai if I prefer 4★ hotels but allow 5★ to bleed in at 0.85 strength" in seconds.
- An engineer can verify that production-parity filters (rating ≥ 3, hasImages, provider availability, bbox + distance) are returning the candidate set we expect, before pushing those filters into the actual SRP service.
- The Bayesian prior `m` and global mean `global_avg` are visible knobs, not buried constants — so the question "should `m` be 30 or 50 for our review distribution?" becomes a slider and a side-by-side comparison instead of a debate.
- Distance decay parameters (`scale_km`, `offset_km`, `λ_d`) are tunable per search type. The PRD calls out that a Bangalore Airport search wants `scale=10km` while a Phoenix Mall search wants `scale=3km`. The simulator lets you confirm that without shipping anything.
- All these knobs persist to JSON. Tuning sessions become reproducible artifacts you can share by uploading a profile.

This is the foundation for the upcoming Phase 1 production rollout. The simulator's scoring formula is the same code path we will land in the SRP service, modulo Painless rewrites where required.

---

## Architecture

### Project layout

```
srp-phase1-simulator/
├── app.py                         # Streamlit entry — UI orchestration only
├── srp_simulator/                 # Pure-logic + helpers package
│   ├── __init__.py
│   ├── config.py                  # Env vars, factory defaults, presets, geo constants
│   ├── elastic.py                 # ES query builders + cached aggregations
│   ├── scoring.py                 # Bayesian rating, affinity, decay, sort
│   ├── persistence.py             # Load / save / coerce JSON profiles
│   ├── theme.py                   # Light + dark CSS strings + inject_theme
│   └── competitors.py             # Pluggable competitor provider interface
├── docs/                          # PRD + ES schema reference + this release note
│   ├── elastic-schema.md
│   ├── ranking-phase-1.md
│   └── ranking-phase-1-distance.md
├── static/fonts/                  # Ubuntu Sans Mono (variable)
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── requirements.txt
├── README.md
├── LICENSE
├── .env.example
├── .gitignore
└── user_defaults.json             # Local-only, gitignored
```

### Scoring pipeline

1. **Candidate query** — `srp_simulator.elastic.build_candidate_query(search_type, params, size)` assembles a production-style ES body: `production_filters()` + per-intent geo (`geo_distance` and/or `geo_bounding_box`) + `_geo_distance` sort + `timeout: 30s` + `from: 0`.
2. **Optional geometry resolution** — for Location-mode queries (Country/State/City/Area), `fetch_location_geometry()` runs a one-shot `geo_bounds` + `geo_centroid` aggregation to derive a bbox and centroid. Cached for 1 hour.
3. **Anchor pinning** — in Hotel mode, if the user-picked anchor hotel is not in the candidate set, `fetch_hotel_by_code()` retrieves it separately and prepends.
4. **Per-row scoring** — `score_row(row, scoring)` computes:
   - `adj = adjusted_rating(reviews, user_avg, m, global_avg)`
   - `a_eff = max(aff_floor, affinity_lookup(...) ^ λ_s)` — flat lookup for Landmark/Area/City/State/Country, matrix lookup for Hotel
   - `decay_eff = max(decay_floor, distance_decay(d, offset_km, scale_km) ^ λ_d)` — only when an anchor exists
   - `final = adj × a_eff × decay_eff`
5. **Sort** — `apply_sort(rows, sort_type, anchor_hotel_code)` applies the user's chosen sort tab. Recommended pins the anchor hotel at `#1` if present.
6. **Render** — KPI strip + sort selector + dataframe with progress columns for `adj_rating` and `final_score`. The "Last ES query body" expander surfaces the actual JSON sent to the cluster, copy-paste-ready for Postman.

### Production-parity Elastic query

Every candidate query carries:

| Filter | Source | Why |
| --- | --- | --- |
| `range hotelRating gte 3` | `srp_simulator.elastic.production_filters()` | Hard rule: never surface 1-2★ hotels |
| `term hasImages true` | same | Hotels without images are hidden in production |
| `exists providerCode.vervoTech` AND (`exists providerCode.CT` OR `exists providerCode.TBO`) | same | Production provider availability gate |

Per-intent geo:

| Intent | Geo applied | Sort anchor |
| --- | --- | --- |
| Hotel | `geo_distance` from anchor hotel + `cityName.keyword` term | Anchor hotel coords |
| Landmark | `geo_distance` from landmark coords | Landmark coords |
| Location → Country / State | `geo_bounding_box` only (auto-resolved) | None |
| Location → City | `geo_bounding_box` + `geo_distance` 25 km from centroid | Centroid |
| Location → Area | bbox + `geo_distance` 5 km from centroid + `match address` for area text | Centroid |

The bounding box and centroid for Location-mode queries are not hardcoded; they are computed by aggregating the lat/lon of all hotels matching the term filter. This mimics the production location resolver's NE/SW coordinates without requiring access to the resolver itself.

### Per-context affinity shapes

| Context | Shape | Schema |
| --- | --- | --- |
| Hotel | 3×3 matrix | `{ selected_★: { hotel_★: weight } }` |
| Landmark | 1×3 vector | `{ hotel_★: weight }` |
| Area | 1×3 vector | same |
| City | 1×3 vector | same |
| State | 1×3 vector | same |
| Country | 1×3 vector | same |

The factory defaults are the PRD matrix for Hotel and the PRD's "selected = 4" row `{5: 0.90, 4: 1.00, 3: 0.75}` for the flat contexts, preserving prior `defaults to selected_star = 4` behaviour. The user can edit each context's table independently, and `score_row` dispatches on `is_flat_context(ctx)` to pick the right lookup shape.

### Configuration

Credentials are read from environment variables first, then `st.secrets`, then a safe non-secret default for URL / index. **`ES_API_KEY` has no default** — `srp_simulator.elastic.es_search()` raises a `RuntimeError` with a clear message if no key is configured.

| Key | Required | Source priority |
| --- | --- | --- |
| `ES_API_KEY` | yes | env > `st.secrets` > error |
| `ES_URL` | no | env > `st.secrets` > safe default |
| `ES_INDEX` | no | env > `st.secrets` > safe default |
| `APP_PASSWORD` | no | env > `st.secrets` > unset (no gate) |

The `.env.example` and `.streamlit/secrets.toml.example` templates show the expected schema; the real files are gitignored.

### Persistence

Tuning state survives across sessions through `user_defaults.json`:

- `load_active_defaults()` — runs at script import; reads the file if present, else returns `FACTORY_DEFAULTS`. Backward-compat handles legacy `"lambda"` and single `"affinity"` keys from older profiles.
- `save_active_defaults(cfg)` — writes the current config including all numeric knobs (`m`, `global_avg`, `lambda_s`, `lambda_d`, `offset_km`, `scale_km`, `aff_floor`, `decay_floor`, `default_affinity`, `candidate_size`) and the per-context affinity shapes.
- `coerce_affinity(ctx, raw)` — picks `_coerce_matrix` for Hotel and `_coerce_flat_weights` for everything else, so JSON's string-keyed dicts come back as int-keyed dicts of the right shape.

`user_defaults.json` lives at the project root and is gitignored. On Streamlit Community Cloud the container is ephemeral, so saved defaults will not persist across redeploys; for local benchmarking it is the source of truth across browser-tab refreshes within a session.

### Theming

`srp_simulator.theme.inject_theme(dark)` injects one of two CSS strings:

- **Light** — Notion-inspired warm off-white surfaces, single accent on focus rings, hairline 1 px borders, soft hover lifts.
- **Dark** — Apple-inspired rich black with two faint radial gradients (top-left blue, bottom-right indigo), glass surfaces with `backdrop-filter: blur(20px)`, system-blue/indigo gradient on primary buttons, glow on focus, gradient border on the app header via `mask-composite: exclude`.

All transitions use `cubic-bezier(0.16, 1, 0.3, 1)` at 180–240 ms so hovers and focus changes feel "smooth" rather than abrupt. The Streamlit collapsed-sidebar control is explicitly styled in both themes so it never disappears against the background.

---

## User Impact

**Who:** Hotel SRP product managers and ranking engineers who need to feel how the Phase 1 formula behaves on live Elastic data without writing code or shipping a deploy.

**How it benefits them:**

- A PM can validate that "`m = 50` is enough to dampen low-review hotels in Mumbai" by sliding `m` and watching the table re-rank instantly.
- An engineer can verify that the production filter set (`hotelRating ≥ 3`, `hasImages = true`, vervoTech + CT/TBO) returns the candidate count and quality they expect — and copy the actual ES body from the "Last ES query body" expander into Postman or Kibana for further inspection.
- Anyone can compare the Recommended sort against Popularity, Nearby, and Hotel Stars side-by-side using the segmented sort control, and see how the secondary `final_score` (or `adj_rating` for Hotel Stars) breaks ties within each bucket.
- A PM tuning per-search-type behaviour can switch between Landmark / Area / City / State / Country contexts and edit each context's flat weight vector independently, with the active context surfaced in the caption under the results.
- A reviewer can hand-edit `user_defaults.json` between sessions to reproduce a teammate's tuning, then close-and-reopen the tab to load it.
- The Hotel ID column on the leftmost edge of the results table makes spot-checking a row against the index a one-click copy of `hotelCode`.

---

## Metrics & Validation

Watch these during tuning sessions:

- **Recommended sort top-20 stability under λ_s changes.** Slide λ_s from 0 (ignore stars) to 2 (strict tier) and confirm the top 20 churn matches PRD expectations: a 5★ user with `λ_s = 2` should push 3★ hotels out fast.
- **Distance decay shape under λ_d changes.** With an anchor set, sliding `λ_d` from 0 to 2 should compress the SRP toward the anchor coords. Watch the `decay` column to confirm the Gaussian shape (1.0 inside `offset_km`, 0.5 at `offset + scale_km`, near zero past 3× scale).
- **Floor behaviour.** Set `aff_floor = 0` and `decay_floor = 0` and confirm that a 3★ hotel 30 km from an anchor with `λ_d = 2` collapses to effectively zero `final_score`. Then raise both floors to 0.15 and confirm the same hotel survives at a non-trivial score — that is the "no single dimension can fully zero a hotel" guarantee.
- **Anchor-pin invariant in Hotel mode.** Pick an anchor hotel that is far from any other 5★ hotel. In Recommended sort it must always be `#1`. In Nearby, Popularity, and Hotel Stars it should rank only by the formula, not by pin.
- **Bayesian dampening on cold-start hotels.** Sort by Popularity, then slide `m` from 0 (raw `userAvgRating`) to 200 (heavy prior). Hotels with a 5.0 raw rating but only 8 reviews should fall sharply as `m` increases.
- **Geometry resolver sanity.** Run a Location → City → Mumbai query and verify the resolved centroid in the "📐 Resolved geometry" caption is somewhere central (Bandra/Worli/Dadar area for hotel density), and the bounding box covers the metro extent.
- **Backward-compat for legacy profiles.** Upload a JSON profile with the old single `"affinity"` matrix (no per-context shape) and confirm it is migrated into the Hotel-mode tab, with all flat contexts reset to factory.
- **Per-context isolation.** Edit Hotel-mode affinity, then switch to City context and confirm Hotel-mode edits did not bleed in (each tab keys its data editor on `aff_editor_{ctx}_v{aff_version}`).
- **Override-star toggle persistence.** In Hotel mode, pick a 5★ anchor hotel without enabling the override toggle. Confirm `selected_star` becomes 5 (auto-snap from picked hotel). Switch to Landmark mode and confirm `selected_star` is `None` (flat weights drive the score). Toggle on the override in Landmark and pick 3 — confirm caption now shows `Selected ★ 3` but score does not change because Landmark uses flat weights.

---

## Rollout Status & Strategy

- **Status:** Local-only; not yet deployed.
- **Branch:** `main` (initial commit pending GitHub push).
- **GitHub target:** `pranavoa/srp-vision`.
- **Deploy plan:** Streamlit Community Cloud is the recommended host. Vercel is not viable for Streamlit (serverless function runtime, no long-running WebSocket support). Alternative containers: Render, Railway, Fly.io.
- **Index impact:** None. The simulator is read-only against `search-master-hotel-details-test`.
- **Service impact:** None. The SRP service in production is unaffected. Once the Phase 1 formula is verified via this simulator, the same scoring code in `srp_simulator/scoring.py` will be ported to the production ranking pipeline (with Painless rewrites where ES-side scoring is needed).
- **Secret handling:** `ES_API_KEY` is not committed. Local devs use `.streamlit/secrets.toml` (gitignored); the Cloud deploy uses Streamlit Cloud's Secrets UI. `APP_PASSWORD`, when set, gates app access for any non-trivial deploy.

---

## Validation

Local sanity checks:

```bash
# Module-level syntax + import check
python3 -c "from srp_simulator import config, scoring, persistence, elastic, theme; print('OK')"

# Pure-scoring sanity check
python3 -c "
from srp_simulator.scoring import haversine_km, adjusted_rating, distance_decay
print('haversine 0->1° lat:', haversine_km((0,0),(1,0)))   # ~111.19
print('adj_rating cold-start:', adjusted_rating(8, 4.8, 50, 4.3))  # ~4.37
print('decay at 5km offset+scale=0.5km/5km:', distance_decay(5, 0.5, 5))  # ~0.5
"

# Run the dashboard
streamlit run app.py
```

Manual UX walkthroughs:

- Hotel mode: search `taj mahal palace`, confirm 5★ auto-snap, search radius 12 km default, Recommended pins the picked hotel at `#1`.
- Location → City → Mumbai: confirm "📐 Resolved geometry" caption, confirm `Dist (km)` column populated, switch to Nearby sort.
- Landmark → Gateway of India: confirm radius defaults to 12 km, confirm flat weights apply (Selected ★ stays `—` until override toggle).
- Area → pick a city → "Bandra" suggestion appears in the dropdown derived from address text.
- Save / load round-trip: nudge `m` to 80, click "Update defaults to current values", check `user_defaults.json` shows `"m": 80`, close-and-reopen tab, confirm slider opens at 80.
- Reset to factory: click button, confirm `user_defaults.json` is deleted and all knobs revert.
- Theme toggle: flip Dark mode, confirm header gradient changes and KPI cards become glass-style; reload page and confirm theme choice does not survive (session_state-only by design).

---

## Known Issues / Edge Cases

- **No price field in the index.** `pricingV2` and `pricing` only carry metadata (currency, sampleCount, source); no actual `price` numeric field. As a result there is no Pricing sort tab. If a price field is added later, a new sort can be wired in roughly five minutes.
- **No real Booking competitor data yet.** The competitor comparison panel is feature-flagged off (`SHOW_COMPETITOR_SECTION = False`) because the only realistic data source today is manual entry. Booking.com Demand API requires partner approval (1–4 weeks via Awin or CJ); the integration stub is in `srp_simulator/competitors.py` ready for the API key swap. Agoda has a similar partner gate. MakeMyTrip has no clean public API path.
- **Streamlit Cloud will not persist `user_defaults.json` across redeploys.** The container is ephemeral. For shared persistence across deploys we would need a small key-value store (Redis, Postgres, or even a Gist). Not in scope for v0.1.0; for local benchmarking the file-based approach is sufficient.
- **Heuristic area extraction is best-effort.** `fetch_areas_for_city` parses comma-separated address segments, drops the first (hotel name) and last 2 (city/state/pincode), filters noise tokens (`road`, `street`, etc.), and surfaces middle segments appearing in ≥ 2 hotels. It works well for Indian addresses with consistent formatting; in cities where addresses are unstructured or the index has uneven data, the dropdown may be sparse, and the user falls back to the free-text "Custom" option.
- **`hotelRating` filter applies to the autocomplete.** The Hotel-mode name search filters to `hotelRating ≥ 3` so the user cannot pick an anchor that the SRP would never show. If a user genuinely wants to pin a 2★ hotel for benchmarking, they would need to relax that filter in `hotel_lookup()` manually.
- **Composite aggregation pagination is capped at 20 × 1000 = 20 000 places.** Sufficient for the current Indian hotel index but may need raising if the index grows globally.
- **Distance decay only fires when an anchor exists.** State and Country searches deliberately have no anchor (centroid of an entire state/country is not meaningful as a proximity reference), so `λ_d` and decay floor are no-ops there. The caption surfaces this with a `λ_d —` indicator when the anchor is missing.
- **Browser refresh (Cmd+R) preserves session_state.** That means hand-edits to `user_defaults.json` between sessions only take effect after a hard close-and-reopen of the tab, not on a refresh. Adding a "Reload defaults from file" button is straightforward if iteration on the JSON becomes a frequent flow.
- **Anchor hotel pin is Recommended-only.** Other sort tabs do not pin the user-selected hotel. By design — Nearby, Popularity, and Hotel Stars are useful precisely because they do not respect intent.
- **Override star toggle is per-mode but the underlying value is shared.** `st.session_state["selected_star"]` is a single key. Toggling override on in one mode and picking 5 will persist 5 across mode switches if you toggle override on in another mode too. This is intentional (intent persists across mode flips) but worth knowing.
- **No tests yet.** `srp_simulator.scoring` and `srp_simulator.persistence` are pure functions and trivially testable; a `tests/` folder with `pytest` coverage is the next infrastructure step.

---

## Links

- README: [`README.md`](../README.md)
- Phase 1 PRD: [`docs/ranking-phase-1.md`](ranking-phase-1.md)
- Phase 1 distance extension: [`docs/ranking-phase-1-distance.md`](ranking-phase-1-distance.md)
- Elastic schema reference: [`docs/elastic-schema.md`](elastic-schema.md)
- GitHub target: `pranavoa/srp-vision` (initial push pending)
