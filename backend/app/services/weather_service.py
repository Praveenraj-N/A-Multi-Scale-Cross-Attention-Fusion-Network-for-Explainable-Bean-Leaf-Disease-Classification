"""Small, replaceable weather layer.

`WeatherProvider` is the interface; `OpenMeteoProvider` implements it using
the Open-Meteo forecast endpoint (https://open-meteo.com/en/docs): current
conditions from `current=` plus the last 24 hourly precipitation values from
`hourly=precipitation&past_hours=24`. Open-Meteo needs no key for
non-commercial use; commercial plans set WEATHER_API_KEY and WEATHER_BASE_URL.

Failures never raise into callers: `WeatherService.get` returns a
`WeatherResult` whose `data` is None and whose `status`/`message` explain why.
No weather value is ever invented.
"""

import json
import logging
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple

from backend.app.services.outbreak_risk_service import WeatherInput

logger = logging.getLogger(__name__)


class WeatherError(Exception):
    """Provider-level failure. `status` is a short machine-readable reason."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class WeatherResult:
    data: Optional[WeatherInput]
    status: str  # ok | not_configured | timeout | rate_limited | network_error | invalid_response | unavailable
    message: Optional[str] = None


class WeatherProvider:
    name = "base"

    def fetch(self, lat: float, lon: float) -> WeatherInput:  # pragma: no cover - interface
        raise NotImplementedError


class OpenMeteoProvider(WeatherProvider):
    name = "open-meteo"

    def __init__(self, base_url: str, api_key: Optional[str], timeout_s: float, opener: Callable = urllib.request.urlopen):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_s = timeout_s
        self._open = opener

    def _url(self, lat: float, lon: float) -> str:
        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m",
            "hourly": "precipitation",
            "past_hours": "24",
            "forecast_hours": "1",
            "wind_speed_unit": "ms",
            "timezone": "GMT",
            "timeformat": "unixtime",
        }
        if self.api_key:
            params["apikey"] = self.api_key
        return f"{self.base_url}?{urllib.parse.urlencode(params)}"

    def fetch(self, lat: float, lon: float) -> WeatherInput:
        request = urllib.request.Request(self._url(lat, lon), headers={"User-Agent": "mscaf-outbreak-monitor/1.0"})
        try:
            with self._open(request, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise WeatherError("rate_limited", "The weather provider rate limit was reached.")
            raise WeatherError("network_error", f"The weather provider returned HTTP {exc.code}.")
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise WeatherError("timeout", "The weather provider timed out.")
            raise WeatherError("network_error", "Could not reach the weather provider.")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise WeatherError("invalid_response", "The weather provider returned malformed data.")

        return self._parse(payload)

    @staticmethod
    def _num(value):
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None

    def _parse(self, payload) -> WeatherInput:
        if not isinstance(payload, dict) or payload.get("error"):
            raise WeatherError("invalid_response", "The weather provider reported an error for this location.")

        current = payload.get("current")
        if not isinstance(current, dict) or not isinstance(current.get("time"), (int, float)):
            raise WeatherError("invalid_response", "Weather response had no current observation.")

        observed_at = datetime.fromtimestamp(current["time"], tz=timezone.utc)

        rainfall = None
        hourly = payload.get("hourly")
        if isinstance(hourly, dict) and isinstance(hourly.get("time"), list) and isinstance(hourly.get("precipitation"), list):
            # Sum the 24 hourly values that end at or before the current observation
            values = [
                self._num(p)
                for t, p in zip(hourly["time"], hourly["precipitation"])
                if isinstance(t, (int, float)) and t <= current["time"]
            ]
            values = values[-24:]
            # Only report a total when every hour is present (no silent partial sums)
            if len(values) == 24 and all(v is not None for v in values):
                rainfall = round(sum(values), 2)

        return WeatherInput(
            kind="current",
            observed_at=observed_at,
            source=self.name,
            temperature_c=self._num(current.get("temperature_2m")),
            relative_humidity_pct=self._num(current.get("relative_humidity_2m")),
            rainfall_24h_mm=rainfall,
            wind_speed_ms=self._num(current.get("wind_speed_10m")),
            wind_direction_deg=self._num(current.get("wind_direction_10m")),
        )


class WeatherService:
    """Caches provider results per ~0.1 degree cell and backs off after failures."""

    CELL_DECIMALS = 1

    def __init__(self, provider: Optional[WeatherProvider], cache_ttl_s: int = 1800, failure_backoff_s: int = 60,
                 clock: Callable[[], float] = time.monotonic):
        self.provider = provider
        self.cache_ttl_s = cache_ttl_s
        self.failure_backoff_s = failure_backoff_s
        self._clock = clock
        self._cache: Dict[Tuple[float, float], Tuple[float, WeatherInput]] = {}
        self._failed_until = 0.0
        self._last_failure: Optional[WeatherResult] = None
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return self.provider is not None

    def cell(self, lat: float, lon: float) -> Tuple[float, float]:
        return (round(lat, self.CELL_DECIMALS), round(lon, self.CELL_DECIMALS))

    def get(self, lat: float, lon: float) -> WeatherResult:
        if self.provider is None:
            return WeatherResult(None, "not_configured", "No weather provider is configured (WEATHER_PROVIDER=none).")

        cell = self.cell(lat, lon)
        now = self._clock()

        with self._lock:
            cached = self._cache.get(cell)
            if cached and now - cached[0] < self.cache_ttl_s:
                return WeatherResult(cached[1], "ok")
            if now < self._failed_until and self._last_failure is not None:
                return self._last_failure

        try:
            data = self.provider.fetch(*cell)
        except WeatherError as exc:
            logger.warning("Weather fetch failed (%s): %s", exc.status, exc.message)
            result = WeatherResult(None, exc.status, exc.message)
        except Exception:  # never let a provider bug break risk assessment
            logger.exception("Unexpected weather provider error")
            result = WeatherResult(None, "unavailable", "Weather data is temporarily unavailable.")
        else:
            with self._lock:
                self._cache[cell] = (now, data)
            return WeatherResult(data, "ok")

        with self._lock:
            self._failed_until = now + self.failure_backoff_s
            self._last_failure = result
        return result


def build_weather_service(settings) -> WeatherService:
    if settings.weather_provider == "open-meteo":
        provider: Optional[WeatherProvider] = OpenMeteoProvider(
            settings.weather_base_url, settings.weather_api_key, settings.weather_timeout_s
        )
    elif settings.weather_provider == "none":
        provider = None
    else:
        logger.error("Unknown WEATHER_PROVIDER '%s'; weather disabled.", settings.weather_provider)
        provider = None
    return WeatherService(provider, settings.weather_cache_ttl_s, settings.weather_failure_backoff_s)
