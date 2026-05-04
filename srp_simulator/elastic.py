"""Elasticsearch helpers — query builders, aggregations, candidate fetch.

Mirrors the production search pipeline:
1. Production-parity filters (rating ≥ 3, hasImages, provider availability)
2. Geo: bbox + geo_distance, sorted by _geo_distance ascending
3. Cached aggregations for distinct places, location geometry, area extraction
"""

from __future__ import annotations

from typing import Any

import requests
import streamlit as st

from .config import get_es_api_key, get_es_index, get_es_url


# ─────────────────────────── Low-level ─────────────────────────

def es_search(body: dict) -> dict:
    """POST a search body to the configured Elastic index.

    Raises a clear error if no API key is configured.
    """
    api_key = get_es_api_key()
    if not api_key:
        raise RuntimeError(
            "ES_API_KEY is not set. Add it to environment variables or "
            "`.streamlit/secrets.toml` (see secrets.toml.example)."
        )
    headers = {
        "Authorization": f"apiKey {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.post(
        f"{get_es_url()}/{get_es_index()}/_search",
        headers=headers, json=body, timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ─────────────────────────── Aggregations ─────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_distinct(
    field: str,
    parent_field: str | None = None,
    parent_value: str | None = None,
    size: int = 500,
) -> list[str]:
    """Distinct values for ``field``, optionally filtered by parent_field=parent_value."""
    body: dict[str, Any] = {"size": 0}
    if parent_field and parent_value:
        body["query"] = {"term": {f"{parent_field}.keyword": parent_value}}
    body["aggs"] = {"vals": {"terms": {"field": f"{field}.keyword", "size": size}}}
    resp = es_search(body)
    buckets = resp.get("aggregations", {}).get("vals", {}).get("buckets", [])
    return sorted(b["key"] for b in buckets if b.get("key"))


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_areas_for_city(
    country: str | None, state: str | None, city: str | None, sample: int = 250,
) -> list[str]:
    """Heuristically derive locality/area names from hotel addresses in a city.

    The ES schema has no structured 'locality' field, so we sample hotels in
    the chosen city, split each address on commas, drop the hotel-name (first)
    and city/state/pincode (last) segments, and surface the most common middle
    segments as candidate area names.
    """
    if not city:
        return []
    filters: list[dict] = [{"term": {"cityName.keyword": city}}]
    if state:   filters.append({"term": {"stateName.keyword":   state}})
    if country: filters.append({"term": {"countryName.keyword": country}})
    body = {
        "_source": ["address"],
        "size": sample,
        "query": {"bool": {"filter": filters}},
    }
    resp = es_search(body)
    hits = resp.get("hits", {}).get("hits", [])

    from collections import Counter
    counter: Counter[str] = Counter()
    blocked = {(city or "").lower(), (state or "").lower(), (country or "").lower(), "india"}
    NOISE_WORDS = {
        "road", "street", "marg", "lane", "near", "opp", "behind", "next", "above",
        "main", "block", "sector", "phase", "wing", "tower", "floor", "shop", "plot",
        "no.", "no", "the", "and", "of", "at", "in", "to", "by", "from", "old", "new",
    }
    for h in hits:
        addr = (h.get("_source", {}).get("address") or "").strip()
        if not addr:
            continue
        parts = [p.strip().rstrip(".") for p in addr.split(",")]
        middle = parts[1:-2] if len(parts) >= 4 else parts
        for p in middle:
            pl = p.lower()
            if not p or len(p) < 4 or len(p) > 35:
                continue
            if pl in blocked:
                continue
            if p.replace(" ", "").replace("-", "").isdigit():
                continue
            tokens = pl.split()
            if tokens and all(t in NOISE_WORDS for t in tokens):
                continue
            if not any(c.isalpha() for c in p):
                continue
            counter[p] += 1
    return [k for k, v in counter.most_common(30) if v >= 2]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_places(level: str) -> list[dict]:
    """Return all distinct places at a given level, with parent context.

    level ∈ {"country", "state", "city"}.
    """
    if level == "country":
        body = {
            "size": 0,
            "aggs": {"vals": {"terms": {"field": "countryName.keyword", "size": 500}}},
        }
        resp = es_search(body)
        buckets = resp.get("aggregations", {}).get("vals", {}).get("buckets", [])
        out = [{"label": b["key"], "country": b["key"]} for b in buckets if b.get("key")]
        return sorted(out, key=lambda p: p["label"])

    if level == "state":
        sources = [
            {"state":   {"terms": {"field": "stateName.keyword"}}},
            {"country": {"terms": {"field": "countryName.keyword"}}},
        ]
    elif level == "city":
        sources = [
            {"city":    {"terms": {"field": "cityName.keyword"}}},
            {"state":   {"terms": {"field": "stateName.keyword"}}},
            {"country": {"terms": {"field": "countryName.keyword"}}},
        ]
    else:
        return []

    out: list[dict] = []
    after_key: dict | None = None
    for _ in range(20):  # cap pagination at 20 × 1000 = 20k unique combinations
        comp: dict[str, Any] = {"size": 1000, "sources": sources}
        if after_key:
            comp["after"] = after_key
        body = {"size": 0, "aggs": {"places": {"composite": comp}}}
        resp = es_search(body)
        agg = resp.get("aggregations", {}).get("places", {}) or {}
        for b in agg.get("buckets", []):
            k = b.get("key", {})
            if level == "state" and k.get("state"):
                out.append({
                    "label":   f'{k["state"]}, {k["country"]}',
                    "country": k["country"],
                    "state":   k["state"],
                })
            elif level == "city" and k.get("city"):
                out.append({
                    "label":   f'{k["city"]}, {k["state"]}, {k["country"]}',
                    "country": k["country"],
                    "state":   k["state"],
                    "city":    k["city"],
                })
        after_key = agg.get("after_key")
        if not after_key:
            break
    return sorted(out, key=lambda p: p["label"])


# ─────────────────────────── Hotel lookup ─────────────────────

def hotel_lookup(query: str, size: int = 10) -> list[dict]:
    """Search hotels by name or hotelCode. Filtered to hotelRating ≥ 3 for SRP consistency."""
    body = {
        "_source": [
            "hotelCode", "hotelName", "cityName", "stateName",
            "countryName", "location", "hotelRating",
        ],
        "size": size,
        "query": {
            "bool": {
                "must": [{
                    "bool": {
                        "should": [
                            {"term": {"hotelCode.keyword": {"value": query, "boost": 10}}},
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["hotelName^3", "address", "cityName"],
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                }],
                "filter": [{"range": {"hotelRating": {"gte": 3}}}],
            }
        },
    }
    resp = es_search(body)
    return [h["_source"] for h in resp.get("hits", {}).get("hits", [])]


def fetch_hotel_by_code(hotel_code: str) -> dict | None:
    body = {
        "_source": True,
        "size": 1,
        "query": {"term": {"hotelCode.keyword": hotel_code}},
    }
    resp = es_search(body)
    hits = resp.get("hits", {}).get("hits", [])
    return hits[0]["_source"] if hits else None


# ─────────────────────────── Production filters ───────────────

def production_filters() -> list[dict]:
    """Production-parity hard filters applied to every SRP query.

    1. ``hotelRating ≥ 3`` — never surface 1-2★ hotels.
    2. ``hasImages = true`` — hotels without images are hidden.
    3. providerCode availability — must have vervoTech AND (CT OR TBO).
    """
    return [
        {"range": {"hotelRating": {"gte": 3}}},
        {"term":  {"hasImages": True}},
        {
            "bool": {
                "must": [
                    {"exists": {"field": "providerCode.vervoTech"}},
                    {
                        "bool": {
                            "should": [
                                {"exists": {"field": "providerCode.CT"}},
                                {"exists": {"field": "providerCode.TBO"}},
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                ]
            }
        },
    ]


# ─────────────────────────── Location geometry ────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_location_geometry(
    country: str | None, state: str | None, city: str | None,
) -> dict | None:
    """Return ``{bbox, centroid}`` for the given location level.

    Mimics production's location resolver — production stores NE/SW per location;
    here we derive equivalent geometry from hotel positions in ES via geo_bounds
    and geo_centroid aggregations.
    """
    filters: list[dict] = []
    if country: filters.append({"term": {"countryName.keyword": country}})
    if state:   filters.append({"term": {"stateName.keyword":   state}})
    if city:    filters.append({"term": {"cityName.keyword":    city}})
    if not filters:
        return None
    body = {
        "size": 0,
        "query": {"bool": {"filter": filters}},
        "aggs": {
            "bbox":     {"geo_bounds":   {"field": "location"}},
            "centroid": {"geo_centroid": {"field": "location"}},
        },
    }
    resp = es_search(body)
    aggs = resp.get("aggregations", {})
    bbox = (aggs.get("bbox", {}) or {}).get("bounds")
    centroid = (aggs.get("centroid", {}) or {}).get("location")
    if not bbox or not centroid:
        return None
    return {"bbox": bbox, "centroid": centroid}


# ─────────────────────────── Geo clauses ──────────────────────

def _geo_distance_filter(anchor: dict, radius_km: float) -> dict:
    return {
        "geo_distance": {
            "distance": f"{float(radius_km)}km",
            "location": {"lat": anchor["lat"], "lon": anchor["lon"]},
            "validation_method": "IGNORE_MALFORMED",
            "distance_type": "arc",
        }
    }


def _geo_bbox_filter(bbox: dict) -> dict:
    return {
        "geo_bounding_box": {
            "location": {
                "top_left":     bbox["top_left"],
                "bottom_right": bbox["bottom_right"],
            },
            "validation_method": "IGNORE_MALFORMED",
            "ignore_unmapped": True,
        }
    }


def _geo_distance_sort(anchor: dict) -> dict:
    return {
        "_geo_distance": {
            "location": {"lat": anchor["lat"], "lon": anchor["lon"]},
            "order": "asc",
            "unit": "km",
            "distance_type": "arc",
            "ignore_unmapped": True,
        }
    }


# ─────────────────────────── Candidate query ──────────────────

def build_candidate_query(search_type: str, params: dict, size: int = 200) -> dict:
    """Production-style candidate query: prod filters + geo bbox/distance + geo-sort."""
    filters: list[dict] = list(production_filters())
    sort_anchor: dict | None = None

    if search_type == "Hotel":
        anchor = params.get("anchor")
        if anchor and anchor.get("lat") is not None:
            filters.append(_geo_distance_filter(anchor, params["radius_km"]))
            if anchor.get("cityName"):
                filters.append({"term": {"cityName.keyword": anchor["cityName"]}})
            sort_anchor = anchor

    elif search_type == "Location":
        loc_type = params.get("loc_type", "City").lower()

        if params.get("country"):
            filters.append({"term": {"countryName.keyword": params["country"]}})
        if params.get("state"):
            filters.append({"term": {"stateName.keyword":   params["state"]}})
        if params.get("city"):
            filters.append({"term": {"cityName.keyword":    params["city"]}})
        if loc_type == "area" and params.get("area_text"):
            filters.append({"match": {"address": params["area_text"]}})

        if params.get("bbox"):
            filters.append(_geo_bbox_filter(params["bbox"]))

        anchor = params.get("anchor")
        if loc_type in ("city", "area") and anchor and anchor.get("lat") is not None:
            filters.append(_geo_distance_filter(anchor, params.get("radius_km") or 25.0))
            sort_anchor = anchor

    elif search_type == "Landmark":
        anchor = params.get("anchor")
        if anchor and anchor.get("lat") is not None:
            filters.append(_geo_distance_filter(anchor, params["radius_km"]))
            sort_anchor = anchor

    body: dict[str, Any] = {
        "_source": [
            "hotelCode", "hotelName", "address", "cityName", "stateName",
            "countryName", "hotelRating", "userAvgRating", "hotelTotalReviews",
            "location", "chainName", "brandName", "hasImages", "providerCode",
            "propertyType",
        ],
        "size": size,
        "from": 0,
        "timeout": "30s",
        "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
    }
    if sort_anchor:
        body["sort"] = [_geo_distance_sort(sort_anchor)]
    return body


# ─────────────────────────── Result shaping ───────────────────

def source_to_row(s: dict) -> dict:
    """Flatten an ES _source dict into a row used by scoring + display."""
    loc = s.get("location") if isinstance(s.get("location"), dict) else {}
    return {
        "hotelCode": s.get("hotelCode"),
        "hotelName": s.get("hotelName"),
        "cityName":  s.get("cityName"),
        "stateName": s.get("stateName"),
        "countryName": s.get("countryName"),
        "address":   s.get("address"),
        "hotelRating": int(s["hotelRating"]) if s.get("hotelRating") is not None else None,
        "userAvgRating": float(s["userAvgRating"]) if s.get("userAvgRating") is not None else None,
        "hotelTotalReviews": int(s["hotelTotalReviews"]) if s.get("hotelTotalReviews") is not None else None,
        "lat": (loc or {}).get("lat"),
        "lon": (loc or {}).get("lon"),
        "chainName": s.get("chainName"),
        "brandName": s.get("brandName"),
        "propertyType": s.get("propertyType"),
    }


def hits_to_rows(resp: dict) -> list[dict]:
    return [source_to_row(h.get("_source", {})) for h in resp.get("hits", {}).get("hits", [])]
