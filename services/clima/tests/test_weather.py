"""Pruebas deterministas de la integración; las coordenadas son ficticias."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pavas_clima import weather
from pavas_clima.config import Settings
from pavas_clima.main import create_app
from pavas_clima.weather import LIMA, WeatherService

ACTUAL = "/api/v1/clima/actual"
FORECAST = "/api/v1/clima/pronostico"


@dataclass
class Clock:
    current: datetime = datetime(2026, 10, 1, 12, tzinfo=LIMA)
    elapsed: float = 0

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return self.elapsed


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    result = Clock()
    monkeypatch.setattr(weather, "local_now", result.now)
    monkeypatch.setattr(weather, "monotonic", result.monotonic)
    return result


def settings() -> Settings:
    return Settings(_env_file=None, latitude=-10, longitude=-75)


def payload(clock: Clock) -> dict[str, object]:
    local = clock.current.astimezone(LIMA)
    return {
        "current": {
            "time": local.replace(tzinfo=None).isoformat(),
            "temperature_2m": 24.5,
            "weather_code": 3,
        },
        "daily": {
            "time": [(local.date() + timedelta(days=i)).isoformat() for i in range(7)],
            "temperature_2m_min": [19.0] * 7,
            "temperature_2m_max": [29.0] * 7,
            "weather_code": [3] * 7,
            "precipitation_probability_max": [20, 0, 100, 15, 30, 45, 60],
        },
    }


def section(data: dict[str, object], name: str) -> dict[str, object]:
    result = data[name]
    assert isinstance(result, dict)
    return result


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
    return TestClient(create_app(settings=settings(), transport=httpx.MockTransport(handler)))


def test_routes_share_query_and_send_expected_parameters(clock: Clock) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload(clock))

    with client_for(handler) as client:
        actual = client.get(ACTUAL)
        forecast = client.get(FORECAST)
        assert actual.status_code == forecast.status_code == 200
        current = actual.json()
        weekly = forecast.json()
        assert current["consulta_clima_id"] == weekly["consulta_clima_id"]
        UUID(current["consulta_clima_id"])
        assert current["consultado_en"] == "2026-10-01T12:00:00-05:00"
        assert current["momento_dato"] == "2026-10-01T12:00:00-05:00"
        assert current["lugar"] == "Cueva de las Pavas"
        assert current["zona_horaria"] == "America/Lima"
        assert current["proveedor"] == "open-meteo"
        assert current["atribucion"] == "https://open-meteo.com/"
        assert current["temperatura"] == 24.5
        assert current["codigo_clima"] == 3
        assert current["estado"] == "disponible"
        assert current["motivo"] is None
        assert len(weekly["dias"]) == 7
        assert weekly["dias"][0] == {
            "fecha": "2026-10-01",
            "lluvia_pct": 20,
            "temperatura_min": 19,
            "temperatura_max": 29,
            "codigo_clima": 3,
            "estado": "disponible",
            "motivo": None,
        }
        assert weekly["dias"][1]["lluvia_pct"] == 0
        assert weekly["dias"][2]["lluvia_pct"] == 100
        assert len(requests) == 1
        assert requests[0].url.host == "api.open-meteo.com"
        assert requests[0].url.path == "/v1/forecast"
        assert dict(requests[0].url.params) == {
            "latitude": "-10.0",
            "longitude": "-75.0",
            "timezone": "America/Lima",
            "forecast_days": "7",
            "temperature_unit": "celsius",
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_min,temperature_2m_max,weather_code,"
            "precipitation_probability_max",
        }
        assert requests[0].extensions["timeout"]["read"] == 5


@pytest.mark.parametrize("start", ["2026-01-29", "2026-12-29", "2028-02-27"])
def test_seven_local_dates_across_calendar_boundaries(clock: Clock, start: str) -> None:
    clock.current = datetime.fromisoformat(f"{start}T23:55:00-05:00")
    with client_for(lambda _: httpx.Response(200, json=payload(clock))) as client:
        response = client.get(FORECAST)
        assert response.status_code == 200
        assert [day["fecha"] for day in response.json()["dias"]] == [
            (clock.current.date() + timedelta(days=i)).isoformat() for i in range(7)
        ]


def test_horizon_uses_lima_date_instead_of_utc(clock: Clock) -> None:
    clock.current = datetime.fromisoformat("2026-10-02T00:30:00+00:00")
    with client_for(lambda _: httpx.Response(200, json=payload(clock))) as client:
        result = client.get(FORECAST).json()
        assert result["dias"][0]["fecha"] == "2026-10-01"
        assert result["dias"][0]["estado"] == "disponible"
        assert result["consultado_en"] == "2026-10-01T19:30:00-05:00"


@pytest.mark.parametrize("invalid", [None, -1, 101, "20", True, "NaN"])
def test_invalid_rain_preserves_date_and_other_values(clock: Clock, invalid: object) -> None:
    data = payload(clock)
    section(data, "daily")["precipitation_probability_max"] = [invalid]
    with client_for(lambda _: httpx.Response(200, json=data)) as client:
        response = client.get(FORECAST)
        assert response.status_code == 200
        days = response.json()["dias"]
        assert len(days) == 7
        for day in days:
            assert day["lluvia_pct"] is None
            assert day["estado"] == "sin_datos"
            assert "lluvia_pct" in day["motivo"]
            assert day["temperatura_min"] == 19
            assert day["codigo_clima"] == 3


def test_incomplete_arrays_and_missing_dates_keep_seven_days(clock: Clock) -> None:
    data = payload(clock)
    daily = section(data, "daily")
    daily["time"] = ["2026-10-03", "invalid", "2026-10-01"]
    daily["precipitation_probability_max"] = [40]
    daily["temperature_2m_min"] = [21, 22, 18]
    daily.pop("weather_code")
    with client_for(lambda _: httpx.Response(200, json=data)) as client:
        days = client.get(FORECAST).json()["dias"]
        assert len(days) == 7
        assert days[0]["temperatura_min"] == 18
        assert days[0]["lluvia_pct"] is None
        assert days[1]["temperatura_min"] is None
        assert days[2]["lluvia_pct"] == 40
        assert days[2]["codigo_clima"] is None
        assert days[3]["estado"] == "sin_datos"


@pytest.mark.parametrize("missing_section", ["current", "daily"])
def test_missing_section_returns_partial_response(clock: Clock, missing_section: str) -> None:
    data = payload(clock)
    data.pop(missing_section)
    with client_for(lambda _: httpx.Response(200, json=data)) as client:
        current = client.get(ACTUAL)
        forecast = client.get(FORECAST)
        assert current.status_code == forecast.status_code == 200
        if missing_section == "current":
            assert current.json()["estado"] == "sin_datos"
            assert current.json()["momento_dato"] is None
            assert forecast.json()["dias"][0]["estado"] == "disponible"
        else:
            assert current.json()["estado"] == "disponible"
            assert all(day["estado"] == "sin_datos" for day in forecast.json()["dias"])


def test_current_timestamp_offset_and_invalid_fields(clock: Clock) -> None:
    data = payload(clock)
    current = section(data, "current")
    current.update(time="2026-10-01T17:00:00Z", temperature_2m="24", weather_code=1.5)
    with client_for(lambda _: httpx.Response(200, json=data)) as client:
        result = client.get(ACTUAL).json()
        assert result["momento_dato"] == "2026-10-01T12:00:00-05:00"
        assert result["temperatura"] is None
        assert result["codigo_clima"] is None
        assert result["estado"] == "sin_datos"


def test_duplicate_dates_and_inverted_temperatures_are_unavailable(clock: Clock) -> None:
    data = payload(clock)
    daily = section(data, "daily")
    daily["time"] = ["2026-10-01", "2026-10-01", "2026-10-03"]
    daily["temperature_2m_min"] = [19, 19, 35]
    with client_for(lambda _: httpx.Response(200, json=data)) as client:
        days = client.get(FORECAST).json()["dias"]
        assert days[0]["lluvia_pct"] is None
        assert days[2]["temperatura_min"] is None
        assert days[2]["temperatura_max"] is None
        assert days[2]["lluvia_pct"] == 100


@pytest.mark.parametrize("renewal", ["expiry", "midnight"])
def test_cache_renews_at_expiry_or_local_midnight(clock: Clock, renewal: str) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload(clock))

    with client_for(handler) as client:
        first = client.get(FORECAST).json()
        clock.elapsed = 3599
        assert client.get(ACTUAL).json()["consulta_clima_id"] == first["consulta_clima_id"]
        if renewal == "expiry":
            clock.elapsed = 3600
        else:
            clock.current += timedelta(days=1)
        second = client.get(FORECAST).json()
        assert second["consulta_clima_id"] != first["consulta_clima_id"]
        assert second["dias"][0]["fecha"] == clock.current.date().isoformat()
        assert len(requests) == 2


def test_concurrent_renewals_make_one_request(clock: Clock) -> None:
    async def scenario() -> None:
        requests = 0

        async def handler(_: httpx.Request) -> httpx.Response:
            nonlocal requests
            requests += 1
            await asyncio.sleep(0)
            return httpx.Response(200, json=payload(clock))

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = WeatherService(settings(), client)
            for _ in range(2):
                snapshots = await asyncio.gather(*(service.get_snapshot() for _ in range(8)))
                assert len({item.current.consulta_clima_id for item in snapshots}) == 1
                clock.elapsed += 3600
            assert requests == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["timeout", "connection", "deadline", "429", "500", "503"])
def test_transient_failure_retries_once(clock: Clock, failure: str) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("simulated", request=request)
            if failure == "connection":
                raise httpx.ConnectError("simulated", request=request)
            if failure == "deadline":
                raise TimeoutError("simulated")
            return httpx.Response(int(failure))
        return httpx.Response(200, json=payload(clock))

    with client_for(handler) as client:
        assert client.get(FORECAST).status_code == 200
        assert attempts == 2


def test_total_deadline_cancels_request_and_retries_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(weather, "REQUEST_TIMEOUT_SECONDS", 0.01)
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        await asyncio.Event().wait()
        raise AssertionError("La solicitud debería cancelarse al superar el plazo.")

    with TestClient(
        create_app(settings=settings(), transport=httpx.MockTransport(handler))
    ) as client:
        assert client.get(FORECAST).status_code == 503
        assert attempts == 2


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_provider_numbers_are_returned_as_null(number: str) -> None:
    content = (
        f'{{"current":{{"time":"2026-10-01T12:00","temperature_2m":{number},"weather_code":3}}}}'
    ).encode()
    with client_for(lambda _: httpx.Response(200, content=content)) as client:
        response = client.get(ACTUAL)
        assert response.status_code == 200
        assert response.json()["temperatura"] is None
        assert response.json()["codigo_clima"] == 3
        assert response.json()["estado"] == "sin_datos"


@pytest.mark.parametrize("status,expected_attempts", [(400, 1), (404, 1), (429, 2), (500, 2)])
def test_http_failure_returns_503(status: int, expected_attempts: int) -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status)

    with client_for(handler) as client:
        response = client.get(FORECAST)
        assert response.status_code == 503
        assert "Open-Meteo" in response.json()["detail"]
        assert attempts == expected_attempts
        assert client.get("/health").status_code == 200


def test_transport_failure_does_not_cache_an_error(clock: Clock) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise httpx.ConnectError("simulated", request=request)
        return httpx.Response(200, json=payload(clock))

    with client_for(handler) as client:
        assert client.get(ACTUAL).status_code == 503
        assert client.get(ACTUAL).status_code == 200
        assert attempts == 3


@pytest.mark.parametrize(
    "malformed", [b"not json", b"null", b"[]", b"{}", b'{"daily":{"time":["bad"]}}']
)
def test_malformed_response_is_not_retried(malformed: bytes) -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, content=malformed)

    with client_for(handler) as client:
        assert client.get(ACTUAL).status_code == 503
        assert attempts == 1


def test_expired_cache_is_not_served_when_provider_fails(clock: Clock) -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json=payload(clock)) if attempts == 1 else httpx.Response(503)

    with client_for(handler) as client:
        assert client.get(FORECAST).status_code == 200
        clock.elapsed = 3599
        assert client.get(FORECAST).status_code == 200
        assert attempts == 1
        clock.elapsed = 3600
        assert client.get(FORECAST).status_code == 503
        assert attempts == 3


@pytest.mark.parametrize("latitude,longitude", [(None, None), (-10, None), (None, -75)])
def test_missing_coordinates_keep_health_and_docs_working(
    latitude: float | None, longitude: float | None
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("No debe consultar al proveedor sin coordenadas.")

    configuration = Settings(_env_file=None, latitude=latitude, longitude=longitude)
    with TestClient(
        create_app(settings=configuration, transport=httpx.MockTransport(handler))
    ) as client:
        assert client.get("/health").json() == {"status": "ok", "service": "clima"}
        assert client.get("/docs").status_code == 200
        for route in [ACTUAL, FORECAST]:
            response = client.get(route)
            assert response.status_code == 503
            assert "CLIMA_LATITUDE y CLIMA_LONGITUDE" in response.json()["detail"]
        schema = client.get("/openapi.json").json()
        assert "503" in schema["paths"][ACTUAL]["get"]["responses"]
        assert "ForecastResponse" in schema["components"]["schemas"]


@pytest.mark.parametrize(
    "variable,value",
    [("latitude", "91"), ("latitude", "nan"), ("longitude", "-181"), ("longitude", "inf")],
)
def test_coordinate_configuration_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(f"CLIMA_{variable.upper()}", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_coordinates_load_from_service_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIMA_LATITUDE", "-10")
    monkeypatch.setenv("CLIMA_LONGITUDE", "-75")
    configuration = Settings(_env_file=None)
    assert configuration.latitude == -10
    assert configuration.longitude == -75


def test_cache_is_isolated_between_apps(clock: Clock) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload(clock))

    with client_for(handler) as first_client, client_for(handler) as second_client:
        first = first_client.get(ACTUAL).json()
        second = second_client.get(ACTUAL).json()
        assert first["consulta_clima_id"] != second["consulta_clima_id"]
        assert len(requests) == 2
