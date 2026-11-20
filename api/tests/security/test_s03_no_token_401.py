"""S-03 · Seguridad: Llamada protegida sin token, con token inválido o vencido.

Esperado: 401 `NO_AUTENTICADO`. Regla: contrato (`components.responses.NoAutenticado`), RN-I-01.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Sobre la app real (`create_app`), con el JWKS de prueba y una sesión falsa: sin base, sin red
y sin secretos. El usuario SÍ es administrador del hogar: el rechazo es solo por el token.
Cada respuesta lleva `WWW-Authenticate: Bearer` (DC-44) y valida contra el esquema `Error`.
El detalle por cada operación del contrato está en `tests/e2e/test_security_e2e.py`.
"""

from collections.abc import Iterator

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.config import get_settings
from app.errors import UNAUTHORIZED_MESSAGE
from app.main import API_PREFIX, create_app
from tests.helpers.auth import (
    ADMIN_ID,
    HOGAR_ID,
    TEST_KEY_ID,
    auth_header,
    install_fake_memberships,
    install_test_jwks,
    make_membership_row,
    make_test_settings,
    make_token,
    override_db_session,
)
from tests.security.error_schema import assert_contract_error

UNAUTHORIZED_BODY = {"codigo": "NO_AUTENTICADO", "mensaje": UNAUTHORIZED_MESSAGE, "detalles": None}

# Una operación protegida sin hogar y otras con hogar (guardias de membresía y permiso).
PROTECTED_CALLS = (
    ("GET", "/usuarios/me"),
    ("GET", f"/hogares/{HOGAR_ID}/consumo/actual"),
    ("GET", f"/hogares/{HOGAR_ID}/historial?periodo=dia"),
    ("GET", f"/hogares/{HOGAR_ID}/miembros"),
)


def _token_signed_by_foreign_key() -> str:
    """Token con claims válidos, pero firmado por una clave que el JWKS no publica."""
    claims = jwt.decode(make_token(ADMIN_ID), options={"verify_signature": False})
    foreign_key = ec.generate_private_key(ec.SECP256R1())
    return jwt.encode(claims, foreign_key, algorithm="ES256", headers={"kid": TEST_KEY_ID})


INVALID_HEADERS = {
    "sin-token": {},
    "bearer-vacio": {"Authorization": "Bearer"},
    "basura": auth_header("no-es-un-jwt"),
    "vencido": auth_header(make_token(ADMIN_ID, expired=True)),
    "otra-clave": auth_header(_token_signed_by_foreign_key()),
    "alg-none": auth_header(make_token(ADMIN_ID, algorithm="none")),
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    install_test_jwks(monkeypatch)
    install_fake_memberships(
        monkeypatch, [make_membership_row(ADMIN_ID, HOGAR_ID, rol="administrador")]
    )
    app = create_app(make_test_settings())
    app.dependency_overrides[get_settings] = make_test_settings
    override_db_session(app)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("case", sorted(INVALID_HEADERS))
@pytest.mark.parametrize(("method", "path"), PROTECTED_CALLS)
def test_protected_call_without_valid_token_is_401(
    client: TestClient, method: str, path: str, case: str
) -> None:
    response = client.request(method, f"{API_PREFIX}{path}", headers=INVALID_HEADERS[case])
    assert response.status_code == 401, (response.status_code, response.text)
    assert response.json() == UNAUTHORIZED_BODY
    assert_contract_error(response.json(), "NO_AUTENTICADO", UNAUTHORIZED_MESSAGE)
    assert response.headers["WWW-Authenticate"] == "Bearer"
