import re
from typing import Any, Optional

# Mirrors the TS shapes in RihlaExpo/src/api/searchModels.ts, so book.tsx / OfferCard.tsx
# need minimal changes when pointed at this backend instead of api.rihla.cc.
#
# One real difference: Duffel offer ids are strings (e.g. "off_0000...") not numbers,
# so `FlightOffer.id` on the TS side should become `string` when you wire this up.
#
# NOTE: Duffel offers can have multiple "slices" (outbound / return for round trips).
# This flattens all slices' segments into a single list, same flat shape the app
# already uses — good enough for one-way and round-trip display, but if you want to
# visually separate outbound/return later, group by `slice_index` instead.

_ISO_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")


def _parse_iso_duration_minutes(duration: Optional[str]) -> Optional[int]:
    if not duration:
        return None
    match = _ISO_DURATION_RE.match(duration)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


def _format_minutes(total_minutes: Optional[int]) -> Optional[str]:
    if total_minutes is None:
        return None
    h, m = divmod(total_minutes, 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _split_datetime(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Duffel's departing_at/arriving_at are local ISO datetimes without a UTC
    offset, e.g. "2026-08-01T10:00:00" — split into ("2026-08-01", "10:00")."""
    if not value:
        return None, None
    date_part, _, time_part = value.partition("T")
    time_hhmm = time_part[:5] if time_part else None
    return date_part or None, time_hhmm


def _baggage_allowance(segment: dict) -> Optional[dict]:
    """Pulls the first passenger's baggage entries off a segment. Duffel gives
    baggage per-passenger, per-segment; the app's model only has one summary
    baggage line per offer, so we take the first checked-bag entry we find."""
    for passenger in segment.get("passengers", []) or []:
        for bag in passenger.get("baggages", []) or []:
            if bag.get("type") == "checked" and bag.get("quantity", 0) > 0:
                return {"pieces": bag["quantity"], "weightPerPiece": None, "unit": None}
    return None


def normalize_segment(raw_segment: dict, segment_index: int, offer_id: str) -> dict:
    date, departure_time = _split_datetime(raw_segment.get("departing_at"))
    _, arrival_time = _split_datetime(raw_segment.get("arriving_at"))
    duration_minutes = _parse_iso_duration_minutes(raw_segment.get("duration"))

    carrier = raw_segment.get("marketing_carrier") or {}
    aircraft = raw_segment.get("aircraft") or {}
    flight_number = raw_segment.get("marketing_carrier_flight_number") or ""

    return {
        "id": raw_segment.get("id") or f"{offer_id}-{segment_index}",
        "airlineIata": carrier.get("iata_code") or "",
        "flightCode": f"{carrier.get('iata_code') or ''}{flight_number}",
        "originIata": (raw_segment.get("origin") or {}).get("iata_code") or "",
        "destinationIata": (raw_segment.get("destination") or {}).get("iata_code") or "",
        "departureTimeLocal": departure_time,
        "arrivalTimeLocal": arrival_time,
        "aircraftCode": aircraft.get("iata_code") or "",
        "aircraftModel": aircraft.get("name") or aircraft.get("iata_code") or "",
        "date": date,
        "distance": None,  # Duffel doesn't return great-circle distance on segments
        "duration": duration_minutes,
        "durationFormatted": _format_minutes(duration_minutes),
    }


def normalize_offer(raw_offer: dict) -> dict:
    segments: list[dict] = []
    seg_index = 0
    for sl in raw_offer.get("slices", []) or []:
        for raw_segment in sl.get("segments", []) or []:
            segments.append(normalize_segment(raw_segment, seg_index, raw_offer["id"]))
            seg_index += 1

    baggage = None
    for sl in raw_offer.get("slices", []) or []:
        for raw_segment in sl.get("segments", []) or []:
            baggage = _baggage_allowance(raw_segment)
            if baggage:
                break
        if baggage:
            break

    price = None
    try:
        price = float(raw_offer["total_amount"])
    except (KeyError, TypeError, ValueError):
        pass

    return {
        "id": raw_offer.get("id"),
        "currency": (raw_offer.get("total_currency") or "USD").upper(),
        "price": price,
        "pricePKR": None,  # Duffel doesn't quote a secondary currency
        "ticketingUntil": raw_offer.get("expires_at") or "",
        "baggageAllowance": baggage,
        "segments": segments,
        # Extra fields not in the old model but useful to keep around:
        "owner": (raw_offer.get("owner") or {}).get("name"),
        "passengerIds": [p.get("id") for p in raw_offer.get("passengers", []) or []],
    }


def normalize_offer_request(raw_offer_request: dict) -> dict:
    offers = [normalize_offer(o) for o in raw_offer_request.get("offers", []) or []]
    return {
        "offerRequestId": raw_offer_request.get("id"),
        "offers": offers,
    }
