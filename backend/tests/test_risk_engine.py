import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.outbreak_risk_service import (
    CaseInput, InvalidRiskInputError, TargetInput, UnsupportedDiseaseError, WeatherInput, assess_risk,
)
from backend.app.services.risk_config import load_risk_config

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
CFG = load_risk_config()
TARGET = TargetInput(plantation_id="p1", crop_type="common_bean")


def case(i="c1", disease="bean_rust", km=1.0, days=1.0, status="confirmed", conf=0.95, bearing=None):
    return CaseInput(i, disease, km, NOW - timedelta(days=days), status, conf, bearing)


def weather(**kw):
    base = dict(
        kind="current", observed_at=NOW - timedelta(minutes=30), source="test", temperature_c=22.0,
        relative_humidity_pct=92.0, rainfall_24h_mm=12.0, wind_speed_ms=6.0, wind_direction_deg=90.0,
    )
    base.update(kw)
    return WeatherInput(**base)


def run(cases, disease="bean_rust", wx=None, surveillance=None, **kw):
    return assess_risk(
        TARGET, disease, cases, wx, CFG, now=NOW,
        surveillance_observations=len(cases) if surveillance is None else surveillance, **kw,
    )


def test_no_data_at_all_is_insufficient_not_low():
    r = run([], surveillance=0)
    assert r["risk_category"] == "insufficient_data" and r["risk_score"] is None
    assert "not evidence of low risk" in r["explanation"]


def test_no_cases_but_area_surveyed_is_low_and_says_so():
    r = run([], surveillance=3)
    assert r["risk_category"] == "low" and r["risk_score"] == 0.0
    assert "not proof" in r["explanation"]


def test_other_disease_only_counts_as_surveillance():
    r = run([case(disease="angular_leaf_spot")], disease="bean_rust", surveillance=1)
    assert r["risk_category"] == "low" and r["data_quality"]["cases_excluded"]["other_disease"] == 1


def test_recent_close_case_raises_score_and_explains():
    r = run([case(km=0.5, days=0.5)], wx=weather(wind_direction_deg=None))
    assert r["risk_score"] > 25 and r["risk_category"] in {"moderate", "high", "very_high"}
    assert "1 bean rust report" in r["explanation"]
    assert r["score_name"] == "preliminary inspection-priority index"
    assert "not a probability of infection" in r["explanation"]
    assert r["rule_version"] == CFG["rule_version"] and r["recommended_action"]


def test_closer_and_more_recent_cases_score_higher():
    far_old = run([case(km=10, days=25)])["risk_score"]
    near_new = run([case(km=1, days=1)])["risk_score"]
    assert near_new > far_old


def test_cases_outside_window_are_excluded():
    r = run([case(days=45)], surveillance=1)
    assert r["data_quality"]["cases_excluded"]["outside_window"] == 1 and r["risk_category"] == "low"


def test_too_far_excluded_per_disease_distance():
    assert run([case(km=16)], surveillance=1)["data_quality"]["cases_excluded"]["too_far"] == 1  # rust limit 15 km
    als = run([case(disease="angular_leaf_spot", km=6)], disease="angular_leaf_spot", surveillance=1)  # ALS limit 5 km
    assert als["data_quality"]["cases_excluded"]["too_far"] == 1


def test_rejected_and_low_confidence_unverified_are_ignored():
    r = run([case("a", status="rejected"), case("b", status="unverified", conf=0.4)], surveillance=2)
    ex = r["data_quality"]["cases_excluded"]
    assert ex["rejected"] == 1 and ex["low_confidence"] == 1 and r["risk_category"] == "low"


def test_unverified_weighs_less_than_confirmed_and_is_disclosed():
    confirmed = run([case(status="confirmed")])
    unverified = run([case(status="unverified")])
    assert unverified["risk_score"] < confirmed["risk_score"]
    assert "unverified model detections" in unverified["explanation"]


def test_model_confidence_does_not_change_score_for_confirmed():
    assert run([case(status="confirmed", conf=0.71)])["risk_score"] == run([case(status="confirmed", conf=0.99)])["risk_score"]


def test_missing_weather_is_not_zero_risk_and_is_disclosed():
    cases = [case(km=1, days=1)]
    without = run(cases, wx=None)
    assert without["data_quality"]["weather_status"] == "missing"
    assert without["data_quality"]["environmental_assessment_complete"] is False
    assert "environmental assessment is incomplete" in without["explanation"]
    assert "favourable" not in without["explanation"]
    # Renormalising over available factors means missing weather does not drag the score toward zero
    bad = run(cases, wx=weather(relative_humidity_pct=10, temperature_c=40, wind_speed_ms=0.0))
    assert without["risk_score"] > bad["risk_score"]


def test_favourable_weather_raises_score_over_unfavourable():
    cases = [case(km=1, days=1, bearing=90.0)]
    good = run(cases, wx=weather())
    poor = run(cases, wx=weather(relative_humidity_pct=30, temperature_c=38, wind_speed_ms=0.1))
    assert good["risk_score"] > poor["risk_score"]
    assert "favourable" in good["explanation"]


