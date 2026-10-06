"""Contratos HTTP del servicio Afluencia."""
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class FactorResponse(BaseModel):
    lluvia_pct: float | None
    factor_dia: int


class DayResult(BaseModel):
    fecha: date
    estado: Literal["disponible", "sin_estimacion"]
    puntuacion: int | None = Field(default=None, ge=0, le=100)
    nivel: Literal["baja", "media", "alta"] | None = None
    factores: FactorResponse | None = None
    explicacion: str
    version_reglas: str


class ForecastResponse(BaseModel):
    lugar: Literal["Cueva de las Pavas"] = "Cueva de las Pavas"
    zona_horaria: Literal["America/Lima"] = "America/Lima"
    consulta_clima_id: UUID
    consultado_en: AwareDatetime
    calculado_en: AwareDatetime
    version_reglas: str
    dias: list[DayResult] = Field(min_length=7, max_length=7)


class HistoryItem(BaseModel):
    id: UUID
    consulta_clima_id: UUID
    calculado_en: AwareDatetime
    fecha_objetivo: date
    lluvia_pct: float | None
    factor_dia: int
    puntuacion: int | None
    nivel: Literal["baja", "media", "alta"] | None
    estado: Literal["disponible", "sin_estimacion"]
    motivo: str
    version_reglas: str


class HistoryResponse(BaseModel):
    pagina: int
    tamano_pagina: int = 20
    total: int
    resultados: list[HistoryItem]


class ErrorResponse(BaseModel):
    detail: str
