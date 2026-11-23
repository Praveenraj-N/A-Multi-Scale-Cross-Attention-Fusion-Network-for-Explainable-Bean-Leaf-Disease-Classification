"""Transparent baseline engine for a preliminary inspection-priority index.

What this is: a weighted, rule-based index that ranks how much inspection
attention a plantation may deserve given nearby reports and (optionally)
current environmental conditions.

What this is NOT: a probability of infection, a validated epidemiological
model, or proof of transmission. Proximity is one factor among several, and
model confidence is used only to filter unreliable unverified detections.

The engine is pure: it receives already-fetched inputs and returns a result.
It does no database or network I/O, so a trained model can later replace it
behind the same `assess_risk` signature.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from backend.app.services.geo import angular_difference_deg

CATEGORY_LOW = "low"
CATEGORY_MODERATE = "moderate"
CATEGORY_HIGH = "high"
CATEGORY_VERY_HIGH = "very_high"
CATEGORY_INSUFFICIENT = "insufficient_data"

CATEGORY_LABELS = {
    CATEGORY_LOW: "Low",
    CATEGORY_MODERATE: "Moderate",
    CATEGORY_HIGH: "High",
    CATEGORY_VERY_HIGH: "Very High",
    CATEGORY_INSUFFICIENT: "Insufficient Data",
}


class UnsupportedDiseaseError(ValueError):
    """The disease is not configured for risk assessment (e.g. 'healthy')."""


class InvalidRiskInputError(ValueError):
    """An input to the risk engine is malformed."""


@dataclass
class CaseInput:
    observation_id: str
    disease: str
    distance_km: float
    observed_at: datetime  # timezone-aware
    verification_status: str  # confirmed | unverified | rejected
    confidence: Optional[float] = None
    # Compass bearing from the target plantation towards this case
    bearing_to_case_deg: Optional[float] = None


@dataclass
class WeatherInput:
    kind: str  # current | historical | forecast
    observed_at: datetime  # timezone-aware time the values are valid for
    source: str = "unknown"
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    rainfall_24h_mm: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    # Meteorological convention: direction the wind blows FROM
    wind_direction_deg: Optional[float] = None


@dataclass
class TargetInput:
    plantation_id: Optional[str]
    crop_type: Optional[str] = None


# ---------------------------------------------------------------- helpers

def _ramp(value: float, lo: float, hi: float) -> float:
    """0 at/below lo, 1 at/above hi, linear in between."""
    if value <= lo:
        return 0.0
    if value >= hi:
        return 1.0
    return (value - lo) / (hi - lo)


def _trapezoid(value: float, rule: dict) -> float:
    z0, f0, f1, z1 = rule["zero_below"], rule["full_from"], rule["full_to"], rule["zero_above"]
    if value <= z0 or value >= z1:
        return 0.0
    if value < f0:
        return (value - z0) / (f0 - z0)
    if value <= f1:
        return 1.0
    return (z1 - value) / (z1 - f1)


def _require_aware(dt: datetime, name: str) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise InvalidRiskInputError(f"{name} must be a timezone-aware datetime.")
    return dt.astimezone(timezone.utc)


_WEATHER_LIMITS = {
    "temperature_c": (-60.0, 60.0),
    "relative_humidity_pct": (0.0, 100.0),
    "rainfall_24h_mm": (0.0, 1000.0),
    "wind_speed_ms": (0.0, 120.0),
    "wind_direction_deg": (0.0, 360.0),
}


def _clean_weather(weather: Optional[WeatherInput], now: datetime, cfg: dict):
    """Validate weather. Returns (usable values dict, status, notes).

    status: not_requested | missing | stale | invalid | available | partial
    Out-of-range or non-numeric values are dropped (never replaced by a
    default), so they never silently count as favourable or unfavourable.
    """
    if weather is None:
        return {}, "missing", ["No weather data was available for this location."]

    notes: List[str] = []

    try:
        observed = _require_aware(weather.observed_at, "weather.observed_at")
    except InvalidRiskInputError:
        return {}, "invalid", ["Weather data had no valid timestamp and was ignored."]

    wcfg = cfg["weather"]
    if weather.kind not in ("current", "historical", "forecast"):
        return {}, "invalid", [f"Weather kind '{weather.kind}' is not recognised; data ignored."]

    if weather.kind != "forecast":
        if observed > now + timedelta(hours=wcfg["future_tolerance_hours"]):
            return {}, "invalid", ["Weather observation is timestamped in the future and was ignored."]
        if now - observed > timedelta(hours=wcfg["max_age_hours"]):
            age_h = (now - observed).total_seconds() / 3600
            return {}, "stale", [
                f"Weather observation is {age_h:.1f} h old (limit {wcfg['max_age_hours']:g} h) and was ignored."
            ]

    values: Dict[str, float] = {}
    for key, (lo, hi) in _WEATHER_LIMITS.items():
        raw = getattr(weather, key)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or not lo <= raw <= hi:
            notes.append(f"Ignored invalid {key} value.")
            continue
        values[key] = float(raw)

    if not values:
        return {}, "missing", notes or ["Weather response contained no usable variables."]

    complete = all(k in values for k in _WEATHER_LIMITS)
    return values, ("available" if complete else "partial"), notes


# ----------------------------------------------------------------- engine

def assess_risk(
    target: TargetInput,
    disease: str,
    cases: List[CaseInput],
    weather: Optional[WeatherInput],
    config: dict,
    now: Optional[datetime] = None,
    surveillance_observations: int = 0,
    window_days: Optional[float] = None,
    weather_requested: bool = True,
) -> dict:
    """Compute one preliminary risk assessment for one disease.

    `cases` should be the nearby observations the caller found (any disease);
    the engine itself filters by disease, distance, window and verification.
    `surveillance_observations` counts ALL observations (including healthy)
    in the area and window: it distinguishes "no reports because nothing was
    surveyed" (insufficient data) from "surveyed, nothing reported" (low).
    """
    now = _require_aware(now or datetime.now(timezone.utc), "now")

    rules = config["diseases"].get(disease)
    if rules is None:
        raise UnsupportedDiseaseError(
            f"'{disease}' is not a supported disease for risk assessment. Supported: {sorted(config['diseases'])}."
        )

    window = float(window_days if window_days is not None else config["lookup"]["window_days"])
    if window <= 0:
        raise InvalidRiskInputError("window_days must be positive.")
    if surveillance_observations < 0:
        raise InvalidRiskInputError("surveillance_observations cannot be negative.")

    cw = config["case_weighting"]
    max_dist = rules["max_distance_km"]
    cutoff = now - timedelta(days=window)

    considered: List[dict] = []
    excluded = {"other_disease": 0, "too_far": 0, "outside_window": 0, "rejected": 0, "low_confidence": 0}

    for case in cases:
        if case.distance_km is None or not math.isfinite(case.distance_km) or case.distance_km < 0:
            raise InvalidRiskInputError(f"Case {case.observation_id}: distance_km must be a non-negative number.")
        observed = _require_aware(case.observed_at, f"case {case.observation_id} observed_at")
        if case.verification_status not in cw["verification"]:
            raise InvalidRiskInputError(f"Case {case.observation_id}: unknown verification status '{case.verification_status}'.")

        if case.disease != disease:
            excluded["other_disease"] += 1
            continue
        if case.verification_status == "rejected" or cw["verification"][case.verification_status] == 0:
            excluded["rejected"] += 1
            continue
        if case.distance_km > max_dist:
            excluded["too_far"] += 1
            continue
        if observed < cutoff or observed > now + timedelta(hours=1):
            excluded["outside_window"] += 1
            continue
        if (
            case.verification_status == "unverified"
            and case.confidence is not None
            and case.confidence < cw["min_unverified_confidence"]
        ):
            excluded["low_confidence"] += 1
            continue

        age_days = max(0.0, (now - observed).total_seconds() / 86400)
        proximity = max(0.0, 1.0 - case.distance_km / max_dist)
        recency = 0.5 ** (age_days / cw["recency_half_life_days"])
        status_w = cw["verification"][case.verification_status]
        considered.append({
            "case": case,
            "age_days": age_days,
            "weight": proximity * recency * status_w,
        })

    weather_values, weather_status, weather_notes = _clean_weather(weather, now, config)
    if not weather_requested:
        weather_status, weather_notes = "not_requested", ["Weather was not requested for this assessment."]

    data_quality = {
        "weather_status": weather_status,
        "weather_kind": weather.kind if weather and weather_values else None,
        "weather_source": weather.source if weather and weather_values else None,
        "weather_notes": weather_notes,
        "cases_considered": len(considered),
        "cases_excluded": excluded,
        "surveillance_observations": surveillance_observations,
        "window_days": window,
        "search_distance_km": max_dist,
        "missing_factors": [],
    }

    base = {
        "plantation_id": target.plantation_id,
        "disease": disease,
        "disease_label": rules["label"],
        "score_name": config["score_name"],
        "assessed_at": now.isoformat(),
        "rule_version": config["rule_version"],
        "data_quality": data_quality,
        "factors": [],
        "nearby_cases": [
            {
                "observation_id": c["case"].observation_id,
                "distance_km": round(c["case"].distance_km, 2),
                "age_days": round(c["age_days"], 1),
                "verification_status": c["case"].verification_status,
            }
            for c in sorted(considered, key=lambda c: c["case"].distance_km)
        ],
    }

    rec = config["recommendations"]

    # ---- no usable reports: Low only if the area is actually being surveyed
    if not considered or sum(c["weight"] for c in considered) <= 0:
        if surveillance_observations < config["min_surveillance_observations"]:
            data_quality["level"] = "insufficient"
            return {
                **base,
                "risk_score": None,
                "risk_category": CATEGORY_INSUFFICIENT,
                "risk_category_label": CATEGORY_LABELS[CATEGORY_INSUFFICIENT],
                "explanation": (
                    f"No {rules['label'].lower()} reports and no other observations were found within "
                    f"{max_dist:g} km in the last {window:g} days, so the area cannot be judged. "
                    "A lack of data is not evidence of low risk."
                ),
                "recommended_action": rec["insufficient_data"],
            }
        data_quality["level"] = "complete" if weather_status != "missing" else "partial"
        return {
            **base,
            "risk_score": 0.0,
            "risk_category": CATEGORY_LOW,
            "risk_category_label": CATEGORY_LABELS[CATEGORY_LOW],
            "explanation": (
                f"No {rules['label'].lower()} reports within {max_dist:g} km in the last {window:g} days, "
                f"although {surveillance_observations} other observation(s) were recorded in the area. "
                "This reflects the absence of reports, not proof that the disease is absent."
            ),
            "recommended_action": rec["low"],
        }

    # ---- factors
    total_w = sum(c["weight"] for c in considered)
    pressure = 1.0 - math.exp(-total_w / cw["pressure_saturation"])
    weights = rules["weights"]
    wrules = rules["weather_rules"]
    factors: List[dict] = []
    missing: List[str] = []

    def add(name, label, raw, norm, weight, note):
        factors.append({"name": name, "label": label, "raw_value": raw, "normalized": None if norm is None else round(norm, 3),
                        "weight": weight, "used": norm is not None and weight > 0, "note": note})
        if norm is None and weight > 0:
            missing.append(name)

    nearest = min(considered, key=lambda c: c["case"].distance_km)
    newest = min(considered, key=lambda c: c["age_days"])
    add("pressure", "Nearby reported cases", len(considered), pressure, weights["pressure"],
        f"{len(considered)} case(s) within {max_dist:g} km; nearest {nearest['case'].distance_km:.1f} km")

    if "rainfall" in weights:
        v = weather_values.get("rainfall_24h_mm")
        r = wrules["rainfall_24h_mm"]
        add("rainfall", "Rainfall (last 24 h)", v, None if v is None else _ramp(v, r["zero_at_or_below"], r["full_at_or_above"]),
            weights["rainfall"], "Rain splash can spread leaf-spot pathogens; thresholds are provisional.")
    if "humidity" in weights:
        v = weather_values.get("relative_humidity_pct")
        r = wrules["relative_humidity_pct"]
        add("humidity", "Relative humidity", v, None if v is None else _ramp(v, r["zero_at_or_below"], r["full_at_or_above"]),
            weights["humidity"], "Higher humidity favours infection; thresholds are provisional.")
    if "temperature" in weights:
        v = weather_values.get("temperature_c")
        add("temperature", "Air temperature", v, None if v is None else _trapezoid(v, wrules["temperature_c"]),
            weights["temperature"], "Scored against a configured temperature range; range is provisional.")
    if "wind" in weights:
        speed = weather_values.get("wind_speed_ms")
        direction = weather_values.get("wind_direction_deg")
        r = wrules["wind_speed_ms"]
        norm, note = None, "Wind speed unavailable."
        if speed is not None:
            speed_f = _ramp(speed, r["zero_at_or_below"], r["full_at_or_above"])
            bearings = [(c["weight"], c["case"].bearing_to_case_deg) for c in considered if c["case"].bearing_to_case_deg is not None]
            if direction is not None and bearings:
                # Wind blowing FROM a case towards the plantation has wind_from == bearing(plantation -> case)
                bw = sum(w for w, _ in bearings)
                align = sum(w * max(0.0, math.cos(math.radians(angular_difference_deg(direction, b)))) for w, b in bearings) / bw
                norm = speed_f * align
                note = f"Wind speed and how closely the wind direction ({direction:.0f}°) lines up from the reported cases towards the plantation."
            else:
                note = "Wind direction unavailable, so wind could not be assessed."
        add("wind", "Wind (speed and direction from cases)", speed, norm, weights["wind"], note)
    if "susceptibility" in weights:
        crop = (target.crop_type or "").lower()
        s = config["crop_susceptibility"].get(crop, {}).get(disease)
        add("susceptibility", "Crop susceptibility", s, s, weights["susceptibility"],
            "From configured crop susceptibility table." if s is not None else "No susceptibility value configured for this crop.")

    used = [f for f in factors if f["used"]]
    used_weight = sum(f["weight"] for f in used)
    # Missing factors are dropped and the remaining weights renormalised, so a
    # missing value neither adds risk nor silently counts as zero risk.
    score = 100.0 * sum(f["weight"] * f["normalized"] for f in used) / used_weight

    t = config["category_thresholds"]
    category = (
        CATEGORY_VERY_HIGH if score >= t["very_high"]
        else CATEGORY_HIGH if score >= t["high"]
        else CATEGORY_MODERATE if score >= t["moderate"]
        else CATEGORY_LOW
    )

    data_quality["missing_factors"] = missing
    data_quality["level"] = "complete" if not missing else "partial"
    data_quality["environmental_assessment_complete"] = not any(
        n in missing for n in ("rainfall", "humidity", "temperature", "wind")
    )

    # ---- explanation: only statements supported by the inputs
    parts = [
        f"{len(considered)} {rules['label'].lower()} report(s) within {max_dist:g} km in the last {window:g} days "
        f"(nearest {nearest['case'].distance_km:.1f} km, most recent {newest['age_days']:.1f} days ago)."
    ]
    unverified = sum(1 for c in considered if c["case"].verification_status == "unverified")
    if unverified:
        parts.append(f"{unverified} of these are unverified model detections and are weighted lower than confirmed cases.")
    env_used = [f for f in used if f["name"] in ("rainfall", "humidity", "temperature", "wind")]
    if env_used:
        favourable = [f["label"].lower() for f in env_used if f["normalized"] >= 0.66]
        if favourable:
            parts.append(f"Current conditions score as favourable for: {', '.join(favourable)} (provisional thresholds).")
        else:
            parts.append("Available environmental conditions do not score as strongly favourable.")
    if not data_quality["environmental_assessment_complete"]:
        parts.append("The environmental assessment is incomplete, so the index relies mostly on reported cases.")
    parts.append("This is a preliminary inspection-priority index, not a probability of infection.")

    return {
        **base,
        "factors": factors,
        "risk_score": round(score, 1),
        "risk_category": category,
        "risk_category_label": CATEGORY_LABELS[category],
        "explanation": " ".join(parts),
        "recommended_action": rec[category],
    }
