"""Configuration for the baseline outbreak-risk rules.

EVERY number below is a provisional, literature-informed placeholder chosen so
the scoring engine is transparent and testable. None of them has been
validated against field data for this project, and none should be presented
as scientifically established thresholds. An agronomist should review them,
and they can be overridden without code changes by pointing the environment
variable OUTBREAK_RISK_CONFIG at a JSON file (deep-merged over these
defaults). Invalid configurations are rejected at load time.
"""

import copy
import json
from pathlib import Path
from typing import Optional

RULE_VERSION = "baseline-rules-0.1.0"


class RiskConfigError(ValueError):
    """The risk configuration is missing required parts or has invalid values."""


DEFAULT_RISK_CONFIG = {
    "rule_version": RULE_VERSION,
    "score_name": "preliminary inspection-priority index",

    # Default search for nearby reports when the caller does not override it
    "lookup": {"radius_km": 15.0, "window_days": 30},

    # Category = highest entry whose minimum the score reaches (score is 0-100)
    "category_thresholds": {"moderate": 25.0, "high": 50.0, "very_high": 75.0},

    # How individual reports contribute to "disease pressure"
    "case_weighting": {
        # Contribution of a report by its verification status
        "verification": {"confirmed": 1.0, "unverified": 0.5, "rejected": 0.0},
        # Unverified model detections below this softmax confidence are ignored.
        # Confidence is a detection-reliability filter, never a transmission probability.
        "min_unverified_confidence": 0.7,
        "recency_half_life_days": 7.0,
        # pressure = 1 - exp(-sum(case weights) / saturation)
        "pressure_saturation": 2.0
    },

    # With no nearby reports, "Low" requires evidence that the area is being
    # surveyed at all (any observation, including healthy ones, in the window).
    "min_surveillance_observations": 1,

    "weather": {
        # Observations older than this are treated as unavailable
        "max_age_hours": 6.0,
        # Tolerated clock skew for non-forecast observations
        "future_tolerance_hours": 1.0
    },

    # Per-crop susceptibility in [0, 1] by disease. Intentionally empty: no
    # susceptibility data is assumed. Entries added here become a factor.
    "crop_susceptibility": {},

    "diseases": {
        "angular_leaf_spot": {
            "label": "Angular leaf spot",
            # Reports farther than this are not considered for this disease
            "max_distance_km": 5.0,
            "weights": {
                "pressure": 0.40,
                "rainfall": 0.20,
                "humidity": 0.20,
                "temperature": 0.10,
                "susceptibility": 0.10
            },
            "weather_rules": {
                # Piecewise-linear 0..1 ramps; see outbreak_risk_service
                "rainfall_24h_mm": {"zero_at_or_below": 0.5, "full_at_or_above": 10.0},
                "relative_humidity_pct": {"zero_at_or_below": 60.0, "full_at_or_above": 90.0},
                "temperature_c": {"zero_below": 10.0, "full_from": 16.0, "full_to": 28.0, "zero_above": 32.0}
            }
        },
        "bean_rust": {
            "label": "Bean rust",
            "max_distance_km": 15.0,
            "weights": {
                "pressure": 0.40,
                "wind": 0.20,
                "humidity": 0.15,
                "temperature": 0.15,
                "susceptibility": 0.10
            },
            "weather_rules": {
                "wind_speed_ms": {"zero_at_or_below": 0.5, "full_at_or_above": 5.0},
                "relative_humidity_pct": {"zero_at_or_below": 60.0, "full_at_or_above": 90.0},
                "temperature_c": {"zero_below": 10.0, "full_from": 17.0, "full_to": 27.0, "zero_above": 32.0}
            }
        }
    },

    "recommendations": {
        "very_high": "Prioritise a field inspection of this plantation as soon as practical and compare plants against the reported symptoms.",
        "high": "Schedule a field inspection soon and scout the plantation edge nearest to the reported cases.",
        "moderate": "Include this plantation in the next routine scouting round and check for early symptoms.",
        "low": "Continue routine monitoring. Absence of reports does not prove absence of disease.",
        "insufficient_data": "Not enough surveillance data to judge. Scout the plantation and submit observations to improve coverage."
    }
}

