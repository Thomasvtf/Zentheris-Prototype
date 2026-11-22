"""Pruebas del formato de error {codigo, mensaje, detalles} (esquema `Error` del contrato).

Cubre los 3 códigos genéricos del contrato, con mensajes técnicos cortos (constantes
`*_MESSAGE`; `ERROR_DESCRIPTIONS` es solo para el OpenAPI): 401 `NO_AUTENTICADO` (con `WWW-Authenticate:
Bearer`, DC-44), 404 `NO_ENCONTRADO` (sin membresía, RN-I-03) y 500 `ERROR_INTERNO` (S-01:
nunca la excepción interna). DC-16: la app distingue los errores por `codigo`. Una ruta
inexistente también es 404 `NO_ENCONTRADO`; el 405 queda con la respuesta por defecto
(no hay `CodigoError` para él).
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app import errors
from app.errors import (
    INTERNAL_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
    UNAUTHORIZED_MESSAGE,
    ApiError,
    CodigoError,
    NotImplementedOperation,
    register_error_handlers,
)
from app.main import API_PREFIX
from tests.security.error_schema import assert_contract_error


class _Payload(BaseModel):
    nombre: str


def _app_with_test_routes() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/_prueba/api-error")
    def raise_api_error() -> None:
        raise ApiError(403, CodigoError.NO_ES_ADMINISTRADOR, "Solo el administrador.", {"x": 1})

    @app.get("/_prueba/no-autenticado")
    def raise_unauthorized() -> None:
        raise ApiError(
            401,
            CodigoError.NO_AUTENTICADO,
            UNAUTHORIZED_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/_prueba/no-encontrado")
    def raise_not_found() -> None:
        raise ApiError(404, CodigoError.NO_ENCONTRADO, NOT_FOUND_MESSAGE)

    @app.get("/_prueba/cabeceras")
    def raise_with_headers() -> None:
        raise ApiError(
            409, CodigoError.LIMITE_MIEMBROS, "Límite.", headers={"X-Prueba": "valor-de-prueba"}
        )

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
    assert_contract_error(response.json(), "NO_ES_ADMINISTRADOR")


def test_api_error_sends_headers() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/cabeceras")
    assert response.status_code == 409
    assert response.headers["X-Prueba"] == "valor-de-prueba"
    assert_contract_error(response.json(), "LIMITE_MIEMBROS", "Límite.")


def test_api_error_without_headers_sends_no_www_authenticate() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/api-error")
    assert "WWW-Authenticate" not in response.headers


def test_validation_error_returns_422_validacion() -> None:
    response = TestClient(_app_with_test_routes()).post(
        "/_prueba/validacion", json={"nombre": 123, "secreto": "no-debe-volver"}
    )
    body = response.json()
    assert response.status_code == 422
    assert_contract_error(body, "VALIDACION")
    assert body["detalles"]["campos"][0]["ubicacion"] == ["body", "nombre"]
    assert "no-debe-volver" not in response.text
    assert "123" not in response.text


def test_401_no_autenticado_has_www_authenticate() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/no-autenticado")
    assert response.status_code == 401
    assert response.json() == {
        "codigo": "NO_AUTENTICADO",
        "mensaje": UNAUTHORIZED_MESSAGE,
        "detalles": None,
    }
    assert_contract_error(response.json(), "NO_AUTENTICADO")
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_404_no_encontrado_without_www_authenticate() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/no-encontrado")
    assert response.status_code == 404
    assert response.json() == {
        "codigo": "NO_ENCONTRADO",
        "mensaje": NOT_FOUND_MESSAGE,
        "detalles": None,
    }
    assert_contract_error(response.json(), "NO_ENCONTRADO")
    assert "WWW-Authenticate" not in response.headers


def test_unexpected_exception_returns_500_error_interno_without_details() -> None:
    client = TestClient(_app_with_test_routes(), raise_server_exceptions=False)
    response = client.get("/_prueba/falla")
    assert response.status_code == 500
    assert response.json() == {
        "codigo": "ERROR_INTERNO",
        "mensaje": INTERNAL_ERROR_MESSAGE,
        "detalles": None,
    }
    assert_contract_error(response.json(), "ERROR_INTERNO")
    assert "division-interna-secreta" not in response.text
    assert "ZeroDivisionError" not in response.text
    assert "WWW-Authenticate" not in response.headers


def test_generic_messages_are_short_technical_texts() -> None:
    assert UNAUTHORIZED_MESSAGE == "Token ausente, inválido o vencido."
    assert NOT_FOUND_MESSAGE == "Recurso no encontrado."
    assert INTERNAL_ERROR_MESSAGE == "Error interno."


def test_unknown_route_returns_404_no_encontrado(client: TestClient) -> None:
    response = client.get(f"{API_PREFIX}/no-existe")
    assert response.status_code == 404
    assert response.json() == {
        "codigo": "NO_ENCONTRADO",
        "mensaje": NOT_FOUND_MESSAGE,
        "detalles": None,
    }
    assert_contract_error(response.json(), "NO_ENCONTRADO", NOT_FOUND_MESSAGE)


def test_unknown_route_outside_prefix_returns_404_no_encontrado(client: TestClient) -> None:
    response = client.get("/no-existe")
    assert response.status_code == 404
    assert_contract_error(response.json(), "NO_ENCONTRADO", NOT_FOUND_MESSAGE)


def test_method_not_allowed_keeps_default_405(client: TestClient) -> None:
    # TODO(pendiente: código de error para 405, no existe en CodigoError)
    response = client.delete(f"{API_PREFIX}/salud")
    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}
    assert "allow" in response.headers


def test_pending_code_error_no_longer_exists() -> None:
    for name in ("PendingCodeError", "_pending_code_response", "_handle_pending_code"):
        assert not hasattr(errors, name)


def test_not_implemented_operation_still_returns_501() -> None:
    response = TestClient(_app_with_test_routes()).get("/_prueba/no-implementada")
    assert response.status_code == 501
    assert response.json() == {"detail": "TODO(operacionDePrueba)"}
