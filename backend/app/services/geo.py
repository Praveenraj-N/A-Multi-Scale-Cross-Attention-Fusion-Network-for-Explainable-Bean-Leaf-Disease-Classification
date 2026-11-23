"""Geographic helpers: coordinate validation, great-circle distance, bearings
and bounding boxes. Pure functions with no I/O so they are easy to test."""

import math
from dataclasses import dataclass
from typing import Optional

EARTH_RADIUS_KM = 6371.0088


class CoordinateError(ValueError):
    """Latitude / longitude outside the valid range or not a finite number."""


def validate_coordinates(lat, lon) -> tuple:
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        raise CoordinateError("Latitude and longitude must be numbers.")

    if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
        raise CoordinateError("Latitude and longitude must be finite numbers.")
    if not -90.0 <= lat_f <= 90.0:
        raise CoordinateError("Latitude must be between -90 and 90 degrees.")
    if not -180.0 <= lon_f <= 180.0:
        raise CoordinateError("Longitude must be between -180 and 180 degrees.")
    return lat_f, lon_f


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing from point 1 to point 2 (0 = north, clockwise)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    y = math.sin(dlmb) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angular_difference_deg(a: float, b: float) -> float:
    """Smallest absolute difference between two compass angles (0-180)."""
    d = abs(a - b) % 360.0
    return 360.0 - d if d > 180.0 else d


@dataclass(frozen=True)
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    @property
    def crosses_antimeridian(self) -> bool:
        return self.min_lon > self.max_lon


def bounding_box(lat: float, lon: float, radius_km: float) -> BoundingBox:
    """Box that fully contains the circle of `radius_km` around the point.

    It is only a cheap pre-filter for the database; exact distances are
    always computed with `haversine_km` afterwards. Handles the poles and the
    antimeridian.
    """
    dlat = math.degrees(radius_km / EARTH_RADIUS_KM)
    min_lat, max_lat = lat - dlat, lat + dlat

    if min_lat <= -90.0 or max_lat >= 90.0:
        # The circle contains a pole: every longitude is possible
        return BoundingBox(max(min_lat, -90.0), min(max_lat, 90.0), -180.0, 180.0)

    cos_lat = math.cos(math.radians(max(abs(min_lat), abs(max_lat))))
    dlon = math.degrees(radius_km / (EARTH_RADIUS_KM * cos_lat))

    if dlon >= 180.0:
        return BoundingBox(min_lat, max_lat, -180.0, 180.0)

    min_lon, max_lon = lon - dlon, lon + dlon
    if min_lon < -180.0:
        min_lon += 360.0
    if max_lon > 180.0:
        max_lon -= 360.0
    return BoundingBox(min_lat, max_lat, min_lon, max_lon)


def parse_bbox(value: Optional[str]) -> Optional[BoundingBox]:
    """Parse 'min_lat,min_lon,max_lat,max_lon' (south,west,north,east)."""
    if value is None or value == "":
        return None
    try:
        s, w, n, e = (float(part) for part in value.split(","))
    except ValueError:
        raise CoordinateError("bbox must be 'south,west,north,east' as four numbers.")
    validate_coordinates(s, w)
    validate_coordinates(n, e)
    if s > n:
        raise CoordinateError("bbox south must not be greater than north.")
    return BoundingBox(s, n, w, e)


def round_coordinate(value: float, decimals: int) -> float:
    return round(value, decimals)
