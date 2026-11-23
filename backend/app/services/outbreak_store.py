"""SQLite persistence for plantations, disease observations, risk assessments
and fetched weather.

SQLite (Python stdlib) was chosen because the project had no database and this
needs no extra infrastructure. Spatial queries use an indexed latitude /
longitude bounding-box pre-filter followed by exact great-circle (haversine)
distances. If the project later moves to PostgreSQL, PostGIS can replace
`_within` while the rest of this class keeps its interface.

Timestamps are stored as UTC ISO-8601 strings with a fixed format
(YYYY-MM-DDTHH:MM:SSZ) so string comparison equals chronological comparison.
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from backend.app.services.geo import BoundingBox, bearing_deg, bounding_box, haversine_km

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def to_db_ts(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("Timestamps must be timezone-aware.")
    return dt.astimezone(timezone.utc).strftime(TS_FORMAT)


def from_db_ts(value: str) -> datetime:
    return datetime.strptime(value, TS_FORMAT).replace(tzinfo=timezone.utc)


MIGRATIONS: List[Tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE plantations (
            id TEXT PRIMARY KEY,
            alias TEXT NOT NULL,
            name TEXT,
            crop_type TEXT NOT NULL,
            latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
            longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
            boundary_geojson TEXT,
            planting_date TEXT,
            crop_variety TEXT,
            owner_ref TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_plantations_location ON plantations (latitude, longitude);
        CREATE INDEX idx_plantations_crop ON plantations (crop_type);

        CREATE TABLE observations (
            id TEXT PRIMARY KEY,
            client_id TEXT UNIQUE,
            plantation_id TEXT REFERENCES plantations (id),
            disease TEXT NOT NULL,
            confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
            latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
            longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
            observed_at TEXT NOT NULL,
            crop_type TEXT NOT NULL,
            notes TEXT,
            verification_status TEXT NOT NULL DEFAULT 'unverified',
            detection_source TEXT NOT NULL,
            location_source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            verified_at TEXT
        );
        CREATE INDEX idx_observations_location ON observations (latitude, longitude);
        CREATE INDEX idx_observations_time ON observations (observed_at);
        CREATE INDEX idx_observations_disease_time ON observations (disease, observed_at);
        CREATE INDEX idx_observations_plantation ON observations (plantation_id);

        CREATE TABLE risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plantation_id TEXT NOT NULL REFERENCES plantations (id),
            disease TEXT NOT NULL,
            assessed_at TEXT NOT NULL,
            risk_score REAL,
            risk_category TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX idx_risk_plantation_time ON risk_assessments (plantation_id, assessed_at);
        CREATE INDEX idx_risk_time ON risk_assessments (assessed_at);

        CREATE TABLE weather_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            kind TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL,
            temperature_c REAL,
            relative_humidity_pct REAL,
            rainfall_24h_mm REAL,
            wind_speed_ms REAL,
            wind_direction_deg REAL
        );
        CREATE INDEX idx_weather_time ON weather_observations (observed_at);
        """,
    ),
]


class NotFoundError(LookupError):
    pass


class DuplicateObservationError(ValueError):
    def __init__(self, existing_id: str, message: str):
        super().__init__(message)
        self.existing_id = existing_id


