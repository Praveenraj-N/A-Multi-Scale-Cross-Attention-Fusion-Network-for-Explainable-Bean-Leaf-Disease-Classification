import io
import json
import urllib.error
from datetime import datetime, timezone

import pytest

from backend.app.services.weather_service import OpenMeteoProvider, WeatherError, WeatherService
from backend.tests.conftest import FakeProvider

CURRENT_T = 1_780_000_000


def good_payload():
    hours = [CURRENT_T - 3600 * i for i in range(24, -1, -1)] + [CURRENT_T + 3600]
    return {
        "current": {"time": CURRENT_T, "temperature_2m": 24.5, "relative_humidity_2m": 80, "precipitation": 0.0,
                    "wind_speed_10m": 3.2, "wind_direction_10m": 140},
        "hourly": {"time": hours, "precipitation": [0.5] * len(hours)},
    }


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def provider_with(result):
    def opener(request, timeout):
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result if isinstance(result, bytes) else json.dumps(result).encode())

    return OpenMeteoProvider("https://example.test/v1/forecast", "secret-key", 2.0, opener=opener)


def test_parses_open_meteo_payload():
    w = provider_with(good_payload()).fetch(12.9, 77.6)
    assert w.kind == "current" and w.temperature_c == 24.5 and w.wind_speed_ms == 3.2 and w.wind_direction_deg == 140
    assert w.observed_at == datetime.fromtimestamp(CURRENT_T, tz=timezone.utc)
    assert w.rainfall_24h_mm == pytest.approx(12.0)  # 24 hours x 0.5 mm; the future hour is excluded


def test_partial_rain_history_gives_no_total_instead_of_a_wrong_one():
    payload = good_payload()
    payload["hourly"]["precipitation"][3] = None
    assert provider_with(payload).fetch(1, 1).rainfall_24h_mm is None


def test_request_url_uses_documented_parameters_and_key():
    p = provider_with(good_payload())
    url = p._url(12.9, 77.6)
    for part in ("current=temperature_2m", "past_hours=24", "wind_speed_unit=ms", "timeformat=unixtime", "apikey=secret-key"):
        assert part in url


@pytest.mark.parametrize(
    "failure,status",
    [
        (urllib.error.HTTPError("u", 429, "Too Many", {}, None), "rate_limited"),
        (urllib.error.HTTPError("u", 500, "Boom", {}, None), "network_error"),
        (urllib.error.URLError("no route"), "network_error"),
        (TimeoutError("timed out"), "timeout"),
        (urllib.error.URLError(TimeoutError("timed out")), "timeout"),
        (b"<html>not json</html>", "invalid_response"),
        ({"error": True, "reason": "bad"}, "invalid_response"),
        ({"current": {"temperature_2m": 1}}, "invalid_response"),
        ([], "invalid_response"),
    ],
)
def test_failures_become_typed_weather_errors(failure, status):
    with pytest.raises(WeatherError) as exc:
        provider_with(failure).fetch(1, 1)
    assert exc.value.status == status


def test_service_caches_per_cell_and_ttl():
    clock = [0.0]
    fake = FakeProvider()
    svc = WeatherService(fake, cache_ttl_s=100, clock=lambda: clock[0])
    assert svc.get(12.91, 77.61).status == "ok"
    assert svc.get(12.94, 77.64).status == "ok"  # same 0.1 degree cell
    assert fake.calls == 1
    clock[0] = 101
    svc.get(12.91, 77.61)
    assert fake.calls == 2


def test_service_never_raises_and_backs_off_after_failure():
    clock = [0.0]
    fake = FakeProvider()
    fake.error = ("timeout", "The weather provider timed out.")
    svc = WeatherService(fake, failure_backoff_s=60, clock=lambda: clock[0])
    r = svc.get(1, 1)
    assert r.data is None and r.status == "timeout"
    svc.get(5, 5)
    assert fake.calls == 1  # backoff: second call did not hit the provider
    clock[0] = 61
    fake.error = None
    assert svc.get(1, 1).status == "ok"


def test_unexpected_provider_bug_is_contained():
    class Broken(FakeProvider):
        def fetch(self, lat, lon):
            raise RuntimeError("secret internals")

    r = WeatherService(Broken()).get(1, 1)
    assert r.status == "unavailable" and "secret" not in r.message


def test_no_provider_reports_not_configured():
    r = WeatherService(None).get(1, 1)
    assert r.data is None and r.status == "not_configured"