_RULE_KEYS = {
    "pressure", "rainfall", "humidity", "temperature", "wind", "susceptibility"
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_risk_config(cfg: dict) -> dict:
    """Return cfg if valid, otherwise raise RiskConfigError."""
    try:
        thresholds = cfg["category_thresholds"]
        ordered = [thresholds["moderate"], thresholds["high"], thresholds["very_high"]]
        if not all(_is_number(v) for v in ordered):
            raise RiskConfigError("category_thresholds must be numbers.")
        if not (0 < ordered[0] < ordered[1] < ordered[2] <= 100):
            raise RiskConfigError("category_thresholds must satisfy 0 < moderate < high < very_high <= 100.")

        cw = cfg["case_weighting"]
        if not _is_number(cw["pressure_saturation"]) or cw["pressure_saturation"] <= 0:
            raise RiskConfigError("pressure_saturation must be a positive number.")
        if not _is_number(cw["recency_half_life_days"]) or cw["recency_half_life_days"] <= 0:
            raise RiskConfigError("recency_half_life_days must be a positive number.")
        if not 0 <= cw["min_unverified_confidence"] <= 1:
            raise RiskConfigError("min_unverified_confidence must be within 0..1.")
        for status, weight in cw["verification"].items():
            if not _is_number(weight) or not 0 <= weight <= 1:
                raise RiskConfigError(f"verification weight for '{status}' must be within 0..1.")

        lookup = cfg["lookup"]
        if not (_is_number(lookup["radius_km"]) and lookup["radius_km"] > 0):
            raise RiskConfigError("lookup.radius_km must be positive.")
        if not (_is_number(lookup["window_days"]) and lookup["window_days"] > 0):
            raise RiskConfigError("lookup.window_days must be positive.")

        if not cfg["diseases"]:
            raise RiskConfigError("At least one disease must be configured.")

        for name, rules in cfg["diseases"].items():
            if name == "healthy":
                raise RiskConfigError("'healthy' is not a disease and cannot be assessed.")
            if not _is_number(rules["max_distance_km"]) or rules["max_distance_km"] <= 0:
                raise RiskConfigError(f"{name}: max_distance_km must be positive.")
            weights = rules["weights"]
            unknown = set(weights) - _RULE_KEYS
            if unknown:
                raise RiskConfigError(f"{name}: unknown weight keys {sorted(unknown)}.")
            if any(not _is_number(w) or w < 0 for w in weights.values()):
                raise RiskConfigError(f"{name}: weights must be non-negative numbers.")
            if weights.get("pressure", 0) <= 0:
                raise RiskConfigError(f"{name}: the 'pressure' weight must be greater than 0.")
            for ramp_name, ramp in rules["weather_rules"].items():
                if "zero_below" in ramp:
                    pts = [ramp["zero_below"], ramp["full_from"], ramp["full_to"], ramp["zero_above"]]
                    if not all(_is_number(p) for p in pts) or not (pts[0] < pts[1] <= pts[2] < pts[3]):
                        raise RiskConfigError(f"{name}.{ramp_name}: trapezoid points must be increasing.")
                else:
                    lo, hi = ramp["zero_at_or_below"], ramp["full_at_or_above"]
                    if not (_is_number(lo) and _is_number(hi) and lo < hi):
                        raise RiskConfigError(f"{name}.{ramp_name}: zero_at_or_below must be < full_at_or_above.")

        for crop, by_disease in cfg["crop_susceptibility"].items():
            for disease, value in by_disease.items():
                if disease not in cfg["diseases"]:
                    raise RiskConfigError(f"crop_susceptibility.{crop}: unknown disease '{disease}'.")
                if not _is_number(value) or not 0 <= value <= 1:
                    raise RiskConfigError(f"crop_susceptibility.{crop}.{disease} must be within 0..1.")
    except KeyError as exc:
        raise RiskConfigError(f"Missing required risk configuration key: {exc}.")
    return cfg


def load_risk_config(path: Optional[str] = None, overrides: Optional[dict] = None) -> dict:
    """Defaults, optionally deep-merged with a JSON file and/or a dict, validated."""
    cfg = copy.deepcopy(DEFAULT_RISK_CONFIG)

    if path:
        file = Path(path)
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RiskConfigError(f"Cannot read risk configuration '{file}': {exc}")
        if not isinstance(data, dict):
            raise RiskConfigError("The risk configuration file must contain a JSON object.")
        cfg = _deep_merge(cfg, data)

    if overrides:
        cfg = _deep_merge(cfg, overrides)

    return validate_risk_config(cfg)
