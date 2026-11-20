"""Validación del token de Supabase Auth y dependencia `current_user`.

Reglas: DC-44 (firmas públicas por JWKS; HS256 con `SUPABASE_JWT_SECRET` solo si no hay
JWKS), RN-I-03 (el usuario sale del claim `sub`). Algoritmos explícitos: nunca `alg=none`
ni HS256 cuando se valida por JWKS. Sin red: el JWKS es una clave EC generada en memoria.
DC-16: un token inválido es 401 (sesión vencida); una falla de infraestructura
(configuración faltante o JWKS caído) es 500 (error del servidor), sin exponer nada.
"""

import base64
import hashlib
import hmac
import json
from collections.abc import Callable, Iterator
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.errors import INTERNAL_ERROR_MESSAGE, UNAUTHORIZED_MESSAGE, register_error_handlers
from app.security import jwt as jwt_module
from app.security.dependencies import CurrentUser
from app.security.jwt import (
    ASYMMETRIC_ALGORITHMS,
    AUDIENCE,
    AuthUnavailableError,
    InvalidTokenError,
    validate_jwt,
)
from tests.helpers.auth import (
    TEST_ISSUER,
    TEST_JWT_SECRET,
    TEST_KEY_ID,
    TEST_PRIVATE_KEY,
    TEST_SUPABASE_URL,
    auth_header,
    install_test_jwks,
    make_test_settings,
    make_token,
)
from tests.security.error_schema import assert_contract_error

USER_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
UNAUTHORIZED_BODY = {
    "codigo": "NO_AUTENTICADO",
    "mensaje": UNAUTHORIZED_MESSAGE,
    "detalles": None,
}
INTERNAL_ERROR_BODY = {
    "codigo": "ERROR_INTERNO",
    "mensaje": INTERNAL_ERROR_MESSAGE,
    "detalles": None,
}
MISSING_CONFIGURATIONS = [
    pytest.param(Settings(_env_file=None), id="sin-nada"),
    pytest.param(Settings(_env_file=None, SUPABASE_URL=TEST_SUPABASE_URL), id="sin-claves"),
    pytest.param(
        Settings(_env_file=None, SUPABASE_JWT_SECRET=TEST_JWT_SECRET), id="sin-supabase-url"
    ),
]


class BrokenJwksClient:
    """JWKS caído: la consulta de la clave falla por red."""

    def get_signing_key_from_jwt(self, _token: str) -> jwt.PyJWK:
        raise jwt.PyJWKClientConnectionError("sin red: detalle-de-red-interno")


@pytest.fixture
def jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    install_test_jwks(monkeypatch)


def hs256_settings() -> Settings:
    """Modo de respaldo de DC-44: sin JWKS, con secreto HS256."""
    return Settings(
        _env_file=None, SUPABASE_URL=TEST_SUPABASE_URL, SUPABASE_JWT_SECRET=TEST_JWT_SECRET
    )


def foreign_token() -> str:
    """Token bien formado y con el `kid` de prueba, pero firmado con otra clave EC."""
    other_key = ec.generate_private_key(ec.SECP256R1())
    claims = jwt.decode(make_token(USER_ID), options={"verify_signature": False})
    return jwt.encode(claims, other_key, algorithm="ES256", headers={"kid": TEST_KEY_ID})


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def tampered_token() -> str:
    """Token válido al que se le cambia el `sub` sin volver a firmarlo."""
    header, _payload, signature = make_token(USER_ID).split(".")
    other_payload = make_token(UUID(int=1)).split(".")[1]
    return f"{header}.{other_payload}.{signature}"


# --- validate_jwt ---------------------------------------------------------------------


def test_constants_follow_dc44() -> None:
    assert ASYMMETRIC_ALGORITHMS == ("ES256", "RS256")
    assert AUDIENCE == "authenticated"


@pytest.mark.usefixtures("jwks")
def test_valid_token_returns_claims() -> None:
    claims = validate_jwt(make_token(USER_ID, "ana@example.com"), make_test_settings())
    assert claims["sub"] == str(USER_ID)
    assert claims["email"] == "ana@example.com"
    assert claims["iss"] == TEST_ISSUER
    assert claims["aud"] == "authenticated"


