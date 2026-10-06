"""Persistencia exclusiva del servicio Afluencia."""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from pavas_afluencia.schemas import DayResult, HistoryItem


class AfluenciaRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, pool_pre_ping=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS afluencia.ejecuciones (
                    id UUID PRIMARY KEY,
                    consulta_clima_id UUID NOT NULL,
                    calculado_en TIMESTAMPTZ NOT NULL,
                    version_reglas TEXT NOT NULL,
                    UNIQUE (consulta_clima_id, version_reglas)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS afluencia.resultados (
                    id UUID PRIMARY KEY,
                    ejecucion_id UUID NOT NULL REFERENCES afluencia.ejecuciones(id) ON DELETE CASCADE,
                    fecha_objetivo DATE NOT NULL,
                    lluvia_pct NUMERIC,
                    factor_dia INTEGER NOT NULL,
                    puntuacion INTEGER,
                    nivel TEXT,
                    estado TEXT NOT NULL,
                    motivo TEXT NOT NULL,
                    UNIQUE (ejecucion_id, fecha_objetivo),
                    CHECK (puntuacion IS NULL OR (puntuacion >= 0 AND puntuacion <= 100))
                )
            """))

    def find_execution(self, consulta_clima_id: UUID, version: str) -> list[HistoryItem] | None:
        with self.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT r.id, e.consulta_clima_id, e.calculado_en, r.fecha_objetivo,
                       r.lluvia_pct, r.factor_dia, r.puntuacion, r.nivel,
                       r.estado, r.motivo, e.version_reglas
                FROM afluencia.resultados r
                JOIN afluencia.ejecuciones e ON e.id = r.ejecucion_id
                WHERE e.consulta_clima_id = :cid AND e.version_reglas = :version
                ORDER BY r.fecha_objetivo
            """), {"cid": consulta_clima_id, "version": version}).mappings().all()
        if not rows:
            return None
        return [HistoryItem(**dict(row)) for row in rows]

    def save_execution(self, execution_id: UUID, consulta_clima_id: UUID, calculated_at: datetime,
                       version: str, days: list[DayResult]) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO afluencia.ejecuciones (id, consulta_clima_id, calculado_en, version_reglas)
                VALUES (:id, :cid, :calculated_at, :version)
                ON CONFLICT (consulta_clima_id, version_reglas) DO NOTHING
            """), {"id": execution_id, "cid": consulta_clima_id,
                   "calculated_at": calculated_at, "version": version})
            for day in days:
                import uuid
                conn.execute(text("""
                    INSERT INTO afluencia.resultados
                    (id, ejecucion_id, fecha_objetivo, lluvia_pct, factor_dia, puntuacion, nivel, estado, motivo)
                    VALUES (:id, :eid, :fecha, :rain, :factor, :score, :level, :state, :reason)
                    ON CONFLICT (ejecucion_id, fecha_objetivo) DO NOTHING
                """), {"id": uuid.uuid4(), "eid": execution_id, "fecha": day.fecha,
                       "rain": day.factores.lluvia_pct if day.factores else None,
                       "factor": day.factores.factor_dia if day.factores else 50,
                       "score": day.puntuacion, "level": day.nivel,
                       "state": day.estado, "reason": day.explicacion})

    def history(self, start: date, end: date, page: int) -> tuple[int, list[HistoryItem]]:
        offset = (page - 1) * 20
        with self.engine.connect() as conn:
            total = conn.execute(text("""
                SELECT count(*) FROM afluencia.resultados
                WHERE fecha_objetivo BETWEEN :start AND :end
            """), {"start": start, "end": end}).scalar_one()
            rows = conn.execute(text("""
                SELECT r.id, e.consulta_clima_id, e.calculado_en, r.fecha_objetivo,
                       r.lluvia_pct, r.factor_dia, r.puntuacion, r.nivel,
                       r.estado, r.motivo, e.version_reglas
                FROM afluencia.resultados r
                JOIN afluencia.ejecuciones e ON e.id = r.ejecucion_id
                WHERE r.fecha_objetivo BETWEEN :start AND :end
                ORDER BY r.fecha_objetivo DESC, e.calculado_en DESC
                LIMIT 20 OFFSET :offset
            """), {"start": start, "end": end, "offset": offset}).mappings().all()
        return int(total), [HistoryItem(**dict(row)) for row in rows]

    def health(self) -> bool:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
