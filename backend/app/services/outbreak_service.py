"""Application service tying the store, weather and risk engine together, plus
the role-aware serializers that keep private farm data out of public responses."""

import copy
import json
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional

from backend.app.services import outbreak_risk_service as engine
from backend.app.services.geo import BoundingBox
from backend.app.services.outbreak_store import OutbreakStore, from_db_ts
from backend.app.services.weather_service import WeatherResult, WeatherService

PUBLIC = "public"
ADMIN = "admin"

PRIORITY_ORDER = [
    engine.CATEGORY_INSUFFICIENT,
    engine.CATEGORY_LOW,
    engine.CATEGORY_MODERATE,
    engine.CATEGORY_HIGH,
    engine.CATEGORY_VERY_HIGH,
]
NEEDS_INSPECTION = {engine.CATEGORY_MODERATE, engine.CATEGORY_HIGH, engine.CATEGORY_VERY_HIGH}
HIGH_PRIORITY = {engine.CATEGORY_HIGH, engine.CATEGORY_VERY_HIGH}


# ------------------------------------------------------------- serializers

def _iso(db_ts: Optional[str]) -> Optional[str]:
    return from_db_ts(db_ts).isoformat().replace("+00:00", "Z") if db_ts else None


def serialize_observation(row: dict, role: str, decimals: int, plantation_alias: Optional[str] = None) -> dict:
    out = {
        "id": row["id"],
        "disease": row["disease"],
        "confidence": row["confidence"],
        "observed_at": _iso(row["observed_at"]),
        "crop_type": row["crop_type"],
        "verification_status": row["verification_status"],
        "detection_source": row["detection_source"],
        "plantation_alias": plantation_alias,
        "created_at": _iso(row["created_at"]),
    }
    if role == ADMIN:
        out.update(
            latitude=row["latitude"], longitude=row["longitude"], plantation_id=row["plantation_id"],
            notes=row["notes"], location_source=row["location_source"], coordinates_precise=True,
        )
    else:
        out.update(
            latitude=round(row["latitude"], decimals), longitude=round(row["longitude"], decimals),
            plantation_id=None, notes=None, location_source=None, coordinates_precise=False,
        )
    return out


def serialize_plantation(row: dict, role: str, decimals: int) -> dict:
    out = {
        "id": row["id"],
        "alias": row["alias"],
        "crop_type": row["crop_type"],
        "created_at": _iso(row["created_at"]),
    }
    if "distance_km" in row:
        out["distance_km"] = round(row["distance_km"], 2 if role == ADMIN else 1)
    if role == ADMIN:
        out.update(
            name=row["name"], latitude=row["latitude"], longitude=row["longitude"], coordinates_precise=True,
            boundary=json.loads(row["boundary_geojson"]) if row["boundary_geojson"] else None,
            planting_date=row["planting_date"], crop_variety=row["crop_variety"], owner_ref=row["owner_ref"],
        )
    else:
        out.update(
            name=None, latitude=round(row["latitude"], decimals), longitude=round(row["longitude"], decimals),
            coordinates_precise=False, boundary=None, planting_date=None, crop_variety=None, owner_ref=None,
        )
    return out


def serialize_assessment(assessment: dict, role: str) -> dict:
    if role == ADMIN:
        return assessment
    out = copy.deepcopy(assessment)
    for case in out["nearby_cases"]:
        case["distance_km"] = round(case["distance_km"], 1)
    return out


def weather_summary(result: Optional[WeatherResult]) -> dict:
    if result is None:
        return {"status": "not_requested", "message": "Weather was not requested.", "values": None}
    if result.data is None:
        return {"status": result.status, "message": result.message, "values": None}
    w = result.data
    return {
        "status": "ok",
        "message": None,
        "kind": w.kind,
        "source": w.source,
        "observed_at": w.observed_at.isoformat().replace("+00:00", "Z"),
        "values": {
            "temperature_c": w.temperature_c,
            "relative_humidity_pct": w.relative_humidity_pct,
            "rainfall_24h_mm": w.rainfall_24h_mm,
            "wind_speed_ms": w.wind_speed_ms,
            "wind_direction_deg": w.wind_direction_deg,
        },
    }


def overall_priority(assessments: List[dict]) -> dict:
    """Highest-priority assessment across diseases (ties go to the higher score)."""
    best = max(
        assessments,
        key=lambda a: (PRIORITY_ORDER.index(a["risk_category"]), a["risk_score"] if a["risk_score"] is not None else -1),
    )
    return {
        "category": best["risk_category"],
        "category_label": best["risk_category_label"],
        "score": best["risk_score"],
        "disease": best["disease"],
        "disease_label": best["disease_label"],
    }


