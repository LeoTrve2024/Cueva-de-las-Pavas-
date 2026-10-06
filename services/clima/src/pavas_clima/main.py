"""Punto de entrada ASGI del servicio Clima."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from pavas_clima.config import Settings
from pavas_clima.schemas import CurrentResponse, ErrorResponse, ForecastResponse
from pavas_clima.repository import WeatherRepository
from pavas_clima.weather import WeatherService, WeatherSnapshot, WeatherUnavailableError


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["clima"] = "clima"


def create_app(
    *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    settings = settings if settings is not None else Settings()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(transport=transport) as client:
            repository = None
            if settings.database_url and settings.environment != "test":
                try:
                    repository = WeatherRepository(settings.database_url)
                except Exception:
                    logging.getLogger(__name__).exception("No se pudo inicializar PostgreSQL para Clima.")
            app.state.weather_repository = repository
            app.state.weather = WeatherService(settings, client, repository=repository)
            yield

    app = FastAPI(title="Pavas · Clima", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health(request: Request, response: Response) -> HealthResponse:
        """Disponibilidad del servicio y, cuando aplica, conexión a PostgreSQL."""
        repository = getattr(request.app.state, "weather_repository", None)
        if repository is not None and not repository.health():
            response.status_code = 503
        return HealthResponse()

    async def snapshot(request: Request) -> WeatherSnapshot:
        service: WeatherService = request.app.state.weather
        try:
            return await service.get_snapshot()
        except WeatherUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get(
        "/api/v1/clima/actual",
        response_model=CurrentResponse,
        responses={503: {"model": ErrorResponse}},
        tags=["clima"],
    )
    async def current(request: Request) -> CurrentResponse:
        """Clima actual modelado; momento del dato y temperaturas en °C."""
        return (await snapshot(request)).current

    @app.get(
        "/api/v1/clima/pronostico",
        response_model=ForecastResponse,
        responses={503: {"model": ErrorResponse}},
        tags=["clima"],
    )
    async def forecast(request: Request) -> ForecastResponse:
        """Siete fechas desde hoy en Lima; temperaturas en °C y lluvia en %."""
        return (await snapshot(request)).forecast

    return app
