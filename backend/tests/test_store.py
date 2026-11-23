import sqlite3
from datetime import timedelta

import pytest

from backend.app.services.geo import BoundingBox
from backend.app.services.outbreak_store import DuplicateObservationError, NotFoundError, OutbreakStore, from_db_ts, to_db_ts
from backend.tests.conftest import NOW


def plantation(store, lat, lon, crop="common_bean", **kw):
    return store.add_plantation(crop_type=crop, latitude=lat, longitude=lon, **kw)


def observation(store, lat=12.9, lon=77.6, disease="bean_rust", minutes_ago=60, **kw):
    kw.setdefault("crop_type", "common_bean")
    kw.setdefault("detection_source", "manual_report")
    kw.setdefault("location_source", "manual_entry")
    return store.add_observation(disease=disease, latitude=lat, longitude=lon, observed_at=NOW - timedelta(minutes=minutes_ago), **kw)


def test_migrate_is_idempotent_and_keeps_data(store):
    plantation(store, 1, 1)
    assert store.migrate() == 1
    assert store.count_plantations() == 1


def test_plantations_within_radius_uses_true_distance(store):
    centre = (12.9, 77.6)
    near = plantation(store, 12.91, 77.6)       # ~1.1 km north
    mid = plantation(store, 12.9, 77.65)        # ~5.4 km east
    far = plantation(store, 13.5, 77.6)         # ~67 km
    ids = [p["id"] for p in store.plantations_within(*centre, radius_km=10)]
    assert ids == [near["id"], mid["id"]] and far["id"] not in ids


def test_radius_boundary_is_inclusive_and_exact(store):
    p = plantation(store, 0.0, 0.0)
    # 1 degree of latitude on this sphere is 111.195 km
    assert [r["id"] for r in store.plantations_within(1.0, 0.0, radius_km=111.2)] == [p["id"]]
    assert store.plantations_within(1.0, 0.0, radius_km=111.1) == []


def test_empty_spatial_query_returns_empty_list(store):
    assert store.plantations_within(0, 0, 5) == []
    assert store.observations_within(0, 0, 5) == []


def test_nearby_filters_by_crop(store):
    plantation(store, 12.9, 77.6, crop="common_bean")
    maize = plantation(store, 12.9, 77.601, crop="maize")
    rows = store.plantations_within(12.9, 77.6, 5, crop_type="maize")
    assert [r["id"] for r in rows] == [maize["id"]]


def test_nearby_across_antimeridian(store):
    p = plantation(store, 0.0, -179.95)
    assert [r["id"] for r in store.plantations_within(0.0, 179.95, 20)] == [p["id"]]


def test_observations_within_filters_disease_and_time_and_has_bearing(store):
    east = observation(store, 12.9, 77.62, "bean_rust", minutes_ago=30)
    observation(store, 12.9, 77.62, "angular_leaf_spot", minutes_ago=30)
    observation(store, 12.9, 77.621, "bean_rust", minutes_ago=60 * 24 * 40)
    rows = store.observations_within(12.9, 77.6, 10, since=NOW - timedelta(days=30), diseases=["bean_rust"])
    assert [r["id"] for r in rows] == [east["id"]]
    assert rows[0]["bearing_deg"] == pytest.approx(90, abs=1)


def test_query_observations_filters_and_pagination(store):
    for i in range(5):
        observation(store, 12.9 + i * 0.1, 77.6, "bean_rust", minutes_ago=i * 60 + 1)
    observation(store, 1.0, 1.0, "healthy", minutes_ago=5, verification_status="confirmed")
    rows, total = store.query_observations(diseases=["bean_rust"], limit=2, offset=0)
    assert total == 5 and len(rows) == 2 and rows[0]["observed_at"] >= rows[1]["observed_at"]
    rows, total = store.query_observations(bbox=BoundingBox(12.85, 13.05, 77.0, 78.0))
    assert total == 2
    _, total = store.query_observations(verification=["confirmed"])
    assert total == 1
    _, total = store.query_observations(date_from=NOW - timedelta(minutes=70), date_to=NOW)
    assert total == 3


def test_duplicate_detection_by_distance_and_time(store):
    first = observation(store, 12.9, 77.6, minutes_ago=30)
    with pytest.raises(DuplicateObservationError) as exc:
        observation(store, 12.90005, 77.60005, minutes_ago=28)  # ~7 m and 2 min away
    assert exc.value.existing_id == first["id"]
    observation(store, 12.9, 77.6, minutes_ago=5)               # same place, 25 minutes later: allowed
    observation(store, 12.91, 77.6, minutes_ago=30)             # 1 km away: allowed
    observation(store, 12.9, 77.6, "angular_leaf_spot", minutes_ago=30)  # different disease: allowed


def test_client_id_makes_submission_idempotent(store):
    a = observation(store, client_id="abcdefgh-1")
    b = observation(store, client_id="abcdefgh-1")
    assert a["id"] == b["id"] and store.query_observations()[1] == 1


def test_unknown_plantation_and_missing_records(store):
    with pytest.raises(NotFoundError):
        observation(store, plantation_id="nope")
    with pytest.raises(NotFoundError):
        store.get_observation("nope")
    with pytest.raises(NotFoundError):
        store.get_plantation("nope")


def test_database_constraints_reject_bad_rows(store):
    with pytest.raises(sqlite3.IntegrityError):
        observation(store, confidence=1.5)
    with pytest.raises(sqlite3.IntegrityError):
        store.add_plantation(crop_type="common_bean", latitude=95, longitude=0)


def test_set_verification(store):
    o = observation(store)
    assert o["verified_at"] is None
    updated = store.set_verification(o["id"], "confirmed")
    assert updated["verification_status"] == "confirmed" and updated["verified_at"]


def test_history_buckets(store):
    observation(store, minutes_ago=10)
    observation(store, 13.5, 77.6, minutes_ago=15, verification_status="confirmed")
    observation(store, 14.5, 77.6, "angular_leaf_spot", minutes_ago=60 * 24 * 3)
    day = store.history(date_from=NOW - timedelta(days=7), date_to=NOW, bucket="day")
    assert sum(r["count"] for r in day) == 3
    week = store.history(date_from=NOW - timedelta(days=7), date_to=NOW, bucket="week")
    assert sum(r["count"] for r in week) == 3


def test_timestamp_round_trip():
    assert from_db_ts(to_db_ts(NOW)) == NOW
    with pytest.raises(ValueError):
        to_db_ts(NOW.replace(tzinfo=None))


def test_unreachable_database_raises_sqlite_error(tmp_path):
    bad = OutbreakStore(str(tmp_path / "ok.db"))
    bad.db_path = str(tmp_path / "missing_dir" / "x.db")
    with pytest.raises(sqlite3.Error):
        bad.ping()
