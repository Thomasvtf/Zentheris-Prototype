"""Autenticación de prueba: claves EC en memoria, tokens firmados y membresías falsas.

Ninguna clave ni token real: el par EC P-256 se genera al importar este módulo y el
secreto HS256 es una cadena de prueba que solo existe aquí. Sin red: `install_test_jwks`
reemplaza `get_jwks_client` por un `PyJWKClient` que nunca sale a internet.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from jwt.algorithms import ECAlgorithm

from app.config import Settings
from app.data import memberships as memberships_data
from app.data.database import get_session
from app.data.memberships import ActiveMembershipRow
from app.security import jwt as jwt_module

TEST_SUPABASE_URL = "https://proyecto-de-prueba.supabase.co"
TEST_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"
TEST_JWKS_URL = f"{TEST_ISSUER}/.well-known/jwks.json"
TEST_KEY_ID = "clave-de-prueba"
# Solo para pruebas del modo HS256 (DC-44, respaldo sin JWKS). No es un secreto real.
TEST_JWT_SECRET = "secreto-hs256-solo-para-pruebas-sin-valor-real-0123456789"

# Ids fijos de las pruebas de seguridad (hogar, hogar ajeno y personas).
HOGAR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_HOGAR_ID = UUID("22222222-2222-4222-8222-222222222222")
ADMIN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MEMBER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
OUTSIDER_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")

TEST_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
TEST_PUBLIC_JWK: dict[str, Any] = {
    **ECAlgorithm.to_jwk(TEST_PRIVATE_KEY.public_key(), as_dict=True),
    "kid": TEST_KEY_ID,
    "alg": "ES256",
    "use": "sig",
}


def make_test_settings() -> Settings:
    """Configuración con la URL de Supabase y el JWKS de prueba, sin leer `.env`."""
    return Settings(_env_file=None, SUPABASE_URL=TEST_SUPABASE_URL, SUPABASE_JWKS_URL=TEST_JWKS_URL)


def install_test_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reemplaza `get_jwks_client` por un cliente que sirve la clave pública de prueba."""
    client = jwt.PyJWKClient(TEST_JWKS_URL, cache_jwk_set=False)
    monkeypatch.setattr(client, "fetch_data", lambda: {"keys": [TEST_PUBLIC_JWK]})
    monkeypatch.setattr(jwt_module, "get_jwks_client", lambda _url: client)


def make_token(
    user_id: UUID,
    email: str | None = "persona@example.com",
    *,
    expired: bool = False,
    issuer: str | None = None,
    audience: str = "authenticated",
    algorithm: str = "ES256",
    **extra_claims: Any,
) -> str:
    """Token como los de Supabase Auth, firmado con la clave de prueba.

    `algorithm`: "ES256" (clave EC de prueba), "HS256" (`TEST_JWT_SECRET`) o "none"
    (sin firma). `email=None` omite el claim; un `extra_claims` con valor `None` también
    omite ese claim (por ejemplo, `exp=None`).
    """
    now = datetime.now(UTC)
    exp = now - timedelta(minutes=5) if expired else now + timedelta(hours=1)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "aud": audience,
        "iss": issuer or TEST_ISSUER,
        "iat": int((now - timedelta(hours=2 if expired else 0)).timestamp()),
        "exp": int(exp.timestamp()),
        "role": "authenticated",
    }
    claims.update(extra_claims)
    claims = {name: value for name, value in claims.items() if value is not None}
    headers = {"kid": TEST_KEY_ID}
    if algorithm == "ES256":
        return jwt.encode(claims, TEST_PRIVATE_KEY, algorithm="ES256", headers=headers)
    if algorithm == "HS256":
        return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256", headers=headers)
    if algorithm == "none":
        return jwt.encode(claims, None, algorithm="none", headers=headers)
    raise ValueError(f"Algoritmo de prueba no soportado: {algorithm}")


def auth_header(token: str) -> dict[str, str]:
    """Cabecera `Authorization: Bearer <token>`."""
    return {"Authorization": f"Bearer {token}"}


def make_membership_row(
    usuario_id: UUID,
    hogar_id: UUID,
    *,
    rol: str = "miembro",
    ver_consumo_actual: bool = True,
    ver_historial: bool = True,
    recibir_alertas: bool = True,
    modificar_metas: bool = False,
    membresia_id: UUID | None = None,
) -> ActiveMembershipRow:
    """Fila activa de membresía; por defecto, los permisos por defecto de un hogar."""
    return ActiveMembershipRow(
        membresia_id=membresia_id or UUID(int=usuario_id.int ^ hogar_id.int),
        hogar_id=hogar_id,
        usuario_id=usuario_id,
        rol=rol,  # type: ignore[arg-type]
        permiso_ver_consumo_actual=ver_consumo_actual,
        permiso_ver_historial=ver_historial,
        permiso_recibir_alertas=recibir_alertas,
        permiso_modificar_metas=modificar_metas,
    )


def install_fake_memberships(
    monkeypatch: pytest.MonkeyPatch, rows: list[ActiveMembershipRow]
) -> None:
    """Reemplaza `get_active_membership` por una búsqueda en `rows` (solo filas activas)."""

    def fake_get_active_membership(
        _session: object, usuario_id: UUID, hogar_id: UUID
    ) -> ActiveMembershipRow | None:
        return next(
            (row for row in rows if row.usuario_id == usuario_id and row.hogar_id == hogar_id),
            None,
        )

    monkeypatch.setattr(memberships_data, "get_active_membership", fake_get_active_membership)


class FakeSession:
    """Sesión falsa: cualquier uso falla, para que ninguna prueba toque una base real."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"FakeSession no admite `{name}`: reemplaza la función de datos.")


def override_db_session(app: FastAPI) -> None:
    """Hace que `get_session` entregue una `FakeSession` (limpiar con `dependency_overrides`)."""

    def fake_session() -> Iterator[FakeSession]:
        yield FakeSession()

    app.dependency_overrides[get_session] = fake_session
