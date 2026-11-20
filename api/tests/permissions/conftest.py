"""Fixtures de las pruebas de permisos: app con guardias, JWKS de prueba y membresías falsas."""

from collections.abc import Iterator
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.data.memberships import ActiveMembershipRow
from tests.helpers.auth import auth_header, install_fake_memberships, install_test_jwks, make_token
from tests.permissions.guarded_app import HOGAR_ID, CallRoute, build_guarded_app


@pytest.fixture
def guarded_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    """App con JWKS de prueba; limpia `dependency_overrides` al terminar."""
    install_test_jwks(monkeypatch)
    app = build_guarded_app()
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def call(guarded_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> CallRoute:
    """Llama a una ruta de `/hogares/{hogar_id}` como `user_id`, con las membresías dadas.

    `token=""` envía la petición sin cabecera `Authorization`.
    """
    client = TestClient(guarded_app)

    def _call(
        method: str,
        path: str,
        *,
        user_id: UUID,
        rows: list[ActiveMembershipRow],
        hogar_id: UUID = HOGAR_ID,
        token: str | None = None,
    ) -> httpx.Response:
        install_fake_memberships(monkeypatch, rows)
        if token == "":
            headers = {}
        else:
            headers = auth_header(token or make_token(user_id))
        return client.request(method, f"/hogares/{hogar_id}{path}", headers=headers)

    return _call
