import pytest
from fastapi.testclient import TestClient

from pavas_clima.main import create_app


def test_app_starts_with_its_own_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIMA_ENVIRONMENT", "test")
    monkeypatch.setenv("AFLUENCIA_ENVIRONMENT", "production")
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "clima"}
        assert app.state.settings.environment == "test"
