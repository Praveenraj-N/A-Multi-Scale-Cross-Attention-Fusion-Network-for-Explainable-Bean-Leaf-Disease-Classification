import json

import pytest

from backend.app.services.risk_config import DEFAULT_RISK_CONFIG, RiskConfigError, load_risk_config


def test_defaults_are_valid():
    cfg = load_risk_config()
    assert set(cfg["diseases"]) == {"angular_leaf_spot", "bean_rust"}
    assert "healthy" not in cfg["diseases"]


def test_override_merges_deeply():
    cfg = load_risk_config(overrides={"category_thresholds": {"high": 60.0}, "diseases": {"bean_rust": {"max_distance_km": 20}}})
    assert cfg["category_thresholds"]["high"] == 60.0 and cfg["category_thresholds"]["moderate"] == 25.0
    assert cfg["diseases"]["bean_rust"]["max_distance_km"] == 20
    assert cfg["diseases"]["bean_rust"]["weights"]["pressure"] == 0.40  # untouched sibling keys survive
    assert DEFAULT_RISK_CONFIG["diseases"]["bean_rust"]["max_distance_km"] == 15.0  # defaults not mutated


def test_load_from_json_file(tmp_path):
    f = tmp_path / "risk.json"
    f.write_text(json.dumps({"lookup": {"window_days": 14}}))
    assert load_risk_config(str(f))["lookup"]["window_days"] == 14


@pytest.mark.parametrize(
    "overrides",
    [
        {"category_thresholds": {"moderate": 60.0}},  # not increasing
        {"category_thresholds": {"very_high": 120.0}},  # above 100
        {"case_weighting": {"pressure_saturation": 0}},
        {"case_weighting": {"min_unverified_confidence": 1.5}},
        {"case_weighting": {"verification": {"confirmed": 2}}},
        {"diseases": {"bean_rust": {"weights": {"pressure": 0}}}},  # pressure weight required
        {"diseases": {"bean_rust": {"weights": {"magic": 1}}}},  # unknown factor
        {"diseases": {"bean_rust": {"weights": {"wind": -1}}}},
        {"diseases": {"healthy": {"label": "x", "max_distance_km": 1, "weights": {"pressure": 1}, "weather_rules": {}}}},
        {"diseases": {"bean_rust": {"weather_rules": {"temperature_c": {"zero_below": 30, "full_from": 20, "full_to": 25, "zero_above": 35}}}}},
        {"crop_susceptibility": {"common_bean": {"unknown_disease": 0.5}}},
        {"crop_susceptibility": {"common_bean": {"bean_rust": 3}}},
    ],
)
def test_invalid_configs_are_rejected(overrides):
    with pytest.raises(RiskConfigError):
        load_risk_config(overrides=overrides)


def test_missing_file_and_bad_json(tmp_path):
    with pytest.raises(RiskConfigError):
        load_risk_config(str(tmp_path / "nope.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(RiskConfigError):
        load_risk_config(str(bad))
