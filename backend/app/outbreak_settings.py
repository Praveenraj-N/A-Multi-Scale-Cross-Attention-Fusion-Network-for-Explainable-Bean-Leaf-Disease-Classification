"""Settings for the outbreak-monitoring feature (all from environment variables).

Secrets (API keys) are only ever read here, on the server. See
backend/.env.example for the full list.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from backend.app import config


@dataclass
class OutbreakSettings:
    db_path: str = str(config.PROJECT_ROOT / "backend" / "data" / "outbreak.db")

    # Shared secret for write access and precise locations. Unset = writes
    # disabled and everyone is treated as a public (privacy-limited) viewer.
    admin_api_key: Optional[str] = None

    # Decimal places kept for coordinates shown to non-admin viewers
    # (2 decimals is roughly 1.1 km).
    public_coordinate_decimals: int = 2

    # Weather: "open-meteo" or "none"
    weather_provider: str = "open-meteo"
    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_api_key: Optional[str] = None  # only needed for commercial Open-Meteo plans
    weather_timeout_s: float = 4.0
    weather_cache_ttl_s: int = 1800
    weather_failure_backoff_s: int = 60
    max_weather_cells_per_request: int = 8

    risk_config_path: Optional[str] = None

    # Duplicate detection: same disease within this distance and time
    duplicate_distance_m: float = 25.0
    duplicate_window_minutes: float = 10.0

    max_page_size: int = 500
    max_map_plantations: int = 300

    supported_crops: tuple = field(default=("common_bean",))


def _opt(name: str) -> Optional[str]:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def load_settings() -> OutbreakSettings:
    s = OutbreakSettings()
    s.db_path = _opt("OUTBREAK_DB_PATH") or s.db_path
    s.admin_api_key = _opt("OUTBREAK_ADMIN_API_KEY")
    s.public_coordinate_decimals = int(os.environ.get("OUTBREAK_PUBLIC_COORD_DECIMALS", s.public_coordinate_decimals))
    s.weather_provider = (_opt("WEATHER_PROVIDER") or s.weather_provider).lower()
    s.weather_base_url = _opt("WEATHER_BASE_URL") or s.weather_base_url
    s.weather_api_key = _opt("WEATHER_API_KEY")
    s.weather_timeout_s = float(os.environ.get("WEATHER_TIMEOUT_S", s.weather_timeout_s))
    s.risk_config_path = _opt("OUTBREAK_RISK_CONFIG")
    return s
