"""Pruebas de GET /api/v1/salud (operationId obtenerSalud)."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_get_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/salud")
    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}


def test_old_routes_are_removed(client: TestClient) -> None:
    for path in ("/", "/salud", "/salud/bd"):
        assert client.get(path).status_code == 404


def test_app_starts_without_environment_variables() -> None:
    app = create_app(Settings(_env_file=None))
    assert TestClient(app).get("/api/v1/salud").status_code == 200
