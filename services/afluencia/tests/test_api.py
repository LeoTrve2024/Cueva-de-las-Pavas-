from datetime import datetime

import httpx
from fastapi.testclient import TestClient

from pavas_afluencia.config import Settings
from pavas_afluencia.main import create_app


def climate_payload() -> dict[str, object]:
    return {
        "lugar": "Cueva de las Pavas",
        "zona_horaria": "America/Lima",
        "proveedor": "open-meteo",
        "atribucion": "https://open-meteo.com/",
        "consulta_clima_id": "11111111-1111-1111-1111-111111111111",
        "consultado_en": datetime(2026, 10, 6, 10, 0).isoformat() + "-05:00",
        "dias": [
            {"fecha": f"2026-10-{6+i:02d}", "lluvia_pct": 20, "temperatura_min": 20,
             "temperatura_max": 28, "codigo_clima": 1, "estado": "disponible", "motivo": None}
            for i in range(7)
        ],
    }


def test_forecast_uses_document_rule() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=climate_payload())

    settings = Settings(_env_file=None, environment="test", clima_url="http://clima")
    with TestClient(create_app(settings=settings, transport=httpx.MockTransport(handler))) as client:
        response = client.get("/api/v1/afluencia/pronostico")
    assert response.status_code == 200
    body = response.json()
    assert len(body["dias"]) == 7
    assert body["dias"][0]["puntuacion"] in {88, 68}
    assert body["dias"][0]["factores"]["lluvia_pct"] == 20
