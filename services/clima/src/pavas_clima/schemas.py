"""Contratos públicos del servicio Clima; temperaturas en °C y lluvia en %."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

FiniteTemperature = Annotated[float, Field(allow_inf_nan=False)]
RainProbability = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class WeatherMetadata(BaseModel):
    lugar: Literal["Cueva de las Pavas"] = "Cueva de las Pavas"
    zona_horaria: Literal["America/Lima"] = "America/Lima"
    proveedor: Literal["open-meteo"] = "open-meteo"
    atribucion: Literal["https://open-meteo.com/"] = "https://open-meteo.com/"
    consulta_clima_id: UUID
    consultado_en: AwareDatetime


class CurrentResponse(WeatherMetadata):
    momento_dato: AwareDatetime | None
    temperatura: FiniteTemperature | None = Field(description="Temperatura actual en °C.")
    codigo_clima: int | None = Field(description="Código meteorológico WMO del proveedor.")
    estado: Literal["disponible", "sin_datos"]
    motivo: str | None


class ForecastDay(BaseModel):
    fecha: date
    lluvia_pct: RainProbability | None = Field(description="Probabilidad máxima de lluvia en %.")
    temperatura_min: FiniteTemperature | None = Field(description="Temperatura mínima en °C.")
    temperatura_max: FiniteTemperature | None = Field(description="Temperatura máxima en °C.")
    codigo_clima: int | None = Field(description="Código meteorológico WMO del proveedor.")
    estado: Literal["disponible", "sin_datos"]
    motivo: str | None


class ForecastResponse(WeatherMetadata):
    dias: list[ForecastDay] = Field(min_length=7, max_length=7)


class ErrorResponse(BaseModel):
    detail: str
