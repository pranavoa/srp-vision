"""Configuration: environment vars, factory defaults, presets, geo constants.

All credentials come from environment variables (``ES_URL``, ``ES_INDEX``,
``ES_API_KEY``) or Streamlit secrets — never hardcoded. The app fails fast
with a clear message if no API key is configured.
"""

from __future__ import annotations

import copy
import os
from typing import Any

# ─────────────────────────── Elastic config ────────────────────

# Defaults are safe non-secrets (URL/index name); the API key MUST come
# from env or st.secrets at runtime — never hardcoded.
ES_URL_DEFAULT = "https://181f01242c7f41b1bbdaa71785ad1051.ap-south-1.aws.elastic-cloud.com:443"
ES_INDEX_DEFAULT = "search-master-hotel-details-test"


def _from_secrets(key: str) -> str | None:
    """Read a value from st.secrets if available, else None.

    Imports streamlit lazily so this module is testable without it.
    """
    try:
        import streamlit as st
        return st.secrets.get(key)  # type: ignore[no-any-return]
    except Exception:
        return None


def get_es_url() -> str:
    return os.environ.get("ES_URL") or _from_secrets("ES_URL") or ES_URL_DEFAULT


def get_es_index() -> str:
    return os.environ.get("ES_INDEX") or _from_secrets("ES_INDEX") or ES_INDEX_DEFAULT


def get_es_api_key() -> str | None:
    return os.environ.get("ES_API_KEY") or _from_secrets("ES_API_KEY")


def get_app_password() -> str | None:
    """Optional password gate — when set, app requires it before showing data."""
    return os.environ.get("APP_PASSWORD") or _from_secrets("APP_PASSWORD")


# ─────────────────────────── Search contexts ──────────────────

# Hotel uses a full 3×3 affinity matrix (selected ★ × hotel ★).
# Other contexts use a flat per-hotel-★ weight vector — there's no
# selected-★ intent for "I want hotels in Mumbai".
SEARCH_CONTEXTS: list[str] = ["Hotel", "Landmark", "Area", "City", "State", "Country"]
FLAT_CONTEXTS: set[str] = {"Landmark", "Area", "City", "State", "Country"}


def is_flat_context(ctx: str) -> bool:
    return ctx in FLAT_CONTEXTS


# ─────────────────────────── Factory defaults ──────────────────

FACTORY_AFFINITY_MATRIX: dict[int, dict[int, float]] = {
    5: {5: 1.00, 4: 0.85, 3: 0.55},
    4: {5: 0.90, 4: 1.00, 3: 0.75},
    3: {5: 0.55, 4: 0.85, 3: 1.00},
}
# For flat contexts, default to PRD's "selected = 4" row.
FACTORY_FLAT_WEIGHTS: dict[int, float] = {5: 0.90, 4: 1.00, 3: 0.75}

FACTORY_AFFINITIES: dict[str, Any] = {
    "Hotel": copy.deepcopy(FACTORY_AFFINITY_MATRIX),
    **{ctx: copy.deepcopy(FACTORY_FLAT_WEIGHTS) for ctx in FLAT_CONTEXTS},
}

FACTORY_DEFAULTS: dict[str, Any] = {
    "m": 50,                  # Bayesian prior weight
    "global_avg": 4.30,       # platform-wide rating mean
    "lambda_s": 1.0,          # star-affinity strength
    "lambda_d": 1.0,          # distance-decay strength
    "offset_km": 0.5,         # "free zone" — distance ≤ offset doesn't penalize
    "scale_km": 5.0,          # decay reaches 0.5 at offset+scale
    "aff_floor": 0.15,        # floor on the star factor
    "decay_floor": 0.15,      # floor on the distance factor
    "default_affinity": 0.45, # affinity when hotel ★ is outside 3-5 / null
    "candidate_size": 200,    # candidate set size pulled from Elastic
    "affinities": FACTORY_AFFINITIES,
}

# Numeric keys persisted in user_defaults.json (used by persistence module).
NUMERIC_KEYS = (
    "m", "global_avg", "lambda_s", "lambda_d",
    "offset_km", "scale_km", "aff_floor", "decay_floor",
    "default_affinity", "candidate_size",
)

# Path of the persisted "active defaults" file — sits next to the app.
DEFAULTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "user_defaults.json",
)


# ─────────────────────────── Geo defaults ──────────────────────

# Initial radius (km) per search type when user doesn't override.
DEFAULT_GEO_KM: dict[str, float | None] = {
    "hotel": 12.0,
    "area": 5.0,
    "city": 25.0,    # production parity
    "state": None,
    "country": None,
    "landmark": 12.0,
}


# ─────────────────────────── Landmark presets ──────────────────

LANDMARKS: list[dict[str, Any]] = [
    {"name": "Gateway of India, Mumbai",       "lat": 18.9220, "lon": 72.8347},
    {"name": "Marine Drive, Mumbai",           "lat": 18.9430, "lon": 72.8233},
    {"name": "Bandra-Worli Sea Link, Mumbai",  "lat": 19.0299, "lon": 72.8205},
    {"name": "Juhu Beach, Mumbai",             "lat": 19.0992, "lon": 72.8265},
    {"name": "India Gate, New Delhi",          "lat": 28.6129, "lon": 77.2295},
    {"name": "Red Fort, New Delhi",            "lat": 28.6562, "lon": 77.2410},
    {"name": "Qutub Minar, New Delhi",         "lat": 28.5245, "lon": 77.1855},
    {"name": "Connaught Place, New Delhi",     "lat": 28.6315, "lon": 77.2167},
    {"name": "Taj Mahal, Agra",                "lat": 27.1751, "lon": 78.0421},
    {"name": "Hawa Mahal, Jaipur",             "lat": 26.9239, "lon": 75.8267},
    {"name": "Calangute Beach, Goa",           "lat": 15.5497, "lon": 73.7551},
    {"name": "Baga Beach, Goa",                "lat": 15.5560, "lon": 73.7517},
    {"name": "Anjuna Beach, Goa",              "lat": 15.5742, "lon": 73.7406},
    {"name": "MG Road, Bangalore",             "lat": 12.9759, "lon": 77.6068},
    {"name": "Cubbon Park, Bangalore",         "lat": 12.9763, "lon": 77.5929},
    {"name": "Marina Beach, Chennai",          "lat": 13.0500, "lon": 80.2824},
    {"name": "Charminar, Hyderabad",           "lat": 17.3616, "lon": 78.4747},
    {"name": "Howrah Bridge, Kolkata",         "lat": 22.5854, "lon": 88.3468},
    {"name": "Victoria Memorial, Kolkata",     "lat": 22.5448, "lon": 88.3426},
    {"name": "Lake Pichola, Udaipur",          "lat": 24.5760, "lon": 73.6800},
]
