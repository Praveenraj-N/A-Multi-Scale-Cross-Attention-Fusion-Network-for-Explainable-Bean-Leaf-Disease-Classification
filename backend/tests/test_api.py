from datetime import timedelta
from unittest import mock

import pytest

from backend.tests.conftest import ADMIN, NOW, obs_payload


def post_obs(client, headers=ADMIN, **kw):
    return client.post("/api/observations", json=obs_payload(**kw), headers=headers)


def make_plantation(client, lat=12.9, lon=77.6, **kw):
    body = {"crop_type": "common_bean", "latitude": lat, "longitude": lon, "name": "Hillside Farm", "owner_ref": "farmer-77"}
    body.update(kw)
    r = client.post("/api/plantations", json=body, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()


# ----------------------------------------------------------- access / auth

def test_access_reports_role_and_config(client):
    r = client.get("/api/access")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "public" and body["writes_enabled"] is True
    assert body["risk"]["rule_version"] and set(body["risk"]["thresholds"]) == {"moderate", "high", "very_high"}
    assert client.get("/api/access", headers=ADMIN).json()["role"] == "admin"


def test_wrong_key_is_rejected_everywhere(client):
    assert client.get("/api/access", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/observations", headers={"X-API-Key": "wrong"}).status_code == 401


def test_writes_require_key(client):
    assert post_obs(client, headers={}).status_code == 401
    assert client.post("/api/plantations", json={"latitude": 1, "longitude": 1}).status_code == 401
    assert client.post("/api/outbreak-risk/snapshot").status_code == 401
    assert client.post("/api/observations/x/verification", json={"verification_status": "confirmed"}).status_code == 401


def test_writes_report_misconfiguration_when_no_key_is_set(client, settings):
    settings.admin_api_key = None
    r = client.post("/api/observations", json=obs_payload(), headers=ADMIN)
    assert r.status_code == 503 and "OUTBREAK_ADMIN_API_KEY" in r.json()["detail"]
    assert client.get("/api/access").json()["writes_enabled"] is False


# ------------------------------------------------------ observation create

def test_create_valid_observation(client):
    r = post_obs(client, notes="  seen on lower <b>leaves</b>  ")
    assert r.status_code == 201
    body = r.json()
    assert body["disease"] == "bean_rust" and body["verification_status"] == "unverified"
    assert body["latitude"] == 12.9
    assert body["notes"] == "seen on lower bleaves/b"  # angle brackets stripped, whitespace trimmed
    assert client.get(f"/api/observations/{body['id']}", headers=ADMIN).json()["id"] == body["id"]


@pytest.mark.parametrize(
    "override",
    [
        {"disease": "powdery_mildew"},
        {"disease": ""},
        {"confidence": 1.2},
        {"confidence": -0.1},
        {"confidence": None},  # required for model detections
        {"latitude": 91},
        {"longitude": -181},
        {"latitude": None},     # coordinates must come as a pair
        {"observed_at": "2099-01-01T00:00:00Z"},
        {"observed_at": "2026-05-31T10:00:00"},  # no timezone
        {"verification_status": "rejected"},
        {"crop_type": "bad crop!!"},
        {"notes": "x" * 1001},
        {"location_source": "telepathy"},
        {"client_id": "short"},
        {"unexpected_field": 1},
    ],
)
def test_invalid_observation_payloads_rejected(client, override):
    assert post_obs(client, **override).status_code == 422


def test_missing_coordinates_without_plantation_is_rejected(client):
    body = obs_payload()
    del body["latitude"], body["longitude"]
    r = client.post("/api/observations", json=body, headers=ADMIN)
    assert r.status_code == 422 and "coordinates" in r.json()["detail"].lower()


def test_location_from_registered_plantation(client):
    p = make_plantation(client, 13.0, 77.7)
    body = obs_payload(location_source="registered_plantation", plantation_id=p["id"])
    del body["latitude"], body["longitude"]
    r = client.post("/api/observations", json=body, headers=ADMIN)
    assert r.status_code == 201 and (r.json()["latitude"], r.json()["longitude"]) == (13.0, 77.7)


def test_registered_plantation_source_needs_plantation_and_it_must_exist(client):
    assert post_obs(client, location_source="registered_plantation").status_code == 422
    assert post_obs(client, plantation_id="doesnotexist").status_code == 404


def test_manual_report_without_confidence_is_allowed(client):
    assert post_obs(client, detection_source="manual_report", confidence=None).status_code == 201


def test_duplicate_submission_conflicts_and_client_id_is_idempotent(client):
    assert post_obs(client).status_code == 201
    dup = post_obs(client)
    assert dup.status_code == 409 and dup.json()["existing_observation_id"]

    first = post_obs(client, client_id="idem-key-0001", latitude=14.0)
    again = post_obs(client, client_id="idem-key-0001", latitude=14.0)
    assert first.status_code == 201 and again.status_code == 200 and first.json()["id"] == again.json()["id"]


def test_verification_status_handling(client):
    oid = post_obs(client).json()["id"]
    r = client.post(f"/api/observations/{oid}/verification", json={"verification_status": "confirmed"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["verification_status"] == "confirmed"
    assert client.post(f"/api/observations/{oid}/verification", json={"verification_status": "bogus"}, headers=ADMIN).status_code == 422
    assert client.post("/api/observations/missing/verification", json={"verification_status": "confirmed"}, headers=ADMIN).status_code == 404


# ------------------------------------------------------- reads / privacy

def test_public_view_rounds_coordinates_and_hides_private_fields(client):
    p = make_plantation(client, 12.91234, 77.65678)
    post_obs(client, latitude=12.91234, longitude=77.65678, plantation_id=p["id"], notes="owner's phone 555-0100")

    public_obs = client.get("/api/observations").json()["items"][0]
    assert (public_obs["latitude"], public_obs["longitude"]) == (12.91, 77.66)
    assert public_obs["notes"] is None and public_obs["plantation_id"] is None and public_obs["coordinates_precise"] is False
    assert public_obs["plantation_alias"].startswith("PL-")

    admin_obs = client.get("/api/observations", headers=ADMIN).json()["items"][0]
    assert admin_obs["latitude"] == 12.91234 and admin_obs["notes"] and admin_obs["plantation_id"] == p["id"]

    public_p = client.get(f"/api/plantations/{p['id']}").json()
    assert public_p["name"] is None and public_p["owner_ref"] is None and public_p["latitude"] == 12.91
    admin_p = client.get(f"/api/plantations/{p['id']}", headers=ADMIN).json()
    assert admin_p["name"] == "Hillside Farm" and admin_p["owner_ref"] == "farmer-77" and admin_p["latitude"] == 12.91234
    assert "farmer-77" not in client.get("/api/map-data").text
    assert "Hillside" not in client.get("/api/map-data").text


def test_list_filters_and_pagination(client):
    post_obs(client, latitude=12.0)
    post_obs(client, latitude=13.0, disease="angular_leaf_spot")
    post_obs(client, latitude=14.0, disease="healthy", confidence=0.99, verification_status="confirmed")
    assert client.get("/api/observations", params={"disease": "bean_rust"}).json()["total"] == 1
    assert client.get("/api/observations", params={"disease": ["bean_rust", "healthy"]}).json()["total"] == 2
    assert client.get("/api/observations", params={"verification_status": "confirmed"}).json()["total"] == 1
    assert client.get("/api/observations", params={"bbox": "12.5,77,13.5,78"}).json()["total"] == 1
    page = client.get("/api/observations", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    day = (NOW - timedelta(days=1)).date().isoformat()
    assert client.get("/api/observations", params={"date_from": f"{day}T00:00:00Z", "date_to": f"{day}T23:59:59Z"}).json()["total"] == 3
    assert client.get("/api/observations", params={"date_from": "2020-01-01T00:00:00Z", "date_to": "2020-01-02T00:00:00Z"}).json()["total"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"disease": "nope"}, {"verification_status": "maybe"}, {"bbox": "bad"}, {"limit": 0}, {"offset": -1},
        {"date_from": "2026-06-02T00:00:00Z", "date_to": "2026-06-01T00:00:00Z"}, {"crop_type": "!!"},
    ],
)
def test_invalid_list_parameters(client, params):
    assert client.get("/api/observations", params=params).status_code == 422


def test_missing_records_are_404(client):
    assert client.get("/api/observations/nope").status_code == 404
    assert client.get("/api/plantations/nope").status_code == 404
    assert client.get("/api/outbreak-risk", params={"plantation_id": "nope"}).status_code == 404


# ----------------------------------------------------- plantation + nearby

def test_plantation_validation(client):
    bad = [
        {"latitude": 95, "longitude": 0}, {"latitude": 0, "longitude": 200}, {"latitude": 0}, {"latitude": 0, "longitude": 0, "crop_type": "x"},
        {"latitude": 0, "longitude": 0, "planting_date": "2999-01-01"},
        {"latitude": 0, "longitude": 0, "boundary": {"type": "Point", "coordinates": [0, 0]}},
        {"latitude": 0, "longitude": 0, "boundary": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}},
    ]
    for body in bad:
        assert client.post("/api/plantations", json=body, headers=ADMIN).status_code == 422, body
    ring = [[77.0, 12.0], [77.1, 12.0], [77.1, 12.1], [77.0, 12.0]]
    ok = client.post("/api/plantations", json={"latitude": 12.0, "longitude": 77.0, "boundary": {"type": "Polygon", "coordinates": [ring]}}, headers=ADMIN)
    assert ok.status_code == 201 and ok.json()["boundary"]["type"] == "Polygon"


def test_nearby_plantations(client):
    near = make_plantation(client, 12.91, 77.6)
    make_plantation(client, 14.0, 77.6)
    r = client.get("/api/plantations/nearby", params={"lat": 12.9, "lon": 77.6, "radius_km": 5})
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["id"] for i in items] == [near["id"]] and items[0]["distance_km"] == pytest.approx(1.1, abs=0.1)
    assert "not a model of disease spread" in r.json()["search_area"]["note"]


def test_nearby_empty_and_invalid(client):
    r = client.get("/api/plantations/nearby", params={"lat": 0, "lon": 0})
    assert r.status_code == 200 and r.json()["items"] == []
    for params in [{"lat": 91, "lon": 0}, {"lat": 0, "lon": 181}, {"lat": 0, "lon": 0, "radius_km": 0},
                   {"lat": 0, "lon": 0, "radius_km": 1000}, {"lat": 0}, {"lat": "nan", "lon": 0}]:
        assert client.get("/api/plantations/nearby", params=params).status_code == 422, params


# ------------------------------------------------------------------- risk

def seed_cluster(client):
    p = make_plantation(client, 12.9, 77.6)
    post_obs(client, latitude=12.905, longitude=77.61, verification_status="confirmed")
    return p


def test_risk_for_plantation_with_weather(client, provider):
    p = seed_cluster(client)
    r = client.get("/api/outbreak-risk", params={"plantation_id": p["id"]})
    assert r.status_code == 200
    body = r.json()
    rust = next(a for a in body["assessments"] if a["disease"] == "bean_rust")
    assert rust["risk_category"] in {"moderate", "high", "very_high"} and rust["risk_score"] > 0
    assert rust["data_quality"]["weather_status"] == "available"
    assert body["weather"]["status"] == "ok" and body["weather"]["kind"] == "current"
    assert "not a validated infection probability" in body["disclaimer"].lower()
    als = next(a for a in body["assessments"] if a["disease"] == "angular_leaf_spot")
    assert als["risk_category"] == "low"  # surveyed area, no ALS reports
    assert body["target"]["name"] is None  # public view


def test_risk_survives_weather_failure(client, provider):
    p = seed_cluster(client)
    provider.error = ("timeout", "The weather provider timed out.")
    r = client.get("/api/outbreak-risk", params={"plantation_id": p["id"]})
    assert r.status_code == 200
    body = r.json()
    assert body["weather"]["status"] == "timeout" and body["weather"]["values"] is None
    rust = next(a for a in body["assessments"] if a["disease"] == "bean_rust")
    assert rust["data_quality"]["environmental_assessment_complete"] is False
    assert "incomplete" in rust["explanation"]


def test_risk_with_stale_weather(client, provider):
    p = seed_cluster(client)
    provider.age = timedelta(hours=30)
    rust = next(a for a in client.get("/api/outbreak-risk", params={"plantation_id": p["id"]}).json()["assessments"] if a["disease"] == "bean_rust")
    assert rust["data_quality"]["weather_status"] == "stale"


def test_risk_without_weather_provider(client, service):
    p = seed_cluster(client)
    service.weather.provider = None
    body = client.get("/api/outbreak-risk", params={"plantation_id": p["id"]}).json()
    assert body["weather"]["status"] == "not_configured"
    assert client.get("/api/outbreak-risk", params={"plantation_id": p["id"], "include_weather": "false"}).json()["weather"]["status"] == "not_requested"


def test_risk_insufficient_data_for_unsurveyed_point(client):
    r = client.get("/api/outbreak-risk", params={"lat": 40, "lon": 40, "crop_type": "common_bean"}).json()
    assert {a["risk_category"] for a in r["assessments"]} == {"insufficient_data"}
    assert all(a["risk_score"] is None for a in r["assessments"])
    assert r["overall"]["category"] == "insufficient_data"


def test_risk_validation_errors(client):
    p = seed_cluster(client)
    for params in [
        {}, {"lat": 1}, {"lat": 95, "lon": 0}, {"plantation_id": p["id"], "lat": 1, "lon": 1},
        {"plantation_id": p["id"], "disease": "healthy"}, {"plantation_id": p["id"], "disease": "powdery_mildew"},
        {"plantation_id": p["id"], "radius_km": -1}, {"plantation_id": p["id"], "window_days": 0},
    ]:
        assert client.get("/api/outbreak-risk", params=params).status_code == 422, params


def test_persisting_assessments_requires_admin_and_feeds_history(client):
    p = seed_cluster(client)
    assert client.get("/api/outbreak-risk", params={"plantation_id": p["id"], "persist": "true"}).status_code == 401
    r = client.get("/api/outbreak-risk", params={"plantation_id": p["id"], "persist": "true"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["persisted"] is True
    hist = client.get("/api/outbreak-history", params={"date_from": "2026-05-01T00:00:00Z", "date_to": "2026-06-02T00:00:00Z"}).json()
    assert hist["priority_series"] and hist["priority_series"][0]["plantations_assessed"] == 1


def test_snapshot_endpoint(client):
    seed_cluster(client)
    r = client.post("/api/outbreak-risk/snapshot", headers=ADMIN)
    assert r.status_code == 200 and r.json()["assessed"] == 1


def test_risk_service_failure_returns_503_without_leaking_details(client, store):
    p = seed_cluster(client)
    import sqlite3
    with mock.patch.object(type(store), "observations_within", side_effect=sqlite3.OperationalError("disk I/O error at /secret/path.db")):
        r = client.get("/api/outbreak-risk", params={"plantation_id": p["id"]})
    assert r.status_code == 503 and "secret" not in r.text


# ---------------------------------------------------------------- history

def test_history_series_and_notes(client):
    post_obs(client)  # 1 day ago
    post_obs(client, latitude=13.5, verification_status="confirmed")
    post_obs(client, latitude=14.5, disease="angular_leaf_spot", observed_at=(NOW - timedelta(days=3)).isoformat().replace("+00:00", "Z"))
    h = client.get("/api/outbreak-history", params={"date_from": "2026-05-25T00:00:00Z", "date_to": "2026-06-01T12:00:00Z"}).json()
    assert h["total"] == 3 and h["by_disease"] == {"bean_rust": 2, "angular_leaf_spot": 1}
    assert h["by_verification"] == {"unverified": 2, "confirmed": 1}
    assert len(h["series"]) == 8 and sum(p["total"] for p in h["series"]) == 3  # empty days are explicit zeros
    assert "does not by itself show" in h["interpretation_note"]
    assert h["priority_series"] == []  # nothing stored, nothing invented
    wk = client.get("/api/outbreak-history", params={"date_from": "2026-05-25T00:00:00Z", "date_to": "2026-06-01T12:00:00Z", "bucket": "week"}).json()
    assert sum(p["total"] for p in wk["series"]) == 3


def test_history_validation(client):
    assert client.get("/api/outbreak-history", params={"bucket": "year"}).status_code == 422
    assert client.get("/api/outbreak-history", params={"date_from": "2020-01-01T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"}).status_code == 422
    assert client.get("/api/outbreak-history", params={"date_from": "2026-02-01T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"}).status_code == 422
    empty = client.get("/api/outbreak-history").json()
    assert empty["total"] == 0 and empty["by_disease"] == {}


# --------------------------------------------------------------- map data

def test_map_data_contents_and_summary(client):
    seed_cluster(client)
    make_plantation(client, 40.0, 40.0)
    post_obs(client, latitude=12.5, disease="healthy", confidence=0.98)
    d = client.get("/api/map-data").json()
    assert len(d["observations"]) == 2 and len(d["plantations"]) == 2
    s = d["summary"]
    assert s["reported_detections"] == 1 and s["plantations_registered"] == 2 and s["plantations_assessed"] == 2
    assert s["plantations_requiring_inspection"] == 1 and s["recent_detections_7d"] == 1
    cats = {p["risk"]["overall"]["category"] for p in d["plantations"]}
    assert "insufficient_data" in cats and d["weather"]["status"] in {"ok", "partial"}
    assert "not verified infection" in d["legend_note"]


def test_map_data_filters(client):
    seed_cluster(client)
    post_obs(client, latitude=20.0, disease="angular_leaf_spot")
    assert len(client.get("/api/map-data", params={"disease": "angular_leaf_spot"}).json()["observations"]) == 1
    assert len(client.get("/api/map-data", params={"verification_status": "confirmed"}).json()["observations"]) == 1
    only_far = client.get("/api/map-data", params={"bbox": "19,76,21,78"}).json()
    assert len(only_far["observations"]) == 1 and only_far["plantations"] == []
    hi = client.get("/api/map-data", params={"risk_category": ["high", "very_high"]}).json()
    assert all(p["risk"]["overall"]["category"] in {"high", "very_high"} for p in hi["plantations"])
    assert client.get("/api/map-data", params={"risk_category": "extreme"}).status_code == 422


def test_map_data_empty_database(client):
    d = client.get("/api/map-data").json()
    assert d["observations"] == [] and d["plantations"] == []
    assert d["summary"]["reported_detections"] == 0 and d["summary"]["plantations_requiring_inspection"] is None


def test_map_data_without_risk_or_weather_failure(client, provider):
    seed_cluster(client)
    no_risk = client.get("/api/map-data", params={"include_risk": "false"}).json()
    assert "risk" not in no_risk["plantations"][0] and no_risk["summary"]["high_priority_locations"] is None
    provider.error = ("network_error", "Could not reach the weather provider.")
    d = client.get("/api/map-data").json()
    assert d["weather"]["status"] == "unavailable" and d["plantations"][0]["risk"]["overall"]["category"] != "insufficient_data"


def test_map_data_weather_cells_are_budgeted(client, provider, settings):
    settings.max_weather_cells_per_request = 2
    for i in range(5):
        make_plantation(client, 10.0 + i, 50.0)  # five distinct cells
    client.get("/api/map-data")
    assert provider.calls == 2


def test_map_data_truncation_flag(client):
    for i in range(3):
        post_obs(client, latitude=10 + i)
    d = client.get("/api/map-data", params={"observation_limit": 1}).json()
    assert len(d["observations"]) == 1 and d["truncated"]["observations"] is True


def test_system_database_failure_returns_503(client, store):
    with mock.patch.object(type(store), "query_observations", side_effect=__import__("sqlite3").OperationalError("boom")):
        assert client.get("/api/observations").status_code == 503
        assert client.get("/api/map-data").status_code == 503