# ----------------------------------------------------------------- service

class OutbreakService:
    def __init__(self, store: OutbreakStore, weather: WeatherService, risk_config: dict, settings,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.store = store
        self.weather = weather
        self.risk_config = risk_config
        self.settings = settings
        self.clock = clock

    @property
    def supported_diseases(self) -> List[str]:
        return list(self.risk_config["diseases"])

    def _config_for(self, radius_km: Optional[float]) -> dict:
        if radius_km is None:
            return self.risk_config
        cfg = copy.deepcopy(self.risk_config)
        for rules in cfg["diseases"].values():
            rules["max_distance_km"] = min(rules["max_distance_km"], radius_km)
        return cfg

    def assess_location(self, *, lat: float, lon: float, crop_type: Optional[str], plantation_id: Optional[str],
                        diseases: Optional[Iterable[str]] = None, radius_km: Optional[float] = None,
                        window_days: Optional[float] = None, weather_result: Optional[WeatherResult] = None,
                        weather_requested: bool = True, now: Optional[datetime] = None) -> List[dict]:
        now = now or self.clock()
        cfg = self._config_for(radius_km)
        diseases = list(diseases) if diseases else list(cfg["diseases"])
        window = float(window_days if window_days is not None else cfg["lookup"]["window_days"])

        for d in diseases:  # fail before any query for unsupported diseases
            if d not in cfg["diseases"]:
                raise engine.UnsupportedDiseaseError(
                    f"'{d}' is not a supported disease for risk assessment. Supported: {sorted(cfg['diseases'])}."
                )

        search_km = max(cfg["diseases"][d]["max_distance_km"] for d in diseases)
        rows = self.store.observations_within(lat, lon, search_km, since=now - timedelta(days=window), until=now + timedelta(hours=1))
        surveillance = sum(1 for r in rows if r["verification_status"] != "rejected")

        cases = [
            engine.CaseInput(
                observation_id=r["id"], disease=r["disease"], distance_km=r["distance_km"],
                observed_at=from_db_ts(r["observed_at"]), verification_status=r["verification_status"],
                confidence=r["confidence"], bearing_to_case_deg=r["bearing_deg"],
            )
            for r in rows
        ]
        weather = weather_result.data if weather_result else None
        target = engine.TargetInput(plantation_id=plantation_id, crop_type=crop_type)

        return [
            engine.assess_risk(
                target, d, cases, weather, cfg, now=now, surveillance_observations=surveillance,
                window_days=window, weather_requested=weather_requested and weather_result is not None,
            )
            for d in diseases
        ]

    def fetch_weather(self, lat: float, lon: float) -> WeatherResult:
        return self.weather.get(lat, lon)

    def assess_plantations(self, plantations: List[dict], *, include_weather: bool, radius_km: Optional[float] = None,
                           window_days: Optional[float] = None, persist: bool = False) -> Dict[str, dict]:
        """Assess many plantations, fetching weather once per grid cell within a budget.

        Returns {plantation_id: {"assessments": [...], "overall": {...}}}.
        """
        now = self.clock()
        cell_results: Dict[tuple, Optional[WeatherResult]] = {}
        budget = self.settings.max_weather_cells_per_request
        out: Dict[str, dict] = {}

        for p in plantations:
            weather_result = None
            if include_weather and self.weather.configured:
                cell = self.weather.cell(p["latitude"], p["longitude"])
                if cell not in cell_results:
                    if len([c for c in cell_results.values() if c is not None]) < budget:
                        cell_results[cell] = self.fetch_weather(*cell)
                        if persist and cell_results[cell].data:
                            self.store.save_weather(cell[0], cell[1], cell_results[cell].data)
                    else:
                        cell_results[cell] = None  # budget exhausted: reported as not requested
                weather_result = cell_results[cell]
            elif include_weather:
                weather_result = self.fetch_weather(p["latitude"], p["longitude"])  # returns not_configured

            assessments = self.assess_location(
                lat=p["latitude"], lon=p["longitude"], crop_type=p["crop_type"], plantation_id=p["id"],
                radius_km=radius_km, window_days=window_days, weather_result=weather_result,
                weather_requested=include_weather, now=now,
            )
            if persist:
                for a in assessments:
                    self.store.save_risk_assessment(a)
            out[p["id"]] = {"assessments": assessments, "overall": overall_priority(assessments), "weather": weather_result}

        return out
