from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi.testclient import TestClient

from pavas_afluencia.config import Settings
from pavas_afluencia.main import create_app
from pavas_afluencia.schemas import VisitorRecord
from pavas_afluencia.service import build_comparison

AUTH = ("admin", "admin")
LIMA = ZoneInfo("America/Lima")
TODAY = datetime.now(LIMA).date()


class FakeRepository:
    def __init__(self) -> None:
        self.saved: dict[date, tuple[int, str | None]] = {}

    def upsert_visitors(self, day: date, visitors: int, note: str | None) -> VisitorRecord:
        self.saved[day] = (visitors, note)
        return VisitorRecord(fecha=day, visitantes=visitors, nota=note,
                             registrado_en=datetime(2026, 10, 6, 12, 0, tzinfo=LIMA))

    def visitor_rows(self, start: date, end: date) -> list[dict[str, Any]]:
        return [{"fecha": d, "visitantes": v, "nota": n, "puntuacion": 88, "nivel": "alta"}
                for d, (v, n) in self.saved.items() if start <= d <= end]


def make_client() -> tuple[TestClient, FakeRepository]:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    settings = Settings(_env_file=None, environment="test", clima_url="http://clima")
    client = TestClient(create_app(settings=settings, transport=httpx.MockTransport(handler)))
    return client, FakeRepository()


def test_build_comparison_summary() -> None:
    rows = [
        {"fecha": date(2026, 10, 3), "visitantes": 250, "nota": None,
         "puntuacion": 88, "nivel": "alta"},
        {"fecha": date(2026, 10, 4), "visitantes": 340, "nota": None,
         "puntuacion": 88, "nivel": "alta"},
        {"fecha": date(2026, 10, 5), "visitantes": 100, "nota": "cierre parcial",
         "puntuacion": None, "nivel": None},
    ]
    result = build_comparison(rows)
    assert [item.visitas_estimadas for item in result.resultados] == [300, 300, None]
    assert [item.diferencia for item in result.resultados] == [50, -40, None]
    assert result.resumen.dias_comparados == 2
    assert result.resumen.error_absoluto_medio == 45.0
    assert result.resumen.sesgo_medio == 5.0


def test_build_comparison_without_rows() -> None:
    result = build_comparison([])
    assert result.resultados == []
    assert result.resumen.error_absoluto_medio is None


def test_register_requires_credentials() -> None:
    client, _ = make_client()
    with client:
        response = client.put(f"/api/v1/afluencia/visitantes/{TODAY}", json={"visitantes": 120})
    assert response.status_code == 401


def test_register_and_compare() -> None:
    client, repo = make_client()
    with client:
        client.app.state.service.repository = repo  # type: ignore[attr-defined]
        put = client.put(f"/api/v1/afluencia/visitantes/{TODAY}", auth=AUTH,
                         json={"visitantes": 280, "nota": "feriado local"})
        assert put.status_code == 200
        assert put.json()["visitantes"] == 280
        got = client.get("/api/v1/afluencia/comparacion", auth=AUTH,
                         params={"desde": str(TODAY), "hasta": str(TODAY)})
    assert got.status_code == 200
    body = got.json()
    assert body["resultados"][0]["visitas_estimadas"] == 300
    assert body["resultados"][0]["diferencia"] == 20
    assert body["resumen"]["dias_comparados"] == 1


def test_register_rejects_future_date_and_negative_values() -> None:
    client, repo = make_client()
    with client:
        client.app.state.service.repository = repo  # type: ignore[attr-defined]
        future = client.put(f"/api/v1/afluencia/visitantes/{TODAY + timedelta(days=1)}", auth=AUTH,
                            json={"visitantes": 10})
        negative = client.put(f"/api/v1/afluencia/visitantes/{TODAY}", auth=AUTH,
                              json={"visitantes": -1})
    assert future.status_code == 422
    assert negative.status_code == 422
    assert repo.saved == {}


def test_register_without_database_is_503() -> None:
    client, _ = make_client()
    with client:
        response = client.put(f"/api/v1/afluencia/visitantes/{TODAY}", auth=AUTH,
                              json={"visitantes": 10})
    assert response.status_code == 503


def test_compare_validates_range() -> None:
    client, repo = make_client()
    with client:
        client.app.state.service.repository = repo  # type: ignore[attr-defined]
        reversed_range = client.get("/api/v1/afluencia/comparacion", auth=AUTH,
                                    params={"desde": "2026-10-05", "hasta": "2026-10-01"})
        too_long = client.get("/api/v1/afluencia/comparacion", auth=AUTH,
                              params={"desde": "2024-01-01", "hasta": "2026-01-01"})
    assert reversed_range.status_code == 422
    assert too_long.status_code == 422
