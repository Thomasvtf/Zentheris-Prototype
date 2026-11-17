"""S-01 · Seguridad: Error interno en cualquier endpoint.

Esperado: La respuesta no expone la excepción. Regla: Guía 3 §7.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

La app real (`create_app`) responde 500 con `{"mensaje", "detalles": null}` (sin `codigo`
mientras siga abierta la decisión #29) y registra la excepción en el log, nunca en la
respuesta: ni el texto, ni el tipo, ni la traza.
"""

import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.data import memberships as memberships_data
from app.errors import ERROR_DESCRIPTIONS
from app.main import API_PREFIX, create_app
from app.security.dependencies import CurrentMembership
from tests.helpers.auth import (
    auth_header,
    install_test_jwks,
    make_test_settings,
    make_token,
    override_db_session,
)
from tests.permissions.guarded_app import ADMIN_ID, HOGAR_ID

SECRET_DETAIL = "detalle-interno-que-no-debe-salir postgresql://usuario:clave@host/db"
INTERNAL_ERROR_BODY = {"mensaje": ERROR_DESCRIPTIONS[500], "detalles": None}


class InternalFailureError(RuntimeError):
    """Excepción interna con un nombre reconocible para comprobar que no se filtra."""


def _assert_does_not_leak(text: str) -> None:
    for fragment in (SECRET_DETAIL, "detalle-interno", "InternalFailureError", "RuntimeError",
                     "Traceback", "postgresql://", 'File "'):
        assert fragment not in text


@pytest.fixture
def real_app(settings: Settings) -> Iterator[FastAPI]:
    app = create_app(settings)

    def explode() -> None:
        raise InternalFailureError(SECRET_DETAIL)

    app.add_api_route(f"{API_PREFIX}/_prueba/falla", explode, methods=["GET"])
    yield app
    app.dependency_overrides.clear()


def test_unhandled_exception_returns_generic_500(real_app: FastAPI) -> None:
    response = TestClient(real_app, raise_server_exceptions=False).get(
        f"{API_PREFIX}/_prueba/falla"
    )
    assert response.status_code == 500
    assert response.json() == INTERNAL_ERROR_BODY
    _assert_does_not_leak(response.text)
    _assert_does_not_leak(str(response.headers))


def test_unhandled_exception_is_logged(
    real_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        TestClient(real_app, raise_server_exceptions=False).get(f"{API_PREFIX}/_prueba/falla")
    records = [r for r in caplog.records if r.name == "app.errors"]
    assert records, "el 500 debe quedar registrado en el log"
    assert records[0].exc_info is not None
    assert records[0].exc_info[0] is InternalFailureError


def test_dependency_failure_does_not_leak(
    monkeypatch: pytest.MonkeyPatch, real_app: FastAPI
) -> None:
    # La capa de datos falla (p. ej., la base cae) con un error interno que no debe salir.
    install_test_jwks(monkeypatch)

    def broken_get_active_membership(*_args: object) -> None:
        raise InternalFailureError(SECRET_DETAIL)

    monkeypatch.setattr(memberships_data, "get_active_membership", broken_get_active_membership)

    def needs_membership(member: CurrentMembership) -> dict[str, str]:
        return {"rol": member.rol}

    real_app.add_api_route(
        f"{API_PREFIX}/_prueba/hogares/{{hogar_id}}", needs_membership, methods=["GET"]
    )
    real_app.dependency_overrides[get_settings] = make_test_settings
    override_db_session(real_app)

    response = TestClient(real_app, raise_server_exceptions=False).get(
        f"{API_PREFIX}/_prueba/hogares/{HOGAR_ID}", headers=auth_header(make_token(ADMIN_ID))
    )

    assert response.status_code == 500
    assert response.json() == INTERNAL_ERROR_BODY
    _assert_does_not_leak(response.text)
