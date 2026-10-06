"""Regla explicable de afluencia y consumo del servicio Clima."""
import asyncio
import math
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx

from pavas_afluencia.config import Settings
from pavas_afluencia.repository import AfluenciaRepository
from pavas_afluencia.schemas import DayResult, FactorResponse, ForecastResponse, HistoryItem

LIMA = ZoneInfo("America/Lima")


class AfluenciaUnavailableError(Exception):
    """El servicio Clima o la persistencia no están disponibles."""


def score(rain: float, factor_day: int) -> int:
    return math.floor((0.6 * (100 - rain) + 0.4 * factor_day) + 0.5)


def level(value: int) -> str:
    if value <= 39:
        return "baja"
    if value <= 69:
        return "media"
    return "alta"


def day_factor(day: date) -> int:
    return 100 if day.weekday() >= 5 else 50


class AfluenciaService:
    def __init__(self, settings: Settings, client: httpx.AsyncClient,
                 repository: AfluenciaRepository | None = None) -> None:
        self.settings = settings
        self.client = client
        self.repository = repository

    async def _climate_forecast(self) -> dict[str, Any]:
        try:
            async with asyncio.timeout(5):
                response = await self.client.get(
                    f"{self.settings.clima_url.rstrip('/')}/api/v1/clima/pronostico",
                    timeout=5,
                )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get("dias"), list):
                raise AfluenciaUnavailableError("La respuesta de Clima no tiene el formato esperado.")
            return data
        except (httpx.HTTPError, TimeoutError, ValueError) as exc:
            raise AfluenciaUnavailableError("El servicio Clima no está disponible temporalmente.") from exc

    async def forecast(self) -> ForecastResponse:
        climate = await self._climate_forecast()
        consulta_id = UUID(str(climate["consulta_clima_id"]))
        calculated_at = datetime.now(LIMA)
        if self.repository is not None:
            cached = self.repository.find_execution(consulta_id, self.settings.rules_version)
            if cached is not None and len(cached) == 7:
                days = [
                    DayResult(
                        fecha=item.fecha_objetivo, estado=item.estado, puntuacion=item.puntuacion,
                        nivel=item.nivel, factores=FactorResponse(lluvia_pct=item.lluvia_pct, factor_dia=item.factor_dia)
                        if item.lluvia_pct is not None else None,
                        explicacion=item.motivo, version_reglas=item.version_reglas,
                    ) for item in cached
                ]
                return ForecastResponse(consulta_clima_id=consulta_id,
                    consultado_en=climate["consultado_en"], calculado_en=cached[0].calculado_en,
                    version_reglas=self.settings.rules_version, dias=days)

        days: list[DayResult] = []
        for raw in climate["dias"][:7]:
            target = date.fromisoformat(str(raw["fecha"]))
            rain = raw.get("lluvia_pct")
            factor = day_factor(target)
            if raw.get("estado") != "disponible" or rain is None or not isinstance(rain, (int, float)):
                days.append(DayResult(fecha=target, estado="sin_estimacion", puntuacion=None,
                    nivel=None, factores=None,
                    explicacion=str(raw.get("motivo") or "Falta la probabilidad de lluvia."),
                    version_reglas=self.settings.rules_version))
                continue
            rain = float(rain)
            if not 0 <= rain <= 100:
                days.append(DayResult(fecha=target, estado="sin_estimacion", puntuacion=None,
                    nivel=None, factores=FactorResponse(lluvia_pct=rain, factor_dia=factor), explicacion="La probabilidad de lluvia está fuera de rango.",
                    version_reglas=self.settings.rules_version))
                continue
            value = score(rain, factor)
            days.append(DayResult(fecha=target, estado="disponible", puntuacion=value, nivel=level(value),
                factores=FactorResponse(lluvia_pct=rain, factor_dia=factor),
                explicacion=f"Lluvia {rain:g} % y {'fin de semana' if factor == 100 else 'día laborable'}",
                version_reglas=self.settings.rules_version))

        execution_id = uuid4()
        if self.repository is not None:
            self.repository.save_execution(execution_id, consulta_id, calculated_at, self.settings.rules_version, days)
        return ForecastResponse(consulta_clima_id=consulta_id, consultado_en=climate["consultado_en"],
            calculado_en=calculated_at, version_reglas=self.settings.rules_version, dias=days)
