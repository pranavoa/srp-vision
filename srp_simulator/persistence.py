"""Load and persist user-tuned defaults (m, λ, affinity weights) to JSON.

Schema is forward-compatible: legacy "lambda" and "affinity" keys auto-migrate
to the new "lambda_s" / "affinities" shape on load.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
from typing import Any

from .config import (
    DEFAULTS_FILE,
    FACTORY_AFFINITIES,
    FACTORY_DEFAULTS,
    NUMERIC_KEYS,
    SEARCH_CONTEXTS,
    is_flat_context,
)


# ─────────────────────────── Coercion helpers ──────────────────

def _coerce_matrix(raw: Any) -> dict[int, dict[int, float]] | None:
    """Coerce JSON-loaded matrix (string keys) to int-keyed dict-of-dicts."""
    if not isinstance(raw, dict):
        return None
    try:
        return {int(k): {int(kk): float(vv) for kk, vv in row.items()} for k, row in raw.items()}
    except (TypeError, ValueError):
        return None


def _coerce_flat_weights(raw: Any) -> dict[int, float] | None:
    """Coerce JSON-loaded flat weights (string keys) to int-keyed dict."""
    if not isinstance(raw, dict):
        return None
    try:
        return {int(k): float(v) for k, v in raw.items()}
    except (TypeError, ValueError):
        return None


def coerce_affinity(ctx: str, raw: Any) -> Any | None:
    """Pick the right coercer for the context's expected shape."""
    return _coerce_flat_weights(raw) if is_flat_context(ctx) else _coerce_matrix(raw)


# ─────────────────────────── Load ──────────────────────────────

def load_active_defaults() -> dict:
    """Return user-saved defaults if present, else factory defaults.

    Forward-compat: legacy "lambda" → lambda_s, legacy single "affinity" → Hotel matrix.
    """
    if not os.path.exists(DEFAULTS_FILE):
        return copy.deepcopy(FACTORY_DEFAULTS)
    try:
        with open(DEFAULTS_FILE) as f:
            user = json.load(f)
        out = copy.deepcopy(FACTORY_DEFAULTS)

        if "lambda" in user and "lambda_s" not in user:
            user["lambda_s"] = user["lambda"]
        for k in NUMERIC_KEYS:
            if k in user:
                out[k] = type(FACTORY_DEFAULTS[k])(user[k])

        if isinstance(user.get("affinities"), dict):
            out["affinities"] = copy.deepcopy(FACTORY_AFFINITIES)
            for ctx, raw in user["affinities"].items():
                if ctx not in SEARCH_CONTEXTS:
                    continue
                coerced = coerce_affinity(ctx, raw)
                if coerced is not None:
                    out["affinities"][ctx] = coerced
        elif isinstance(user.get("affinity"), dict):
            legacy = _coerce_matrix(user["affinity"])
            if legacy:
                out["affinities"] = copy.deepcopy(FACTORY_AFFINITIES)
                out["affinities"]["Hotel"] = legacy
        return out
    except Exception:
        return copy.deepcopy(FACTORY_DEFAULTS)


# ─────────────────────────── Save ──────────────────────────────

def save_active_defaults(cfg: dict) -> None:
    """Persist current values as the new defaults for the next session."""
    payload: dict[str, Any] = {
        "m": int(cfg["m"]),
        "global_avg": float(cfg["global_avg"]),
        "lambda_s": float(cfg["lambda_s"]),
        "lambda_d": float(cfg["lambda_d"]),
        "offset_km": float(cfg["offset_km"]),
        "scale_km": float(cfg["scale_km"]),
        "aff_floor": float(cfg["aff_floor"]),
        "decay_floor": float(cfg["decay_floor"]),
        "default_affinity": float(cfg["default_affinity"]),
        "candidate_size": int(cfg["candidate_size"]),
        "affinities": serialise_affinities(cfg["affinities"]),
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    with open(DEFAULTS_FILE, "w") as f:
        json.dump(payload, f, indent=2)


def serialise_affinities(affinities: dict[str, Any]) -> dict[str, Any]:
    """Stringify keys so the result is JSON-safe — flat ctxs stay 1-D, Hotel stays 2-D."""
    out: dict[str, Any] = {}
    for ctx, data in affinities.items():
        if is_flat_context(ctx):
            out[ctx] = {str(k): float(v) for k, v in data.items()}
        else:
            out[ctx] = {
                str(k): {str(kk): float(vv) for kk, vv in row.items()}
                for k, row in data.items()
            }
    return out