@pytest.mark.usefixtures("jwks")
def test_issuer_ignores_trailing_slash_in_supabase_url() -> None:
    settings = make_test_settings().model_copy(update={"supabase_url": TEST_SUPABASE_URL + "/"})
    assert validate_jwt(make_token(USER_ID), settings)["iss"] == TEST_ISSUER


@pytest.mark.usefixtures("jwks")
@pytest.mark.parametrize(
    "token_factory",
    [
        pytest.param(foreign_token, id="firma-con-otra-clave"),
        pytest.param(lambda: make_token(USER_ID, expired=True), id="vencido"),
        pytest.param(
            lambda: make_token(USER_ID, issuer="https://otro.supabase.co/auth/v1"),
            id="emisor-incorrecto",
        ),
        pytest.param(lambda: make_token(USER_ID, audience="anon"), id="audiencia-incorrecta"),
        pytest.param(lambda: make_token(USER_ID, algorithm="none"), id="alg-none"),
        pytest.param(lambda: make_token(USER_ID, algorithm="HS256"), id="hs256-con-jwks"),
        pytest.param(lambda: make_token(USER_ID, exp=None), id="sin-exp"),
        pytest.param(lambda: make_token(USER_ID, sub=None), id="sin-sub"),
        pytest.param(lambda: make_token(USER_ID, aud=None), id="sin-aud"),
        pytest.param(tampered_token, id="contenido-alterado"),
        pytest.param(lambda: "no-es-un-jwt", id="basura"),
    ],
)
def test_invalid_tokens_are_rejected(token_factory: Callable[[], str]) -> None:
    with pytest.raises(InvalidTokenError):
        validate_jwt(token_factory(), make_test_settings())


