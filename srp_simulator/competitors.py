"""Competitor SRP comparison — pluggable data source.

For now there's a single ``ManualBookingProvider`` that takes user-entered
rows. When the Booking.com Demand API partnership is approved, drop in a
``DemandAPIBookingProvider`` with the same interface and the rest of the
app stays the same.

Booking.com user-rating scale is 0–10 (vs. our 0–5); we display them
side-by-side without coercion so the difference is visible.
"""

from __future__ import annotations

from typing import Any, Protocol


# A single competitor result row. Loose schema — we accept None for
# anything the user didn't capture.
COMPETITOR_FIELDS: list[str] = [
    "hotelName",
    "hotelRating",        # stars, 1-5
    "userAvgRating",      # competitor's own scale (Booking: 0-10)
    "hotelTotalReviews",
    "price",
    "url",
]

EMPTY_ROW: dict[str, Any] = {f: None for f in COMPETITOR_FIELDS}
EMPTY_ROW["hotelName"] = ""
EMPTY_ROW["url"] = ""


def empty_template(rows: int = 20) -> list[dict[str, Any]]:
    """A fresh template the user can fill in."""
    return [dict(EMPTY_ROW) for _ in range(rows)]


class CompetitorProvider(Protocol):
    """Future interface for an automated competitor data source.

    A real implementation (e.g. Booking Demand API) would translate
    ``params`` (search type + anchor + selected ★) into the platform's
    query, fetch results, and return rows in the shape above.
    """

    name: str

    def fetch(self, search_type: str, params: dict, size: int = 20) -> list[dict[str, Any]]:
        ...


class BookingDemandAPIStub:
    """Stub for the future Booking.com Demand API integration.

    Currently raises NotImplementedError — once we have partner credentials
    this becomes the real implementation. The UI doesn't depend on this class
    today; it's here as a placeholder so the swap is well-scoped later.
    """

    name = "Booking.com (Demand API)"

    def fetch(self, search_type: str, params: dict, size: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Awaiting Booking.com Demand API partner approval. "
            "Apply at https://www.awin.com/us/advertisers/partner/booking.com"
        )


def normalise_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop empty rows; coerce numeric columns; assign rank."""
    out: list[dict[str, Any]] = []
    for row in rows:
        name = (row.get("hotelName") or "").strip()
        if not name:
            continue
        clean: dict[str, Any] = {"hotelName": name}
        for key in ("hotelRating", "hotelTotalReviews"):
            v = row.get(key)
            try:
                clean[key] = int(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                clean[key] = None
        for key in ("userAvgRating", "price"):
            v = row.get(key)
            try:
                clean[key] = float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                clean[key] = None
        clean["url"] = (row.get("url") or "").strip() or None
        out.append(clean)
    for i, r in enumerate(out, start=1):
        r["rank"] = i
    return out