def _row(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row is not None else None


def _bbox_clause(bbox: BoundingBox, lat_col="latitude", lon_col="longitude") -> Tuple[str, list]:
    if bbox.crosses_antimeridian:
        clause = f"{lat_col} BETWEEN ? AND ? AND ({lon_col} >= ? OR {lon_col} <= ?)"
    else:
        clause = f"{lat_col} BETWEEN ? AND ? AND {lon_col} BETWEEN ? AND ?"
    return clause, [bbox.min_lat, bbox.max_lat, bbox.min_lon, bbox.max_lon]


class OutbreakStore:
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ plumbing

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> int:
        """Apply pending migrations. Existing data is never touched. Returns the schema version."""
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
            for version, script in MIGRATIONS:
                if version in applied:
                    continue
                for statement in [s.strip() for s in script.split(";") if s.strip()]:
                    conn.execute(statement)
                conn.execute("INSERT INTO schema_migrations VALUES (?, ?)", (version, to_db_ts(datetime.now(timezone.utc))))
            return max(v for v, _ in MIGRATIONS)

    def ping(self) -> None:
        with self.connect() as conn:
            conn.execute("SELECT 1").fetchone()

    # ---------------------------------------------------------- plantations

    def add_plantation(self, *, crop_type: str, latitude: float, longitude: float, name: Optional[str] = None,
                       boundary_geojson: Optional[dict] = None, planting_date: Optional[str] = None,
                       crop_variety: Optional[str] = None, owner_ref: Optional[str] = None) -> dict:
        pid = uuid.uuid4().hex
        alias = f"PL-{pid[:6].upper()}"
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO plantations (id, alias, name, crop_type, latitude, longitude, boundary_geojson, planting_date,"
                " crop_variety, owner_ref, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pid, alias, name, crop_type, latitude, longitude,
                 json.dumps(boundary_geojson) if boundary_geojson else None, planting_date, crop_variety, owner_ref,
                 to_db_ts(datetime.now(timezone.utc))),
            )
        return self.get_plantation(pid)

    def get_plantation(self, plantation_id: str) -> dict:
        with self.connect() as conn:
            row = _row(conn.execute("SELECT * FROM plantations WHERE id = ?", (plantation_id,)).fetchone())
        if row is None:
            raise NotFoundError(f"Plantation '{plantation_id}' not found.")
        return row

    def plantation_aliases(self, ids: Iterable[str]) -> Dict[str, str]:
        ids = list({i for i in ids if i})
        if not ids:
            return {}
        with self.connect() as conn:
            rows = conn.execute(f"SELECT id, alias FROM plantations WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall()
        return {r["id"]: r["alias"] for r in rows}

    def count_plantations(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM plantations").fetchone()[0]

    def list_plantations(self, bbox: Optional[BoundingBox] = None, crop_type: Optional[str] = None,
                         limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
        where, params = ["1=1"], []
        if bbox:
            clause, p = _bbox_clause(bbox)
            where.append(clause)
            params += p
        if crop_type:
            where.append("crop_type = ?")
            params.append(crop_type)
        sql_where = " AND ".join(where)
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM plantations WHERE {sql_where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM plantations WHERE {sql_where} ORDER BY created_at, id LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        return [dict(r) for r in rows], total

    def plantations_within(self, lat: float, lon: float, radius_km: float, crop_type: Optional[str] = None,
                           limit: Optional[int] = None) -> List[dict]:
        """Plantations within radius, nearest first, each with `distance_km`."""
        rows = self._within("plantations", lat, lon, radius_km, extra_where=["crop_type = ?"] if crop_type else [],
                            extra_params=[crop_type] if crop_type else [])
        return rows[:limit] if limit else rows

    # --------------------------------------------------------- observations

    def get_observation(self, observation_id: str) -> dict:
        with self.connect() as conn:
            row = _row(conn.execute("SELECT * FROM observations WHERE id = ?", (observation_id,)).fetchone())
        if row is None:
            raise NotFoundError(f"Observation '{observation_id}' not found.")
        return row

    def find_by_client_id(self, client_id: str) -> Optional[dict]:
        with self.connect() as conn:
            return _row(conn.execute("SELECT * FROM observations WHERE client_id = ?", (client_id,)).fetchone())

    def add_observation(self, *, disease: str, latitude: float, longitude: float, observed_at: datetime, crop_type: str,
                        detection_source: str, location_source: str, confidence: Optional[float] = None,
                        plantation_id: Optional[str] = None, notes: Optional[str] = None,
                        verification_status: str = "unverified", client_id: Optional[str] = None,
                        duplicate_distance_m: float = 25.0, duplicate_window_minutes: float = 10.0) -> dict:
        """Insert an observation.

        Idempotent by `client_id` (re-sending returns the original). Otherwise an
        observation of the same disease within `duplicate_distance_m` and
        `duplicate_window_minutes` of an existing one raises DuplicateObservationError.
        """
        if client_id:
            existing = self.find_by_client_id(client_id)
            if existing:
                return existing

        if plantation_id:
            self.get_plantation(plantation_id)  # NotFoundError if unknown

        dup = self._find_duplicate(disease, latitude, longitude, observed_at, duplicate_distance_m, duplicate_window_minutes)
        if dup:
            raise DuplicateObservationError(
                dup["id"],
                f"A {disease.replace('_', ' ')} observation within {duplicate_distance_m:g} m and "
                f"{duplicate_window_minutes:g} minutes already exists.",
            )

        oid = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO observations (id, client_id, plantation_id, disease, confidence, latitude, longitude,"
                " observed_at, crop_type, notes, verification_status, detection_source, location_source, created_at,"
                " verified_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (oid, client_id, plantation_id, disease, confidence, latitude, longitude, to_db_ts(observed_at), crop_type,
                 notes, verification_status, detection_source, location_source, to_db_ts(now),
                 to_db_ts(now) if verification_status != "unverified" else None),
            )
        return self.get_observation(oid)

    def _find_duplicate(self, disease, lat, lon, observed_at, distance_m, window_min) -> Optional[dict]:
        lo = to_db_ts(observed_at - timedelta(minutes=window_min))
        hi = to_db_ts(observed_at + timedelta(minutes=window_min))
        rows = self._within("observations", lat, lon, distance_m / 1000.0,
                            extra_where=["disease = ?", "observed_at BETWEEN ? AND ?"], extra_params=[disease, lo, hi])
        return rows[0] if rows else None

    def set_verification(self, observation_id: str, status: str) -> dict:
        self.get_observation(observation_id)
        with self.connect() as conn:
            conn.execute(
                "UPDATE observations SET verification_status = ?, verified_at = ? WHERE id = ?",
                (status, to_db_ts(datetime.now(timezone.utc)) if status != "unverified" else None, observation_id),
            )
        return self.get_observation(observation_id)

    def _obs_filters(self, bbox, diseases, crop_type, verification, date_from, date_to):
        where, params = ["1=1"], []
        if bbox:
            clause, p = _bbox_clause(bbox)
            where.append(clause)
            params += p
        if diseases:
            where.append(f"disease IN ({','.join('?' * len(diseases))})")
            params += list(diseases)
        if crop_type:
            where.append("crop_type = ?")
            params.append(crop_type)
        if verification:
            where.append(f"verification_status IN ({','.join('?' * len(verification))})")
            params += list(verification)
        if date_from:
            where.append("observed_at >= ?")
            params.append(to_db_ts(date_from))
        if date_to:
            where.append("observed_at <= ?")
            params.append(to_db_ts(date_to))
        return " AND ".join(where), params

    def query_observations(self, *, bbox: Optional[BoundingBox] = None, diseases: Optional[Iterable[str]] = None,
                           crop_type: Optional[str] = None, verification: Optional[Iterable[str]] = None,
                           date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
                           limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
        sql_where, params = self._obs_filters(bbox, list(diseases or []), crop_type, list(verification or []), date_from, date_to)
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM observations WHERE {sql_where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM observations WHERE {sql_where} ORDER BY observed_at DESC, id LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        return [dict(r) for r in rows], total

    def observations_within(self, lat: float, lon: float, radius_km: float, *, since: Optional[datetime] = None,
                            until: Optional[datetime] = None, diseases: Optional[Iterable[str]] = None,
                            crop_type: Optional[str] = None) -> List[dict]:
        """Observations in a radius (nearest first) with `distance_km` and `bearing_deg` (from the point to the observation)."""
        where, params = [], []
        if since:
            where.append("observed_at >= ?")
            params.append(to_db_ts(since))
        if until:
            where.append("observed_at <= ?")
            params.append(to_db_ts(until))
        diseases = list(diseases or [])
        if diseases:
            where.append(f"disease IN ({','.join('?' * len(diseases))})")
            params += diseases
        if crop_type:
            where.append("crop_type = ?")
            params.append(crop_type)
        return self._within("observations", lat, lon, radius_km, extra_where=where, extra_params=params)

    def count_observations(self, *, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> int:
        sql_where, params = self._obs_filters(None, [], None, [], date_from, date_to)
        with self.connect() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM observations WHERE {sql_where}", params).fetchone()[0]

    def history(self, *, date_from: datetime, date_to: datetime, bucket: str = "day", bbox: Optional[BoundingBox] = None,
                diseases: Optional[Iterable[str]] = None, crop_type: Optional[str] = None) -> List[dict]:
        """Observation counts per time bucket, disease and verification status."""
        sql_where, params = self._obs_filters(bbox, list(diseases or []), crop_type, [], date_from, date_to)
        period = "substr(observed_at, 1, 10)" if bucket == "day" else "date(substr(observed_at, 1, 10), 'weekday 0', '-6 days')"
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT {period} AS period, disease, verification_status, COUNT(*) AS count FROM observations"
                f" WHERE {sql_where} GROUP BY period, disease, verification_status ORDER BY period",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------ risk + weather

    def save_risk_assessment(self, assessment: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO risk_assessments (plantation_id, disease, assessed_at, risk_score, risk_category, rule_version,"
                " payload_json) VALUES (?,?,?,?,?,?,?)",
                (assessment["plantation_id"], assessment["disease"], assessment["assessed_at"][:19] + "Z",
                 assessment["risk_score"], assessment["risk_category"], assessment["rule_version"], json.dumps(assessment)),
            )

    def risk_history(self, *, date_from: datetime, date_to: datetime, plantation_id: Optional[str] = None) -> List[dict]:
        where = ["assessed_at BETWEEN ? AND ?"]
        params: list = [to_db_ts(date_from), to_db_ts(date_to)]
        if plantation_id:
            where.append("plantation_id = ?")
            params.append(plantation_id)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT plantation_id, disease, assessed_at, risk_score, risk_category FROM risk_assessments"
                f" WHERE {' AND '.join(where)} ORDER BY assessed_at",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def save_weather(self, lat: float, lon: float, weather) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO weather_observations (latitude, longitude, kind, observed_at, fetched_at, source, temperature_c,"
                " relative_humidity_pct, rainfall_24h_mm, wind_speed_ms, wind_direction_deg) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (lat, lon, weather.kind, to_db_ts(weather.observed_at), to_db_ts(datetime.now(timezone.utc)), weather.source,
                 weather.temperature_c, weather.relative_humidity_pct, weather.rainfall_24h_mm, weather.wind_speed_ms,
                 weather.wind_direction_deg),
            )

    # --------------------------------------------------------------- spatial

    def _within(self, table: str, lat: float, lon: float, radius_km: float, extra_where: List[str],
                extra_params: list) -> List[dict]:
        box = bounding_box(lat, lon, radius_km)
        clause, params = _bbox_clause(box)
        where = " AND ".join([clause] + extra_where)
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM {table} WHERE {where}", params + extra_params).fetchall()

        found = []
        for r in rows:
            d = haversine_km(lat, lon, r["latitude"], r["longitude"])
            if d <= radius_km:
                item = dict(r)
                item["distance_km"] = d
                item["bearing_deg"] = bearing_deg(lat, lon, r["latitude"], r["longitude"]) if d > 0 else None
                found.append(item)
        found.sort(key=lambda x: (x["distance_km"], x["id"]))
        return found
