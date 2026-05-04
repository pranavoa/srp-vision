"""Pure scoring logic — two formula variants, affinity lookup, sort.

Stays import-free of Streamlit so it's trivially testable.

Variants:
    "phase1"      — Bayesian rating × affinity^λ_s × decay^λ_d (deferred future state)
    "popularity"  — userAvgRating × log1p(reviews) × affinity^λ  (currently shipping in
                    ON-6566 v1.2.0; see docs/changedoc.md)

Phase 1 formula:
    final = adjusted_rating
            × max(aff_floor,   affinity[selected_★][hotel_★] ^ λ_s)
            × max(decay_floor, distance_decay(d, anchor)     ^ λ_d)

    distance_decay = exp( -max(0, d − offset_km)² / (2 × scale_km²) )

Popularity formula:
    final = max(1.0, userAvgRating)
            × log1p(max(1.0, hotelTotalReviews))
            × affinity[selected_★][hotel_★] ^ λ

Conditional behaviour (phase1):
    - distance term skipped when no anchor
    - star term skipped when context has no selected_star (flat contexts)
"""

from __future__ import annotations

import math
from typing import Any

from .config import (
    FACTORY_AFFINITY_MATRIX,
    FACTORY_FLAT_WEIGHTS,
    FLAT_CONTEXTS,
    SEARCH_CONTEXTS,
    is_flat_context,
)


# ─────────────────────────── Geo / decay ──────────────────────

