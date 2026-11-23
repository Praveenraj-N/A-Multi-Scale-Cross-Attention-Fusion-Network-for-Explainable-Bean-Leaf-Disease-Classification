"""Outbreak monitoring API: observations, plantations, risk, history, map data.

Access model: there is no user system in this project, so a single shared
secret (OUTBREAK_ADMIN_API_KEY, sent as the `X-API-Key` header) separates
two roles. Without the key a caller is a *public* viewer: coordinates are
rounded, and plantation names, owners, notes and boundaries are withheld.
All writes need the key.
"""

import hmac
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.app import config
from backend.app.outbreak_schemas import ObservationCreate, PlantationCreate, VerificationUpdate, normalize_crop
from backend.app.services import outbreak_risk_service as engine
from backend.app.services.geo import CoordinateError, parse_bbox, validate_coordinates
from backend.app.services.outbreak_service import (
    ADMIN, HIGH_PRIORITY, NEEDS_INSPECTION, PRIORITY_ORDER, PUBLIC, OutbreakService, overall_priority,
    serialize_assessment, serialize_observation, serialize_plantation, weather_summary,
)
from backend.app.services.outbreak_store import DuplicateObservationError, NotFoundError, from_db_ts
from backend.app.services.risk_config import RiskConfigError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["outbreak"])

DISEASES_ONLY = [c for c in config.CLASS_NAMES if c != "healthy"]
HISTORY_NOTE = (
    "Counts are reports submitted by users and depend on survey effort and model use. A rise in reports does not "
    "by itself show that a disease is spreading or that one case caused another. Unverified model detections are "
    "shown separately from confirmed cases."
)


# ------------------------------------------------------------ dependencies

def get_service(request: Request) -> OutbreakService:
    service = getattr(request.app.state, "outbreak", None)
    if service is None:
        raise HTTPException(503, "Outbreak monitoring is not initialised.")
    return service


def get_role(service: OutbreakService = Depends(get_service), x_api_key: Optional[str] = Header(None)) -> str:
    if x_api_key is None or x_api_key == "":
        return PUBLIC
    configured = service.settings.admin_api_key
    if not configured or not hmac.compare_digest(x_api_key.encode(), configured.encode()):
        raise HTTPException(401, "Invalid API key.")
    return ADMIN


def require_admin(service: OutbreakService = Depends(get_service), x_api_key: Optional[str] = Header(None)) -> str:
    # Misconfiguration (no key set on the server) is reported before anything else
    if not service.settings.admin_api_key:
        raise HTTPException(503, "Write access is not configured on the server (set OUTBREAK_ADMIN_API_KEY).")
    if not x_api_key:
        raise HTTPException(401, "An API key is required for this operation.")
    if not hmac.compare_digest(x_api_key.encode(), service.settings.admin_api_key.encode()):
        raise HTTPException(401, "Invalid API key.")
    return ADMIN


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _check_range(date_from: Optional[datetime], date_to: Optional[datetime]):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must not be after date_to.")


def _bbox(value: Optional[str]):
    return parse_bbox(value)  # CoordinateError -> 422 via handler


def _check_diseases(values: Optional[List[str]]):
    for v in values or []:
        if v not in config.CLASS_NAMES:
            raise HTTPException(422, f"Unknown disease '{v}'. Expected one of {config.CLASS_NAMES}.")


def _check_verification(values: Optional[List[str]]):
    for v in values or []:
        if v not in ("unverified", "confirmed", "rejected"):
            raise HTTPException(422, f"Unknown verification status '{v}'.")


