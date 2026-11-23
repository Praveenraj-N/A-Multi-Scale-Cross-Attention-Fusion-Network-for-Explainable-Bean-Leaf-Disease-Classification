import pytest

from backend.app.services.geo import (
    CoordinateError, angular_difference_deg, bearing_deg, bounding_box, haversine_km, parse_bbox, validate_coordinates,
)


@pytest.mark.parametrize("lat,lon", [(0, 0), (90, 180), (-90, -180), (12.5, 77.6), ("1.5", "2.5")])
def test_valid_coordinates(lat, lon):
    assert validate_coordinates(lat, lon) == (float(lat), float(lon))


@pytest.mark.parametrize(
    "lat,lon",
    [(90.01, 0), (-90.01, 0), (0, 180.01), (0, -180.01), (float("nan"), 0), (0, float("inf")), ("x", 1), (None, 1)],
)
def test_invalid_coordinates(lat, lon):
    with pytest.raises(CoordinateError):
        validate_coordinates(lat, lon)


def test_haversine_known_distances():
    assert haversine_km(0, 0, 0, 0) == 0
    # One degree of latitude is ~111.2 km
    assert haversine_km(0, 0, 1, 0) == pytest.approx(111.19, abs=0.1)
    # London -> Paris is ~344 km
    assert haversine_km(51.5074, -0.1278, 48.8566, 2.3522) == pytest.approx(343.5, abs=2)
    # Degrees of longitude shrink with latitude (naive lat/lon differencing would not show this)
    assert haversine_km(60, 0, 60, 1) == pytest.approx(55.6, abs=0.2)


def test_haversine_across_antimeridian():
    assert haversine_km(0, 179.5, 0, -179.5) == pytest.approx(111.19, abs=0.1)


def test_bearing_cardinals():
    assert bearing_deg(0, 0, 1, 0) == pytest.approx(0, abs=0.01)
    assert bearing_deg(0, 0, 0, 1) == pytest.approx(90, abs=0.01)
    assert bearing_deg(0, 0, -1, 0) == pytest.approx(180, abs=0.01)
    assert bearing_deg(0, 0, 0, -1) == pytest.approx(270, abs=0.01)


def test_angular_difference_wraps():
    assert angular_difference_deg(350, 10) == 20
    assert angular_difference_deg(0, 180) == 180


def test_bounding_box_contains_circle_points():
    box = bounding_box(10, 20, 50)
    for lat, lon in [(10.4, 20), (9.6, 20), (10, 20.45), (10, 19.55)]:
        if haversine_km(10, 20, lat, lon) <= 50:
            assert box.min_lat <= lat <= box.max_lat and box.min_lon <= lon <= box.max_lon


def test_bounding_box_antimeridian_and_pole():
    assert bounding_box(0, 179.9, 50).crosses_antimeridian
    polar = bounding_box(89.9, 10, 50)
    assert (polar.min_lon, polar.max_lon) == (-180.0, 180.0)


def test_parse_bbox():
    assert parse_bbox(None) is None
    box = parse_bbox("-1,-2,3,4")
    assert (box.min_lat, box.min_lon, box.max_lat, box.max_lon) == (-1, -2, 3, 4)
    for bad in ["1,2,3", "a,b,c,d", "5,0,1,1", "0,0,91,0"]:
        with pytest.raises(CoordinateError):
            parse_bbox(bad)