def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in kilometres between two (lat, lon) points."""
    R = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dp, dl = lat2 - lat1, lon2 - lon1
    aa = math.sin(dp / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(aa))


def distance_decay(d: float, offset_km: float, scale_km: float) -> float:
    """Gaussian decay: 1.0 within offset, 0.5 at offset+scale, ~0 past 3×scale."""
    if scale_km <= 0:
        return 1.0
    over = max(0.0, d - offset_km)
    return math.exp(-(over * over) / (2.0 * scale_km * scale_km))


# ─────────────────────────── Bayesian rating ──────────────────

def adjusted_rating(n: float | None, r: float | None, m: float, global_avg: float) -> float:
    """Bayesian-shrunk rating: pulls low-review hotels toward the global mean."""
    n = 0 if n is None else n
    r = global_avg if r is None else r
    return (n * r + m * global_avg) / (n + m)


# ─────────────────────────── Affinity ──────────────────────────

def affinity_lookup(matrix: dict, selected: int, hotel: int | None, default: float) -> float:
    if hotel is None:
        return default
    return matrix.get(selected, {}).get(hotel, default)


def active_context(search_type: str, params: dict) -> str:
    """Map current search inputs → which affinity matrix/vector to apply."""
    if search_type == "Hotel":
        return "Hotel"
    if search_type == "Landmark":
        return "Landmark"
    if search_type == "Location":
        loc = params.get("loc_type") or "City"
        return loc if loc in SEARCH_CONTEXTS else "City"
    return "Hotel"


# ─────────────────────────── Per-row score ────────────────────

def score_row(row: dict, scoring: dict) -> dict:
    """Apply the full Phase 1 formula to a single hotel row."""
    adj = adjusted_rating(
        row.get("hotelTotalReviews"),
        row.get("userAvgRating"),
        scoring["m"],
        scoring["global_avg"],
    )

    # Star-affinity factor — context-shape aware.
    ctx = scoring.get("context") or "Hotel"
    weights = scoring["affinities"].get(ctx)
    hotel_star = row.get("hotelRating")
    if hotel_star is None:
        a = scoring["default_affinity"]
    elif is_flat_context(ctx):
        a = (weights or FACTORY_FLAT_WEIGHTS).get(hotel_star, scoring["default_affinity"])
    else:
        sel = scoring.get("selected_star")
        if sel is None:
            a = scoring["default_affinity"]
        else:
            a = affinity_lookup(
                weights or FACTORY_AFFINITY_MATRIX,
                sel, hotel_star, scoring["default_affinity"],
            )
    a_eff = max(scoring["aff_floor"], a ** scoring["lambda_s"])

    # Distance-decay factor — only when anchor + hotel coords both present.
    dist: float | None = None
    decay = 1.0
    decay_eff = 1.0
    anchor = scoring.get("anchor")
    if (anchor and anchor.get("lat") is not None
            and row.get("lat") is not None and row.get("lon") is not None):
        dist = haversine_km((anchor["lat"], anchor["lon"]), (row["lat"], row["lon"]))
        decay = distance_decay(dist, scoring["offset_km"], scoring["scale_km"])
        decay_eff = max(scoring["decay_floor"], decay ** scoring["lambda_d"])

    final = adj * a_eff * decay_eff
    return {
        **row,
        "adj_rating": adj,
        "affinity": a,
        "decay": decay,
        "final_score": final,
        "distance_km": dist,
    }


def score_row_popularity(row: dict, scoring: dict) -> dict:
    """Apply the production v1.2.0 formula (ON-6566) to a single hotel row.

        final = userAvgRating × log1p(hotelTotalReviews) × affinity^λ

    Mirrors the Elasticsearch ``function_score`` exactly:
      - missing ``userAvgRating``     → 1.0  (per ``MISSING_USER_RATING``)
      - missing ``hotelTotalReviews`` → 1.0  (per ``MISSING_HOTEL_TOTAL_REVIEWS``)
      - bucket weight = ``affinity[selected_★][hotel_★] ^ λ`` (no floor)
    """
    rating = row.get("userAvgRating")
    rating = 1.0 if rating is None else float(rating)

    reviews = row.get("hotelTotalReviews")
    reviews = 1.0 if reviews is None else float(reviews)
    pop = math.log1p(reviews)

    ctx = scoring.get("context") or "Hotel"
    weights = scoring["affinities"].get(ctx)
    hotel_star = row.get("hotelRating")
    if hotel_star is None:
        a = scoring["default_affinity"]
    elif is_flat_context(ctx):
        a = (weights or FACTORY_FLAT_WEIGHTS).get(hotel_star, scoring["default_affinity"])
    else:
        sel = scoring.get("selected_star")
        if sel is None:
            a = scoring["default_affinity"]
        else:
            a = affinity_lookup(
                weights or FACTORY_AFFINITY_MATRIX,
                sel, hotel_star, scoring["default_affinity"],
            )
    bucket_weight = a ** scoring["lambda_s"]

    final = rating * pop * bucket_weight

    # Distance kept for display only — never enters the popularity score.
    dist: float | None = None
    anchor = scoring.get("anchor")
    if (anchor and anchor.get("lat") is not None
            and row.get("lat") is not None and row.get("lon") is not None):
        dist = haversine_km((anchor["lat"], anchor["lon"]), (row["lat"], row["lon"]))

    return {
        **row,
        "adj_rating": rating,           # raw rating in this variant (for sort compat)
        "popularity": pop,
        "affinity": a,
        "decay": 1.0,
        "final_score": final,
        "distance_km": dist,
    }


# ─────────────────────────── Sort ──────────────────────────────

def apply_sort(rows: list[dict], sort_type: str, anchor_hotel_code: str | None = None) -> list[dict]:
    """Sort the scored candidates by the user's selected sort tab.

    For Recommended sort, the user's anchor hotel (Hotel mode) is pinned at #1.
    """
    if sort_type == "Recommended":
        ranked = sorted(rows, key=lambda x: -x["final_score"])
        if anchor_hotel_code:
            idx = next((i for i, r in enumerate(ranked) if r.get("hotelCode") == anchor_hotel_code), None)
            if idx is not None and idx != 0:
                ranked.insert(0, ranked.pop(idx))
        return ranked
    if sort_type == "Popularity":
        return sorted(rows, key=lambda x: (-x["adj_rating"], -x["final_score"]))
    if sort_type == "Nearby":
        return sorted(
            rows,
            key=lambda x: (
                x["distance_km"] if x["distance_km"] is not None else float("inf"),
                -x["final_score"],
            ),
        )
    if sort_type == "Hotel Stars":
        return sorted(rows, key=lambda x: (-(x["hotelRating"] or 0), -x["adj_rating"]))
    return rows