def test_stale_weather_is_ignored():
    r = run([case()], wx=weather(observed_at=NOW - timedelta(hours=12)))
    assert r["data_quality"]["weather_status"] == "stale"
    assert r["data_quality"]["environmental_assessment_complete"] is False


def test_future_and_unknown_kind_weather_ignored():
    assert run([case()], wx=weather(observed_at=NOW + timedelta(hours=5)))["data_quality"]["weather_status"] == "invalid"
    assert run([case()], wx=weather(kind="rumour"))["data_quality"]["weather_status"] == "invalid"


def test_out_of_range_weather_values_dropped_not_defaulted():
    r = run([case(bearing=90.0)], wx=weather(relative_humidity_pct=250, temperature_c=float("nan")))
    assert r["data_quality"]["weather_status"] == "partial"
    factors = {f["name"]: f for f in r["factors"]}
    assert not factors["humidity"]["used"] and not factors["temperature"]["used"]


def test_wind_direction_matters_for_rust_only():
    # Case lies to the east (bearing 90). Wind FROM the east blows toward the plantation; from the west blows away.
    towards = run([case(km=2, bearing=90.0)], wx=weather(wind_direction_deg=90.0))
    away = run([case(km=2, bearing=90.0)], wx=weather(wind_direction_deg=270.0))
    assert towards["risk_score"] > away["risk_score"]
    wind = {f["name"]: f for f in towards["factors"]}["wind"]
    assert wind["used"] and wind["normalized"] > 0.9
    als = run([case(disease="angular_leaf_spot", km=1, bearing=90.0)], disease="angular_leaf_spot", wx=weather())
    assert "wind" not in {f["name"] for f in als["factors"]}


def test_wind_without_direction_is_missing_not_zero():
    r = run([case(bearing=90.0)], wx=weather(wind_direction_deg=None))
    wind = {f["name"]: f for f in r["factors"]}["wind"]
    assert not wind["used"] and "wind" in r["data_quality"]["missing_factors"]


def test_rain_matters_for_angular_leaf_spot():
    c = [case(disease="angular_leaf_spot", km=1)]
    wet = run(c, disease="angular_leaf_spot", wx=weather(rainfall_24h_mm=20))
    dry = run(c, disease="angular_leaf_spot", wx=weather(rainfall_24h_mm=0))
    assert wet["risk_score"] > dry["risk_score"]


def test_crop_susceptibility_only_used_when_configured():
    assert "susceptibility" in run([case()])["data_quality"]["missing_factors"]
    cfg = load_risk_config(overrides={"crop_susceptibility": {"common_bean": {"bean_rust": 1.0}}})
    r2 = assess_risk(TARGET, "bean_rust", [case()], None, cfg, now=NOW, surveillance_observations=1)
    assert "susceptibility" not in r2["data_quality"]["missing_factors"]


@pytest.mark.parametrize("disease", ["healthy", "powdery_mildew", ""])
def test_unsupported_disease_raises(disease):
    with pytest.raises(UnsupportedDiseaseError):
        run([case()], disease=disease)


def test_healthy_report_is_surveillance_evidence_only():
    r = run([case(disease="healthy")], surveillance=1)
    assert r["risk_category"] == "low" and r["data_quality"]["cases_considered"] == 0


def test_categories_follow_configurable_thresholds():
    cases = [case(km=0.1, days=0.1), case("c2", km=0.2, days=0.2)]
    default = run(cases, wx=weather(wind_direction_deg=None))
    strict = load_risk_config(overrides={"category_thresholds": {"moderate": 90, "high": 95, "very_high": 99}})
    r = assess_risk(TARGET, "bean_rust", cases, weather(wind_direction_deg=None), strict, now=NOW, surveillance_observations=2)
    assert r["risk_score"] == default["risk_score"] and r["risk_category"] == "low"


@pytest.mark.parametrize(
    "bad",
    [
        CaseInput("x", "bean_rust", -1.0, NOW, "confirmed"),
        CaseInput("x", "bean_rust", float("nan"), NOW, "confirmed"),
        CaseInput("x", "bean_rust", 1.0, datetime(2026, 5, 31), "confirmed"),  # naive datetime
        CaseInput("x", "bean_rust", 1.0, NOW, "maybe"),
    ],
)
def test_invalid_case_inputs_rejected(bad):
    with pytest.raises(InvalidRiskInputError):
        run([bad])


def test_invalid_window_and_now_rejected():
    with pytest.raises(InvalidRiskInputError):
        run([case()], window_days=0)
    with pytest.raises(InvalidRiskInputError):
        assess_risk(TARGET, "bean_rust", [], None, CFG, now=datetime(2026, 1, 1), surveillance_observations=0)


def test_result_is_serialisable_and_complete():
    r = run([case(bearing=90.0)], wx=weather())
    json.dumps(r)
    for key in ("plantation_id", "disease", "risk_score", "risk_category", "assessed_at", "factors", "data_quality",
                "rule_version", "explanation", "recommended_action"):
        assert key in r
