"""S-04 · Seguridad: Fallo no previsto en cualquier endpoint.

Esperado: 500 `ERROR_INTERNO` sin exponer la excepción. Regla: contrato
(`components.responses.ErrorServidor`), Guía 3 §7.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Sobre la app real (`create_app`): una ruta sin hogar, una ruta protegida por membresía y la
capa de datos fallando. El cuerpo es siempre `{"codigo": "ERROR_INTERNO", "mensaje":
INTERNAL_ERROR_MESSAGE, "detalles": null}` (esquema `Error`), sin texto, tipo ni traza de la
excepción, y sin `WWW-Authenticate`. La excepción va al log (ver también S-01).
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.data import memberships as memberships_data
from app.errors import INTERNAL_ERROR_MESSAGE
from app.main import API_PREFIX, create_app
from app.security.dependencies import CurrentMembership, CurrentUser
from tests.helpers.auth import (
    ADMIN_ID,
    HOGAR_ID,
    auth_header,
    install_test_jwks,
    make_test_settings,
    make_token,
    override_db_session,
)
from tests.security.error_schema import assert_contract_error

SECRET_DETAIL = "fallo-no-previsto-secreto"
INTERNAL_ERROR_BODY = {
    "codigo": "ERROR_INTERNO",
    "mensaje": INTERNAL_ERROR_MESSAGE,
    "detalles": None,
}
LEAK_FRAGMENTS = (SECRET_DETAIL, "UnexpectedFailureError", "LookupError", "Traceback", 'File "')


class UnexpectedFailureError(LookupError):
    """Fallo no previsto con un nombre reconocible para comprobar que no se filtra."""


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Iterator[FastAPI]:
    install_test_jwks(monkeypatch)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = make_test_settings
    override_db_session(app)

    def public_failure() -> None:
        raise UnexpectedFailureError(SECRET_DETAIL)

    def user_failure(_user: CurrentUser) -> None:
        raise UnexpectedFailureError(SECRET_DETAIL)

    def household_failure(_member: CurrentMembership) -> None:
        raise AssertionError("no debe llegar: la capa de datos falla antes")

    app.add_api_route(f"{API_PREFIX}/_prueba/s04", public_failure, methods=["GET"])
    app.add_api_route(f"{API_PREFIX}/_prueba/s04/usuario", user_failure, methods=["POST"])
    app.add_api_route(
        f"{API_PREFIX}/_prueba/s04/hogares/{{hogar_id}}", household_failure, methods=["GET"]
    )

    def broken_get_active_membership(*_args: object) -> None:
        raise UnexpectedFailureError(SECRET_DETAIL)

    monkeypatch.setattr(memberships_data, "get_active_membership", broken_get_active_membership)
    yield app
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("GET", "/_prueba/s04", id="ruta-publica"),
        pytest.param("POST", "/_prueba/s04/usuario", id="ruta-autenticada"),
        pytest.param("GET", f"/_prueba/s04/hogares/{HOGAR_ID}", id="falla-la-capa-de-datos"),
    ],
)
def test_unexpected_failure_is_500_error_interno(app: FastAPI, method: str, path: str) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    response = client.request(
        method, f"{API_PREFIX}{path}", headers=auth_header(make_token(ADMIN_ID))
    )
    assert response.status_code == 500
    assert response.json() == INTERNAL_ERROR_BODY
    assert_contract_error(response.json(), "ERROR_INTERNO", INTERNAL_ERROR_MESSAGE)
    assert "WWW-Authenticate" not in response.headers
    for fragment in LEAK_FRAGMENTS:
        assert fragment not in response.text
        assert fragment not in str(response.headers)
