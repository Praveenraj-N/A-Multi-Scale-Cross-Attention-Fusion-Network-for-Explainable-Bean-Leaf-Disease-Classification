"""Request validation models for the outbreak API (response bodies are plain
dicts built by the serializers so private fields can be dropped per role)."""

import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app import config

CROP_PATTERN = re.compile(r"^[a-z0-9_]{2,40}$")
CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: Optional[str], max_len: int) -> Optional[str]:
    """Strip control characters and angle brackets; empty becomes None."""
    if value is None:
        return None
    value = _CONTROL.sub("", value).replace("<", "").replace(">", "").strip()
    if len(value) > max_len:
        raise ValueError(f"Must be at most {max_len} characters.")
    return value or None


def normalize_crop(value: str) -> str:
    crop = value.strip().lower().replace(" ", "_").replace("-", "_")
    if not CROP_PATTERN.match(crop):
        raise ValueError("crop_type must be 2-40 letters, digits or underscores (e.g. common_bean).")
    return crop


class ObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: Optional[str] = Field(None, description="Client-generated idempotency key; resubmitting returns the original record.")
    plantation_id: Optional[str] = Field(None, max_length=64)
    disease: str
    confidence: Optional[float] = Field(None, ge=0, le=1, allow_inf_nan=False)
    latitude: Optional[float] = Field(None, ge=-90, le=90, allow_inf_nan=False)
    longitude: Optional[float] = Field(None, ge=-180, le=180, allow_inf_nan=False)
    observed_at: Optional[datetime] = None
    crop_type: str = "common_bean"
    notes: Optional[str] = None
    detection_source: Literal["model_detection", "manual_report"] = "model_detection"
    location_source: Literal["browser_geolocation", "manual_entry", "registered_plantation", "administrator"]
    verification_status: Literal["unverified", "confirmed"] = "unverified"

    @field_validator("client_id")
    @classmethod
    def _client_id(cls, v):
        if v is not None and not CLIENT_ID_PATTERN.match(v):
            raise ValueError("client_id must be 8-64 characters: letters, digits, '-' or '_'.")
        return v

    @field_validator("disease")
    @classmethod
    def _disease(cls, v):
        v = v.strip().lower()
        if v not in config.CLASS_NAMES:
            raise ValueError(f"disease must be one of {config.CLASS_NAMES}.")
        return v

    @field_validator("crop_type")
    @classmethod
    def _crop(cls, v):
        return normalize_crop(v)

    @field_validator("notes")
    @classmethod
    def _notes(cls, v):
        return clean_text(v, 1000)

    @field_validator("observed_at")
    @classmethod
    def _observed_at(cls, v):
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("observed_at must include a timezone (e.g. a trailing 'Z').")
        v = v.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if v > now + timedelta(minutes=5):
            raise ValueError("observed_at cannot be in the future.")
        if v < now - timedelta(days=365 * 5):
            raise ValueError("observed_at is more than 5 years in the past.")
        return v

    @model_validator(mode="after")
    def _coords_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together.")
        if self.detection_source == "model_detection" and self.confidence is None:
            raise ValueError("confidence is required for model detections.")
        return self


class VerificationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verification_status: Literal["unverified", "confirmed", "rejected"]


class PlantationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    crop_type: str = "common_bean"
    latitude: float = Field(..., ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(..., ge=-180, le=180, allow_inf_nan=False)
    boundary: Optional[dict] = Field(None, description="GeoJSON Polygon (lon, lat order).")
    planting_date: Optional[date] = None
    crop_variety: Optional[str] = None
    owner_ref: Optional[str] = None

    @field_validator("crop_type")
    @classmethod
    def _crop(cls, v):
        return normalize_crop(v)

    @field_validator("name", "crop_variety")
    @classmethod
    def _short_text(cls, v):
        return clean_text(v, 120)

    @field_validator("owner_ref")
    @classmethod
    def _owner(cls, v):
        return clean_text(v, 120)

    @field_validator("planting_date")
    @classmethod
    def _planting(cls, v):
        if v and v > date.today():
            raise ValueError("planting_date cannot be in the future.")
        return v

    @field_validator("boundary")
    @classmethod
    def _boundary(cls, v):
        if v is None:
            return v
        if v.get("type") != "Polygon" or not isinstance(v.get("coordinates"), list):
            raise ValueError("boundary must be a GeoJSON Polygon.")
        rings = v["coordinates"]
        if not rings or sum(len(r) for r in rings if isinstance(r, list)) > 1000:
            raise ValueError("boundary must have at least one ring and at most 1000 vertices.")
        for ring in rings:
            if not isinstance(ring, list) or len(ring) < 4:
                raise ValueError("Each boundary ring needs at least 4 positions.")
            for pos in ring:
                if (not isinstance(pos, list) or len(pos) < 2
                        or not all(isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in pos[:2])):
                    raise ValueError("Boundary positions must be [longitude, latitude] numbers.")
                if not -180 <= pos[0] <= 180 or not -90 <= pos[1] <= 90:
                    raise ValueError("Boundary position out of range.")
            if ring[0][:2] != ring[-1][:2]:
                raise ValueError("Boundary rings must be closed (first position equals last).")
        return {"type": "Polygon", "coordinates": [[[p[0], p[1]] for p in ring] for ring in rings]}
