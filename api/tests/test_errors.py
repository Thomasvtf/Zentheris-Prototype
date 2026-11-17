"""Pruebas del formato de error {codigo, mensaje, detalles}.

También el tratamiento provisional de 401, 404 (sin membresía) y 500 con `PendingCodeError`
mientras siga abierta la decisión #29 (cuerpo sin `codigo`; S-01: nunca la excepción interna).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import (
    ERROR_DESCRIPTIONS,
    ApiError,
    CodigoError,
    NotImplementedOperation,
    PendingCodeError,
    register_error_handlers,
)


class _Payload(BaseModel):
    nombre: str


def _app_with_test_routes() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/_prueba/api-error")
    def raise_api_error() -> None:
        raise ApiError(403, CodigoError.NO_ES_ADMINISTRADOR, "Solo el administrador.", {"x": 1})

    @app.get("/_prueba/pendiente/{status_code}")
    def raise_pending(status_code: int) -> None:
        raise PendingCodeError(status_code)

    @app.get("/_prueba/no-implementada")
    def raise_not_implemented() -> None:
        raise NotImplementedOperation("operacionDePrueba")

    @app.get("/_prueba/falla")
    def raise_unexpected() -> None:
        raise ZeroDivisionError("division-interna-secreta")

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


def test_pending_401_has_description_and_www_authenticate() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/pendiente/401")
    assert response.status_code == 401
    assert response.json() == {"mensaje": ERROR_DESCRIPTIONS[401], "detalles": None}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_pending_404_has_description_without_codigo() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/pendiente/404")
    assert response.status_code == 404
    assert response.json() == {"mensaje": ERROR_DESCRIPTIONS[404], "detalles": None}
    assert "WWW-Authenticate" not in response.headers


def test_pending_500_has_description_without_codigo() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/pendiente/500")
    assert response.status_code == 500
    assert response.json() == {"mensaje": ERROR_DESCRIPTIONS[500], "detalles": None}


@pytest.mark.parametrize("status_code", [400, 403, 409, 422, 501])
def test_pending_code_error_only_accepts_401_404_500(status_code: int) -> None:
    with pytest.raises(ValueError):
        PendingCodeError(status_code)


def test_unexpected_exception_returns_500_without_details() -> None:
    client = TestClient(_app_with_test_routes(), raise_server_exceptions=False)
    response = client.get("/_prueba/falla")
    assert response.status_code == 500
    assert response.json() == {"mensaje": ERROR_DESCRIPTIONS[500], "detalles": None}
    assert "division-interna-secreta" not in response.text
    assert "ZeroDivisionError" not in response.text


def test_not_implemented_operation_still_returns_501() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/no-implementada")
    assert response.status_code == 501
    assert response.json() == {"detail": "TODO(operacionDePrueba)"}