def _crop(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return normalize_crop(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


# --------------------------------------------------------------- endpoints

@router.get("/access")
def access(role: str = Depends(get_role), service: OutbreakService = Depends(get_service)):
    cfg = service.risk_config
    return {
        "role": role,
        "writes_enabled": bool(service.settings.admin_api_key),
        "weather": {"provider": service.settings.weather_provider, "configured": service.weather.configured},
        "public_coordinate_decimals": service.settings.public_coordinate_decimals,
        "risk": {
            "rule_version": cfg["rule_version"],
            "score_name": cfg["score_name"],
            "thresholds": cfg["category_thresholds"],
            "diseases": {k: v["label"] for k, v in cfg["diseases"].items()},
            "lookup": cfg["lookup"],
        },
        "diseases": config.CLASS_NAMES,
        "supported_crops": list(service.settings.supported_crops),
    }


@router.post("/observations", status_code=201)
def create_observation(body: ObservationCreate, response: Response, role: str = Depends(require_admin),
                       service: OutbreakService = Depends(get_service)):
    store, s = service.store, service.settings

    lat, lon = body.latitude, body.longitude
    if body.location_source == "registered_plantation" and not body.plantation_id:
        raise HTTPException(422, "plantation_id is required when location_source is 'registered_plantation'.")
    if body.plantation_id:
        plantation = store.get_plantation(body.plantation_id)  # 404 if unknown
        if lat is None:
            lat, lon = plantation["latitude"], plantation["longitude"]
    if lat is None or lon is None:
        raise HTTPException(422, "Missing required coordinates: provide latitude and longitude or a registered plantation_id.")

    if body.client_id and store.find_by_client_id(body.client_id):
        response.status_code = 200  # idempotent resubmission

    try:
        row = store.add_observation(
            disease=body.disease, latitude=lat, longitude=lon, observed_at=body.observed_at or datetime.now(timezone.utc),
            crop_type=body.crop_type, detection_source=body.detection_source, location_source=body.location_source,
            confidence=body.confidence, plantation_id=body.plantation_id, notes=body.notes,
            verification_status=body.verification_status, client_id=body.client_id,
            duplicate_distance_m=s.duplicate_distance_m, duplicate_window_minutes=s.duplicate_window_minutes,
        )
    except DuplicateObservationError as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc), "existing_observation_id": exc.existing_id})

    return serialize_observation(row, role, s.public_coordinate_decimals,
                                 store.plantation_aliases([row["plantation_id"]]).get(row["plantation_id"]))


