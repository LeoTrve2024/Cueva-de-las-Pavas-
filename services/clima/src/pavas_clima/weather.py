"""Consulta de Open-Meteo, normalización y caché local por aplicación."""

import asyncio
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from time import monotonic
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

from pavas_clima.config import Settings
from pavas_clima.schemas import (
    CurrentResponse,
    ForecastDay,
    ForecastResponse,
)
from pavas_clima.repository import WeatherRepository

LIMA = ZoneInfo("America/Lima")
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 3600
REQUEST_TIMEOUT_SECONDS = 5
logger = logging.getLogger(__name__)


class WeatherUnavailableError(Exception):
    """No hay datos vigentes o falta configurar la ubicación."""


def local_now() -> datetime:
    return datetime.now(LIMA)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, str)}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _code(value: object) -> int | None:
    number = _number(value)
    if number is None or not number.is_integer() or number < 0:
        return None
    return int(number)


def _date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        result = date.fromisoformat(value)
    except ValueError:
        return None
    return result if result.isoformat() == value else None


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        result = result.replace(tzinfo=LIMA)
    try:
        return result.astimezone(LIMA)
    except (ValueError, OverflowError):
        return None


def _item(values: object, index: int) -> object:
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


def _availability(
    fields: dict[str, object],
) -> tuple[Literal["disponible", "sin_datos"], str | None]:
    missing = [name for name, value in fields.items() if value is None]
    if missing:
        return "sin_datos", f"Datos ausentes o inválidos: {', '.join(missing)}."
    return "disponible", None


@dataclass(frozen=True)
class WeatherSnapshot:
    current: CurrentResponse
    forecast: ForecastResponse
    horizon_start: date
    fetched_at: float


def _normalize(payload: object, queried_at: datetime, fetched_at: float) -> WeatherSnapshot:
    data = _mapping(payload)
    current = _mapping(data.get("current"))
    daily = _mapping(data.get("daily"))
    current_time = _timestamp(current.get("time"))
    raw_dates = daily.get("time")
    indices: dict[date, int] = {}
    duplicates: set[date] = set()
    if isinstance(raw_dates, list):
        for index, raw_date in enumerate(raw_dates):
            day = _date(raw_date)
            if day is not None:
                if day in indices:
                    duplicates.add(day)
                indices[day] = index
    for day in duplicates:
        del indices[day]
    if current_time is None and not indices:
        raise WeatherUnavailableError(
            "Open-Meteo devolvió una respuesta sin fechas interpretables."
        )

    query_id = uuid4()
    temperature = _number(current.get("temperature_2m"))
    code = _code(current.get("weather_code"))
    state, reason = _availability(
        {"momento_dato": current_time, "temperatura": temperature, "codigo_clima": code}
    )
    current_response = CurrentResponse(
        consulta_clima_id=query_id,
        consultado_en=queried_at,
        momento_dato=current_time,
        temperatura=temperature,
        codigo_clima=code,
        estado=state,
        motivo=reason,
    )
    days: list[ForecastDay] = []
    for offset in range(7):
        day = queried_at.date() + timedelta(days=offset)
        day_index = indices.get(day)

        def value(variable: str, index: int | None = day_index) -> object:
            return None if index is None else _item(daily.get(variable), index)

        rain = _number(value("precipitation_probability_max"))
        if rain is not None and not 0 <= rain <= 100:
            rain = None
        minimum = _number(value("temperature_2m_min"))
        maximum = _number(value("temperature_2m_max"))
        if minimum is not None and maximum is not None and minimum > maximum:
            minimum = maximum = None
        daily_code = _code(value("weather_code"))
        state, reason = _availability(
            {
                "lluvia_pct": rain,
                "temperatura_min": minimum,
                "temperatura_max": maximum,
                "codigo_clima": daily_code,
            }
        )
        days.append(
            ForecastDay(
                fecha=day,
                lluvia_pct=rain,
                temperatura_min=minimum,
                temperatura_max=maximum,
                codigo_clima=daily_code,
                estado=state,
                motivo=reason,
            )
        )
    return WeatherSnapshot(
        current=current_response,
        forecast=ForecastResponse(consulta_clima_id=query_id, consultado_en=queried_at, dias=days),
        horizon_start=queried_at.date(),
        fetched_at=fetched_at,
    )


class WeatherService:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], float] | None = None,
        repository: WeatherRepository | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._clock = clock or local_now
        self._monotonic = monotonic_clock or monotonic
        self._snapshot: WeatherSnapshot | None = None
        self._lock = asyncio.Lock()
        self._repository = repository

    def _cached(self, now: datetime) -> WeatherSnapshot | None:
        snapshot = self._snapshot
        if (
            snapshot is not None
            and snapshot.horizon_start == now.date()
            and 0 <= self._monotonic() - snapshot.fetched_at < CACHE_SECONDS
        ):
            return snapshot
        return None

    async def get_snapshot(self) -> WeatherSnapshot:
        if self._settings.latitude is None or self._settings.longitude is None:
            raise WeatherUnavailableError(
                "Configura CLIMA_LATITUDE y CLIMA_LONGITUDE con las coordenadas verificadas "
                "del balneario."
            )
        now = self._clock().astimezone(LIMA)
        cached = self._cached(now)
        if cached is not None:
            return cached
        async with self._lock:
            now = self._clock().astimezone(LIMA)
            cached = self._cached(now)
            if cached is not None:
                return cached
            fetched_at = self._monotonic()
            payload = await self._fetch(self._settings.latitude, self._settings.longitude)
            snapshot = _normalize(payload, now, fetched_at)
            if self._repository is not None:
                self._repository.save_snapshot(snapshot, self._settings.latitude, self._settings.longitude, payload)
            self._snapshot = snapshot
            return snapshot

    async def _fetch(self, latitude: float, longitude: float) -> object:
        params: dict[str, str | float | int] = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "America/Lima",
            "forecast_days": 7,
            "temperature_unit": "celsius",
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_min,temperature_2m_max,weather_code,"
            "precipitation_probability_max",
        }
        for attempt in range(2):
            try:
                # También limitar la duración total, no solo la inactividad de la red.
                async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                    response = await self._client.get(
                        FORECAST_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
                    )
                response.raise_for_status()
            except (httpx.TransportError, TimeoutError) as exc:
                logger.warning("Fallo de transporte de Open-Meteo (intento %s).", attempt + 1)
                if attempt == 0:
                    continue
                raise WeatherUnavailableError(
                    "Open-Meteo no está disponible temporalmente."
                ) from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                logger.warning("Open-Meteo respondió HTTP %s (intento %s).", status, attempt + 1)
                if attempt == 0 and (status == 429 or status >= 500):
                    continue
                raise WeatherUnavailableError(
                    "Open-Meteo no está disponible temporalmente."
                ) from exc
            try:
                payload: object = response.json()
            except ValueError as exc:
                raise WeatherUnavailableError(
                    "Open-Meteo devolvió una respuesta JSON inválida."
                ) from exc
            return payload
        raise AssertionError("Los intentos de consulta deben retornar o lanzar un error.")
