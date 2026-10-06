"""Persistencia del servicio Clima en su esquema exclusivo."""
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

SCHEMA = "clima"


class WeatherRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, pool_pre_ping=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clima.consultas (
                    id UUID PRIMARY KEY,
                    consultado_en TIMESTAMPTZ NOT NULL,
                    latitud NUMERIC NOT NULL,
                    longitud NUMERIC NOT NULL,
                    zona_horaria TEXT NOT NULL,
                    proveedor TEXT NOT NULL,
                    respuesta_json JSONB NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clima.pronosticos (
                    consulta_id UUID NOT NULL REFERENCES clima.consultas(id) ON DELETE CASCADE,
                    fecha_objetivo DATE NOT NULL,
                    lluvia_pct NUMERIC,
                    temperatura_min NUMERIC,
                    temperatura_max NUMERIC,
                    codigo_clima INTEGER,
                    PRIMARY KEY (consulta_id, fecha_objetivo),
                    CHECK (lluvia_pct IS NULL OR (lluvia_pct >= 0 AND lluvia_pct <= 100))
                )
            """))

    def save_snapshot(self, snapshot: object, latitude: float, longitude: float, payload: object) -> None:
        # Importación local evita acoplar el repositorio a los modelos de transporte.
        from pavas_clima.weather import WeatherSnapshot
        if not isinstance(snapshot, WeatherSnapshot):
            raise TypeError("snapshot inválido")
        query_id: UUID = snapshot.forecast.consulta_clima_id
        queried_at: datetime = snapshot.forecast.consultado_en
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO clima.consultas
                    (id, consultado_en, latitud, longitud, zona_horaria, proveedor, respuesta_json)
                    VALUES (:id, :consultado_en, :latitud, :longitud, 'America/Lima', 'open-meteo', CAST(:payload AS JSONB))
                """),
                {"id": query_id, "consultado_en": queried_at, "latitud": latitude,
                 "longitud": longitude, "payload": json.dumps(payload)},
            )
            for day in snapshot.forecast.dias:
                conn.execute(
                    text("""
                        INSERT INTO clima.pronosticos
                        (consulta_id, fecha_objetivo, lluvia_pct, temperatura_min, temperatura_max, codigo_clima)
                        VALUES (:id, :fecha, :rain, :min, :max, :code)
                    """),
                    {"id": query_id, "fecha": day.fecha, "rain": day.lluvia_pct,
                     "min": day.temperatura_min, "max": day.temperatura_max, "code": day.codigo_clima},
                )

    def health(self) -> bool:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
