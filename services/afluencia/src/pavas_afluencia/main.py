"""Punto de entrada ASGI del servicio Afluencia."""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from pavas_afluencia.config import Settings
from pavas_afluencia.repository import AfluenciaRepository
from pavas_afluencia.schemas import (
    ComparisonResponse,
    ErrorResponse,
    ForecastResponse,
    HistoryResponse,
    VisitorRecord,
    VisitorRecordIn,
)
from pavas_afluencia.service import (
    LIMA,
    AfluenciaService,
    AfluenciaUnavailableError,
    build_comparison,
)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["afluencia"] = "afluencia"


security = HTTPBasic()


def create_app(*, settings: Settings | None = None,
               transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(transport=transport) as client:
            repository = None
            if settings.database_url and settings.environment != "test":
                try:
                    repository = AfluenciaRepository(settings.database_url)
                except Exception:
                    logging.getLogger(__name__).exception("No se pudo inicializar PostgreSQL para Afluencia.")
            app.state.service = AfluenciaService(settings, client, repository)
            yield

    app = FastAPI(title="Pavas · Afluencia", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health(request: Request, response: Response) -> HealthResponse:
        repository = getattr(request.app.state.service, "repository", None)
        if repository is not None and not repository.health():
            response.status_code = 503
        return HealthResponse()

    async def service(request: Request) -> AfluenciaService:
        return request.app.state.service

    def admin(credentials: HTTPBasicCredentials = Depends(security)) -> None:
        if credentials.username != settings.admin_user or credentials.password != settings.admin_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Credenciales inválidas.",
                                headers={"WWW-Authenticate": "Basic"})

    @app.get("/api/v1/afluencia/pronostico", response_model=ForecastResponse,
             responses={503: {"model": ErrorResponse}}, tags=["afluencia"])
    async def forecast(svc: AfluenciaService = Depends(service)) -> ForecastResponse:
        try:
            return await svc.forecast()
        except AfluenciaUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/afluencia/historial", response_model=HistoryResponse,
             responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}, tags=["afluencia"])
    def history(request: Request, desde: date = Query(...), hasta: date = Query(...),
                pagina: int = Query(1, ge=1), _: None = Depends(admin)) -> HistoryResponse:
        if desde > hasta:
            raise HTTPException(status_code=422, detail="desde no puede ser posterior a hasta.")
        repository: AfluenciaRepository | None = getattr(request.app.state.service, "repository", None)
        if repository is None:
            return HistoryResponse(pagina=pagina, resultados=[], total=0)
        total, rows = repository.history(desde, hasta, pagina)
        return HistoryResponse(pagina=pagina, resultados=rows, total=total)

    def repository_or_503(request: Request) -> AfluenciaRepository:
        repository: AfluenciaRepository | None = getattr(request.app.state.service, "repository", None)
        if repository is None:
            raise HTTPException(status_code=503, detail="La base de datos no está disponible.")
        return repository

    @app.put("/api/v1/afluencia/visitantes/{fecha}", response_model=VisitorRecord,
             responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
                        503: {"model": ErrorResponse}}, tags=["visitantes"])
    def register_visitors(fecha: date, body: VisitorRecordIn, request: Request,
                          _: None = Depends(admin)) -> VisitorRecord:
        if fecha > datetime.now(LIMA).date():
            raise HTTPException(
                status_code=422,
                detail="No se pueden registrar visitantes de una fecha futura.",
            )
        return repository_or_503(request).upsert_visitors(fecha, body.visitantes, body.nota)

    @app.get("/api/v1/afluencia/comparacion", response_model=ComparisonResponse,
             responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
                        503: {"model": ErrorResponse}}, tags=["visitantes"])
    def compare(request: Request, desde: date = Query(...), hasta: date = Query(...),
                _: None = Depends(admin)) -> ComparisonResponse:
        if desde > hasta:
            raise HTTPException(status_code=422, detail="desde no puede ser posterior a hasta.")
        if (hasta - desde).days > 366:
            raise HTTPException(status_code=422, detail="El rango no puede superar 366 días.")
        return build_comparison(repository_or_503(request).visitor_rows(desde, hasta))

    return app
