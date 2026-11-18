"""Pruebas del formato de error {codigo, mensaje, detalles}."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import ApiError, CodigoError, register_error_handlers


class _Payload(BaseModel):
    nombre: str


def _app_with_test_routes() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/_prueba/api-error")
    def raise_api_error() -> None:
        raise ApiError(403, CodigoError.NO_ES_ADMINISTRADOR, "Solo el administrador.", {"x": 1})

    @app.post("/_prueba/validacion")
    def validate(payload: _Payload) -> dict[str, str]:
        return {"nombre": payload.nombre}

    return app


def test_api_error_has_contract_format() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/api-error")
    assert response.status_code == 403
    assert response.json() == {
        "codigo": "NO_ES_ADMINISTRADOR",
        "mensaje": "Solo el administrador.",
        "detalles": {"x": 1},
    }


def test_validation_error_returns_422_validacion() -> None:
    response = TestClient(_app_with_test_routes()).post(
        "/_prueba/validacion", json={"nombre": 123, "secreto": "no-debe-volver"}
    )
    body = response.json()
    assert response.status_code == 422
    assert body["codigo"] == "VALIDACION"
    assert set(body) == {"codigo", "mensaje", "detalles"}
    assert body["detalles"]["campos"][0]["ubicacion"] == ["body", "nombre"]
    assert "no-debe-volver" not in response.text
    assert "123" not in response.text