@pytest.mark.usefixtures("jwks")
def test_hs256_signed_with_public_key_is_rejected_with_jwks() -> None:
    # Confusión de algoritmo: HS256 firmado con la clave pública (PEM) como secreto.
    public_pem = TEST_PRIVATE_KEY.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    )
    # PyJWT no deja firmar así; se arma a mano, como lo haría un atacante.
    _header, payload, _signature = make_token(USER_ID).split(".")
    header = _b64url(json.dumps({"alg": "HS256", "kid": TEST_KEY_ID, "typ": "JWT"}).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = _b64url(hmac.new(public_pem, signing_input, hashlib.sha256).digest())
    token = f"{header}.{payload}.{signature}"
    with pytest.raises(InvalidTokenError):
        validate_jwt(token, make_test_settings())


def test_jwks_network_error_is_auth_unavailable(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Infraestructura, no token: no debe tratarse como InvalidTokenError (401).
    monkeypatch.setattr(jwt_module, "get_jwks_client", lambda _url: BrokenJwksClient())
    token = make_token(USER_ID)
    with pytest.raises(AuthUnavailableError):
        validate_jwt(token, make_test_settings())
    assert not issubclass(AuthUnavailableError, InvalidTokenError)
    assert "PyJWKClientConnectionError" in caplog.text
    assert token not in caplog.text


def test_get_jwks_client_is_cached_per_url() -> None:
    jwt_module.get_jwks_client.cache_clear()
    try:
        first = jwt_module.get_jwks_client("https://a.example/jwks.json")
        assert first is jwt_module.get_jwks_client("https://a.example/jwks.json")
        assert isinstance(first, jwt.PyJWKClient)
        assert first is not jwt_module.get_jwks_client("https://b.example/jwks.json")
        # Sin caché por `kid` (no expira); sí la del JWK set, que expira con `lifespan`.
        assert not hasattr(first.get_signing_key, "cache_info")
        assert first.jwk_set_cache is not None
    finally:
        jwt_module.get_jwks_client.cache_clear()


def test_hs256_fallback_without_jwks_accepts_hs256() -> None:
    token = make_token(USER_ID, algorithm="HS256")
    assert validate_jwt(token, hs256_settings())["sub"] == str(USER_ID)


@pytest.mark.parametrize("algorithm", ["none", "ES256"])
def test_hs256_fallback_rejects_other_algorithms(algorithm: str) -> None:
    with pytest.raises(InvalidTokenError):
        validate_jwt(make_token(USER_ID, algorithm=algorithm), hs256_settings())


def test_hs256_fallback_rejects_wrong_secret() -> None:
    settings = Settings(
        _env_file=None,
        SUPABASE_URL=TEST_SUPABASE_URL,
        SUPABASE_JWT_SECRET="otro-secreto-de-prueba-que-tampoco-vale-nada-987654",
    )
    with pytest.raises(InvalidTokenError):
        validate_jwt(make_token(USER_ID, algorithm="HS256"), settings)


@pytest.mark.usefixtures("jwks")
def test_jwks_wins_over_secret_when_both_are_configured() -> None:
    settings = make_test_settings().model_copy(
        update={"supabase_jwt_secret": hs256_settings().supabase_jwt_secret}
    )
    assert validate_jwt(make_token(USER_ID), settings)["sub"] == str(USER_ID)
    with pytest.raises(InvalidTokenError):
        validate_jwt(make_token(USER_ID, algorithm="HS256"), settings)


@pytest.mark.parametrize("settings", MISSING_CONFIGURATIONS)
def test_missing_configuration_is_auth_unavailable(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    with pytest.raises(AuthUnavailableError):
        validate_jwt(make_token(USER_ID, algorithm="HS256"), settings)
    assert caplog.records, "la configuración faltante debe quedar en el log"
    assert TEST_JWT_SECRET not in caplog.text


# --- current_user ---------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    install_test_jwks(monkeypatch)
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/yo")
    def me(user: CurrentUser) -> dict[str, str]:
        return {"id": str(user.id), "correo": user.correo}

    app.dependency_overrides[get_settings] = make_test_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_current_user_returns_authenticated_user(client: TestClient) -> None:
    response = client.get("/yo", headers=auth_header(make_token(USER_ID, "ana@example.com")))
    assert response.status_code == 200
    assert response.json() == {"id": str(USER_ID), "correo": "ana@example.com"}


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="sin-token"),
        pytest.param({"Authorization": "Bearer"}, id="bearer-vacio"),
        pytest.param({"Authorization": f"Basic {make_token(USER_ID)}"}, id="esquema-basic"),
        pytest.param(auth_header(make_token(USER_ID, expired=True)), id="vencido"),
        pytest.param(auth_header(make_token(USER_ID, algorithm="none")), id="alg-none"),
        pytest.param(auth_header(make_token(USER_ID, email=None)), id="sin-email"),
        pytest.param(auth_header(make_token(USER_ID, email="")), id="email-vacio"),
        pytest.param(auth_header(make_token(USER_ID, sub="no-es-uuid")), id="sub-no-uuid"),
        pytest.param(auth_header(make_token(USER_ID, sub=12345)), id="sub-numero"),
        pytest.param(auth_header("no-es-un-jwt"), id="basura"),
    ],
)
def test_current_user_rejects_with_401(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/yo", headers=headers)
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY
    assert_contract_error(response.json(), "NO_AUTENTICADO")
    assert response.headers["WWW-Authenticate"] == "Bearer"


def _get_me_with(settings: Settings) -> httpx.Response:
    """`GET /yo` con un token válido y la configuración dada; el 500 no se relanza."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/yo")
    def me(user: CurrentUser) -> dict[str, str]:
        return {"id": str(user.id)}

    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app, raise_server_exceptions=False)
        return client.get("/yo", headers=auth_header(make_token(USER_ID)))
    finally:
        app.dependency_overrides.clear()


def _assert_generic_500(response: httpx.Response) -> None:
    assert response.status_code == 500
    assert response.json() == INTERNAL_ERROR_BODY
    assert_contract_error(response.json(), "ERROR_INTERNO")
    assert "WWW-Authenticate" not in response.headers
    for fragment in (
        "AuthUnavailableError",
        "PyJWKClientConnectionError",
        "detalle-de-red",
        "configuración incompleta",
        "JWKS",
        "SUPABASE",
        "Traceback",
    ):
        assert fragment not in response.text


@pytest.mark.parametrize("settings", MISSING_CONFIGURATIONS)
def test_current_user_without_configuration_is_500(settings: Settings) -> None:
    _assert_generic_500(_get_me_with(settings))


def test_current_user_with_jwks_down_is_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jwt_module, "get_jwks_client", lambda _url: BrokenJwksClient())
    _assert_generic_500(_get_me_with(make_test_settings()))


def test_rejected_token_is_never_echoed(client: TestClient) -> None:
    token = make_token(USER_ID, expired=True)
    response = client.get("/yo", headers=auth_header(token))
    assert token not in response.text
    assert "expired" not in response.text.lower()
