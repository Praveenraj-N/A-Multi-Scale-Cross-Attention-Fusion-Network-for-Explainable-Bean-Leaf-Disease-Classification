from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.outbreak_settings import OutbreakSettings
from backend.app.routers.outbreak import register_outbreak
from backend.app.services.outbreak_risk_service import WeatherInput
from backend.app.services.outbreak_service import OutbreakService
from backend.app.services.outbreak_store import OutbreakStore
from backend.app.services.risk_config import load_risk_config
from backend.app.services.weather_service import WeatherError, WeatherProvider, WeatherService

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
ADMIN_KEY = "test-admin-key-123"
ADMIN = {"X-API-Key": ADMIN_KEY}


class FakeProvider(WeatherProvider):
    name = "fake"

    def __init__(self):
        self.calls = 0
        self.error = None
        self.data = dict(temperature_c=22.0, relative_humidity_pct=92.0, rainfall_24h_mm=12.0, wind_speed_ms=6.0, wind_direction_deg=90.0)
        self.age = timedelta(minutes=20)

    def fetch(self, lat, lon):
        self.calls += 1
        if self.error:
            raise WeatherError(*self.error)
        return WeatherInput(kind="current", observed_at=NOW - self.age, source="fake", **self.data)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def settings(tmp_path):
    return OutbreakSettings(db_path=str(tmp_path / "outbreak.db"), admin_api_key=ADMIN_KEY)


@pytest.fixture
def store(settings):
    s = OutbreakStore(settings.db_path)
    s.migrate()
    return s


@pytest.fixture
def service(store, settings, provider):
    weather = WeatherService(provider, cache_ttl_s=1800, failure_backoff_s=60)
    return OutbreakService(store, weather, load_risk_config(), settings, clock=lambda: NOW)


@pytest.fixture
def app(service):
    app = FastAPI()
    register_outbreak(app, service)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def obs_payload(**overrides):
    body = {
        "disease": "bean_rust", "confidence": 0.93, "latitude": 12.9000, "longitude": 77.6000,
        "observed_at": (NOW - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "crop_type": "common_bean", "location_source": "manual_entry",
    }
    body.update(overrides)
    return body