@router.get("/observations")
def list_observations(
    role: str = Depends(get_role), service: OutbreakService = Depends(get_service),
    bbox: Optional[str] = Query(None, description="south,west,north,east"),
    disease: Optional[List[str]] = Query(None), crop_type: Optional[str] = None,
    verification_status: Optional[List[str]] = Query(None),
    date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
    limit: int = Query(100, ge=1), offset: int = Query(0, ge=0),
):
    s = service.settings
    _check_diseases(disease)
    _check_verification(verification_status)
    date_from, date_to = _utc(date_from), _utc(date_to)
    _check_range(date_from, date_to)
    limit = min(limit, s.max_page_size)

    rows, total = service.store.query_observations(
        bbox=_bbox(bbox), diseases=disease, crop_type=_crop(crop_type), verification=verification_status,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
    )
    aliases = service.store.plantation_aliases(r["plantation_id"] for r in rows)
    return {
        "items": [serialize_observation(r, role, s.public_coordinate_decimals, aliases.get(r["plantation_id"])) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/observations/{observation_id}")
def get_observation(observation_id: str, role: str = Depends(get_role), service: OutbreakService = Depends(get_service)):
    row = service.store.get_observation(observation_id)
    alias = service.store.plantation_aliases([row["plantation_id"]]).get(row["plantation_id"])
    return serialize_observation(row, role, service.settings.public_coordinate_decimals, alias)


@router.post("/observations/{observation_id}/verification")
def update_verification(observation_id: str, body: VerificationUpdate, role: str = Depends(require_admin),
                        service: OutbreakService = Depends(get_service)):
    row = service.store.set_verification(observation_id, body.verification_status)
    alias = service.store.plantation_aliases([row["plantation_id"]]).get(row["plantation_id"])
    return serialize_observation(row, role, service.settings.public_coordinate_decimals, alias)


@router.post("/plantations", status_code=201)
def create_plantation(body: PlantationCreate, role: str = Depends(require_admin), service: OutbreakService = Depends(get_service)):
    row = service.store.add_plantation(
        crop_type=body.crop_type, latitude=body.latitude, longitude=body.longitude, name=body.name,
        boundary_geojson=body.boundary, planting_date=body.planting_date.isoformat() if body.planting_date else None,
        crop_variety=body.crop_variety, owner_ref=body.owner_ref,
    )
    return serialize_plantation(row, role, service.settings.public_coordinate_decimals)


@router.get("/plantations/nearby")
def nearby_plantations(
    lat: float = Query(..., allow_inf_nan=False), lon: float = Query(..., allow_inf_nan=False),
    radius_km: float = Query(10.0, gt=0, le=200), crop_type: Optional[str] = None, limit: int = Query(50, ge=1),
    role: str = Depends(get_role), service: OutbreakService = Depends(get_service),
):
    lat, lon = validate_coordinates(lat, lon)
    s = service.settings
    rows = service.store.plantations_within(lat, lon, radius_km, crop_type=_crop(crop_type), limit=min(limit, s.max_page_size))
    return {
        "search_area": {"latitude": lat, "longitude": lon, "radius_km": radius_km,
                        "note": "Proximity-search area only. It is not a model of disease spread."},
        "items": [serialize_plantation(r, role, s.public_coordinate_decimals) for r in rows],
        "count": len(rows),
    }


@router.get("/plantations/{plantation_id}")
def get_plantation(plantation_id: str, role: str = Depends(get_role), service: OutbreakService = Depends(get_service)):
    return serialize_plantation(service.store.get_plantation(plantation_id), role, service.settings.public_coordinate_decimals)


@router.get("/outbreak-risk")
def outbreak_risk(
    role: str = Depends(get_role), service: OutbreakService = Depends(get_service),
    plantation_id: Optional[str] = None,
    lat: Optional[float] = Query(None, allow_inf_nan=False), lon: Optional[float] = Query(None, allow_inf_nan=False),
    crop_type: Optional[str] = None, disease: Optional[List[str]] = Query(None),
    radius_km: Optional[float] = Query(None, gt=0, le=200), window_days: Optional[float] = Query(None, gt=0, le=365),
    include_weather: bool = True, persist: bool = False,
):
    s = service.settings
    if plantation_id and (lat is not None or lon is not None):
        raise HTTPException(422, "Provide either plantation_id or lat/lon, not both.")
    if disease:
        for d in disease:
            if d not in service.supported_diseases:
                raise HTTPException(422, f"'{d}' is not a supported disease for risk assessment. Supported: {service.supported_diseases}.")

    if plantation_id:
        plantation = service.store.get_plantation(plantation_id)
        point = (plantation["latitude"], plantation["longitude"])
        crop = plantation["crop_type"]
        target = serialize_plantation(plantation, role, s.public_coordinate_decimals)
    elif lat is not None and lon is not None:
        point = validate_coordinates(lat, lon)
        crop = _crop(crop_type)
        plantation = None
        target = {"latitude": point[0], "longitude": point[1], "crop_type": crop}
    else:
        raise HTTPException(422, "Provide plantation_id, or both lat and lon.")

    weather_result = service.fetch_weather(*point) if include_weather else None
    assessments = service.assess_location(
        lat=point[0], lon=point[1], crop_type=crop, plantation_id=plantation_id, diseases=disease, radius_km=radius_km,
        window_days=window_days, weather_result=weather_result, weather_requested=include_weather,
    )

    persisted = False
    if persist:
        if role != ADMIN:
            raise HTTPException(401, "An API key is required to store assessments.")
        if not plantation:
            raise HTTPException(422, "Only plantation assessments can be stored.")
        for a in assessments:
            service.store.save_risk_assessment(a)
        if weather_result and weather_result.data:
            service.store.save_weather(point[0], point[1], weather_result.data)
        persisted = True

    return {
        "target": target,
        "assessments": [serialize_assessment(a, role) for a in assessments],
        "overall": overall_priority(assessments),
        "weather": weather_summary(weather_result),
        "persisted": persisted,
        "disclaimer": "Preliminary inspection-priority index from configurable baseline rules. Not a validated infection probability.",
    }


@router.post("/outbreak-risk/snapshot")
def snapshot_risk(role: str = Depends(require_admin), service: OutbreakService = Depends(get_service),
                  include_weather: bool = True):
    """Compute and store an assessment for every plantation, building the history of inspection priority."""
    plantations, total = service.store.list_plantations(limit=service.settings.max_map_plantations)
    results = service.assess_plantations(plantations, include_weather=include_weather, persist=True)
    counts: dict = {}
    for r in results.values():
        counts[r["overall"]["category"]] = counts.get(r["overall"]["category"], 0) + 1
    return {"assessed": len(results), "total_plantations": total, "truncated": total > len(results), "by_category": counts}


@router.get("/outbreak-history")
def outbreak_history(
    role: str = Depends(get_role), service: OutbreakService = Depends(get_service),
    date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
    bucket: str = Query("day", pattern="^(day|week)$"), disease: Optional[List[str]] = Query(None),
    crop_type: Optional[str] = None, bbox: Optional[str] = None,
):
    _check_diseases(disease)
    now = service.clock()
    date_to = _utc(date_to) or now
    date_from = _utc(date_from) or (date_to - timedelta(days=30))
    _check_range(date_from, date_to)
    if (date_to - date_from).days > 366:
        raise HTTPException(422, "The date range cannot exceed 366 days.")

    rows = service.store.history(date_from=date_from, date_to=date_to, bucket=bucket, bbox=_bbox(bbox),
                                 diseases=disease, crop_type=_crop(crop_type))

    series: dict = {}
    by_disease: dict = {}
    by_verification: dict = {}
    for r in rows:
        point = series.setdefault(r["period"], {"period": r["period"], "total": 0, "confirmed": 0, "unverified": 0, "rejected": 0,
                                                "by_disease": {}})
        point["total"] += r["count"]
        point[r["verification_status"]] += r["count"]
        point["by_disease"][r["disease"]] = point["by_disease"].get(r["disease"], 0) + r["count"]
        by_disease[r["disease"]] = by_disease.get(r["disease"], 0) + r["count"]
        by_verification[r["verification_status"]] = by_verification.get(r["verification_status"], 0) + r["count"]

    # Fill days with no reports with explicit zeros so the chart axis is continuous
    ordered = []
    if bucket == "day":
        day = date_from.date()
        while day <= date_to.date():
            key = day.isoformat()
            ordered.append(series.get(key, {"period": key, "total": 0, "confirmed": 0, "unverified": 0, "rejected": 0, "by_disease": {}}))
            day += timedelta(days=1)
    else:
        ordered = [series[k] for k in sorted(series)]

    # Inspection-priority changes come only from stored snapshots (never reconstructed)
    snapshots = service.store.risk_history(date_from=date_from, date_to=date_to)
    latest: dict = {}
    for r in snapshots:
        latest[(r["assessed_at"][:10], r["plantation_id"], r["disease"])] = r  # later rows overwrite earlier ones
    per_day: dict = {}
    for (day, pid, _), r in latest.items():
        cur = per_day.setdefault(day, {}).get(pid)
        if cur is None or PRIORITY_ORDER.index(r["risk_category"]) > PRIORITY_ORDER.index(cur):
            per_day[day][pid] = r["risk_category"]
    priority_series = []
    for day in sorted(per_day):
        counts = {c: 0 for c in PRIORITY_ORDER}
        for cat in per_day[day].values():
            counts[cat] += 1
        priority_series.append({"period": day, "plantations_assessed": len(per_day[day]), "by_category": counts})

    return {
        "range": {"from": date_from.isoformat().replace("+00:00", "Z"), "to": date_to.isoformat().replace("+00:00", "Z")},
        "bucket": bucket,
        "total": sum(by_disease.values()),
        "by_disease": by_disease,
        "by_verification": by_verification,
        "series": ordered,
        "priority_series": priority_series,
        "priority_note": "Priority history exists only for days on which an assessment snapshot was stored.",
        "interpretation_note": HISTORY_NOTE,
    }


@router.get("/map-data")
def map_data(
    role: str = Depends(get_role), service: OutbreakService = Depends(get_service),
    bbox: Optional[str] = None, disease: Optional[List[str]] = Query(None), crop_type: Optional[str] = None,
    verification_status: Optional[List[str]] = Query(None), risk_category: Optional[List[str]] = Query(None),
    date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
    radius_km: Optional[float] = Query(None, gt=0, le=200),
    include_risk: bool = True, include_weather: bool = True,
    observation_limit: int = Query(1000, ge=1, le=5000),
):
    s = service.settings
    _check_diseases(disease)
    _check_verification(verification_status)
    for c in risk_category or []:
        if c not in PRIORITY_ORDER:
            raise HTTPException(422, f"Unknown risk category '{c}'. Expected one of {PRIORITY_ORDER}.")
    date_from, date_to = _utc(date_from), _utc(date_to)
    _check_range(date_from, date_to)
    box, crop, now = _bbox(bbox), _crop(crop_type), service.clock()

    obs_rows, obs_total = service.store.query_observations(
        bbox=box, diseases=disease, crop_type=crop, verification=verification_status,
        date_from=date_from, date_to=date_to, limit=observation_limit,
    )
    aliases = service.store.plantation_aliases(r["plantation_id"] for r in obs_rows)
    observations = [serialize_observation(r, role, s.public_coordinate_decimals, aliases.get(r["plantation_id"])) for r in obs_rows]

    plantation_rows, plantation_total = service.store.list_plantations(bbox=box, crop_type=crop, limit=s.max_map_plantations)

    assessed = {}
    weather_states: List[str] = []
    if include_risk and plantation_rows:
        assessed = service.assess_plantations(plantation_rows, include_weather=include_weather, radius_km=radius_km)
        for r in assessed.values():
            w = r["weather"]
            weather_states.append("ok" if (w and w.data) else (w.status if w else "not_requested"))

    plantations = []
    for p in plantation_rows:
        item = serialize_plantation(p, role, s.public_coordinate_decimals)
        a = assessed.get(p["id"])
        if a:
            item["risk"] = {
                "overall": a["overall"],
                "assessments": [
                    {"disease": x["disease"], "category": x["risk_category"], "score": x["risk_score"],
                     "explanation": x["explanation"]} for x in a["assessments"]
                ],
            }
            if risk_category and a["overall"]["category"] not in risk_category:
                continue
        elif risk_category:
            continue
        plantations.append(item)

    # Summary cards: counts of real records only
    detection_filter = [d for d in (disease or DISEASES_ONLY) if d != "healthy"]
    _, detections = service.store.query_observations(
        bbox=box, diseases=detection_filter, crop_type=crop, verification=verification_status or ["unverified", "confirmed"],
        date_from=date_from, date_to=date_to, limit=1) if detection_filter else ([], 0)
    recent_from = max([d for d in (date_from, now - timedelta(days=7)) if d])
    _, recent = service.store.query_observations(
        bbox=box, diseases=detection_filter, crop_type=crop, verification=verification_status or ["unverified", "confirmed"],
        date_from=recent_from, date_to=date_to, limit=1) if detection_filter else ([], 0)

    priorities = [p["risk"]["overall"]["category"] for p in plantations if "risk" in p]
    ok_cells = weather_states.count("ok")
    if not include_risk or not include_weather:
        weather_status = "not_requested"
    elif not service.weather.configured:
        weather_status = "not_configured"
    elif not weather_states:
        weather_status = "not_requested"
    elif ok_cells == len(weather_states):
        weather_status = "ok"
    elif ok_cells == 0:
        weather_status = "unavailable"
    else:
        weather_status = "partial"

    return {
        "observations": observations,
        "plantations": plantations,
        "truncated": {"observations": obs_total > len(observations), "plantations": plantation_total > len(plantation_rows)},
        "summary": {
            "reported_detections": detections,
            "recent_detections_7d": recent,
            "plantations_registered": plantation_total,
            "plantations_assessed": len(priorities),
            "plantations_requiring_inspection": sum(1 for c in priorities if c in NEEDS_INSPECTION) if priorities else None,
            "high_priority_locations": sum(1 for c in priorities if c in HIGH_PRIORITY) if priorities else None,
            "observations_matching_filters": obs_total,
        },
        "weather": {"status": weather_status},
        "risk_rule_version": service.risk_config["rule_version"],
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "legend_note": "Risk markers show an estimated inspection priority, not verified infection.",
    }


# --------------------------------------------------------------- wiring

def build_outbreak_service(settings=None) -> OutbreakService:
    """Create the service from environment settings and apply pending DB migrations."""
    from backend.app.outbreak_settings import load_settings
    from backend.app.services.outbreak_store import OutbreakStore
    from backend.app.services.risk_config import load_risk_config
    from backend.app.services.weather_service import build_weather_service

    settings = settings or load_settings()
    risk_config = load_risk_config(settings.risk_config_path)
    store = OutbreakStore(settings.db_path)
    store.migrate()
    return OutbreakService(store, build_weather_service(settings), risk_config, settings)


def register_outbreak(app: FastAPI, service: Optional[OutbreakService] = None) -> None:
    """Attach the router and error handlers; `service` may be set later on app.state.outbreak."""
    if service is not None:
        app.state.outbreak = service
    app.include_router(router)

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(CoordinateError)
    async def _bad_coords(_: Request, exc: CoordinateError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(engine.UnsupportedDiseaseError)
    async def _unsupported(_: Request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(engine.InvalidRiskInputError)
    async def _bad_risk_input(_: Request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(RiskConfigError)
    async def _bad_config(_: Request, exc):
        logger.error("Risk configuration error: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "The risk configuration is invalid. See server logs."})

    @app.exception_handler(sqlite3.Error)
    async def _db_error(_: Request, exc: sqlite3.Error):
        logger.error("Database error: %s", exc)  # message only: never echo paths or SQL to clients
        return JSONResponse(status_code=503, content={"detail": "The outbreak database is unavailable. Try again shortly."})
