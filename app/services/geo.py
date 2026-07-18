"""
UK postcode geocoding + distance calculation, powering the "local businesses
within X miles of campus" search.

Uses postcodes.io — a free, open, no-API-key UK postcode lookup service —
since CAPLink's initial market is UK higher education (see the university
onboarding flow, which verifies students against a .ac.uk-style domain).
If CAPLink expands beyond the UK, swap this module for a general geocoder
(e.g. Google Geocoding API / Mapbox) behind the same two functions; nothing
else in the codebase should need to change.
"""
import math
from dataclasses import dataclass
from typing import Optional

import httpx

POSTCODES_IO_BASE = "https://api.postcodes.io/postcodes"
EARTH_RADIUS_MILES = 3958.8
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass
class GeocodeResult:
    latitude: float
    longitude: float
    normalized_postcode: str


def geocode_postcode(postcode: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Optional[GeocodeResult]:
    """
    Looks up a UK postcode's coordinates.

    Returns None — rather than raising — for an invalid postcode, an
    unreachable API, or a timeout. Callers should treat None as "couldn't
    verify this postcode right now" and surface a clear, retryable message
    to the user instead of a 500. Location is a nice-to-have enrichment
    here, not a blocking requirement for using the rest of the platform.
    """
    if not postcode or not postcode.strip():
        return None

    cleaned = postcode.strip().upper()
    try:
        response = httpx.get(f"{POSTCODES_IO_BASE}/{cleaned}", timeout=timeout)
    except httpx.HTTPError:
        return None

    if response.status_code != 200:
        return None

    payload = response.json()
    result = payload.get("result")
    if not result or result.get("latitude") is None or result.get("longitude") is None:
        return None

    return GeocodeResult(
        latitude=result["latitude"],
        longitude=result["longitude"],
        normalized_postcode=result.get("postcode", cleaned),
    )


def haversine_distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_MILES * c
