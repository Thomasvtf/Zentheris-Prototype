"""Validación del token de acceso de Supabase Auth (DC-44: firmas públicas por JWKS).

Con `SUPABASE_JWKS_URL` se valida solo con algoritmos asimétricos (`ES256`, `RS256`) y la
clave pública del JWKS. Solo si no hay JWKS pero sí `SUPABASE_JWT_SECRET`, se acepta HS256
con ese secreto. Nunca `alg=none`, nunca HS256 cuando se valida por JWKS.

- `InvalidTokenError`: el token es inválido (la dependencia responde 401).
- `AuthUnavailableError`: falla la infraestructura (configuración faltante o JWKS caído).
  No es culpa del token: sube al manejador genérico y responde 500 (DC-16: la app muestra
  «error del servidor», no «sesión vencida»).
Ninguna de las dos llega a la respuesta.
"""

import logging
from functools import lru_cache
from typing import Any

import jwt
from fastapi.security import HTTPBearer

from app.config import Settings

logger = logging.getLogger(__name__)

# Mismo esquema que `components.securitySchemes.supabaseJwt` del contrato.
# auto_error=False: la falta de token la responde `current_user` con 401 (PendingCodeError).
bearer_scheme = HTTPBearer(
    scheme_name="supabaseJwt",
    bearerFormat="JWT",
    description="Token de acceso emitido por Supabase Auth.",
    auto_error=False,
)

ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")
SYMMETRIC_ALGORITHM = "HS256"
AUDIENCE = "authenticated"
REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]
JWKS_TIMEOUT_SECONDS = 5.0


class InvalidTokenError(Exception):
    """Token ausente, mal formado, vencido o con firma, emisor o audiencia inválidos.

    Interna de la capa de seguridad: nunca llega a la respuesta.
    """


class AuthUnavailableError(RuntimeError):
    """No se puede validar ningún token: falta configuración o el JWKS no responde.

    Interna de la capa de seguridad: `current_user` no la captura y el manejador genérico
    responde 500 sin exponerla.
    """


@lru_cache
def get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    """Cliente del JWKS de Supabase, uno por URL, con las claves en caché."""
    # cache_keys=False: la caché por `kid` no expira y una clave revocada seguiría válida hasta
    # reiniciar. La caché del JWK set (cache_jwk_set, con `lifespan`) sí expira.
    return jwt.PyJWKClient(jwks_url, cache_keys=False, timeout=JWKS_TIMEOUT_SECONDS)


def _expected_issuer(settings: Settings) -> str:
    if not settings.supabase_url:
        logger.error("Falta SUPABASE_URL: no se puede validar el emisor del token.")
        raise AuthUnavailableError("configuración incompleta")
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


def _verification_key(token: str, settings: Settings) -> tuple[Any, list[str]]:
    """Clave y algoritmos permitidos según la configuración (DC-44)."""
    if settings.supabase_jwks_url:
        signing_key = get_jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token)
        # Solo el algoritmo asimétrico propio de la clave del JWKS: así una cabecera con
        # otro `alg` (none, HS256 o RS256 sobre una clave EC) no llega a verificarse.
        if signing_key.algorithm_name not in ASYMMETRIC_ALGORITHMS:
            raise InvalidTokenError("algoritmo de la clave no permitido")
        return signing_key.key, [signing_key.algorithm_name]
    if settings.supabase_jwt_secret is not None:
        return settings.supabase_jwt_secret.get_secret_value(), [SYMMETRIC_ALGORITHM]
    logger.error("Faltan SUPABASE_JWKS_URL y SUPABASE_JWT_SECRET: no se puede validar el token.")
    raise AuthUnavailableError("configuración incompleta")


def validate_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """Valida firma, `exp`, `iss`, `aud` y algoritmo explícito (DC-44). Devuelve los claims."""
    issuer = _expected_issuer(settings)
    try:
        key, algorithms = _verification_key(token, settings)
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=AUDIENCE,
            issuer=issuer,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.PyJWKClientConnectionError as exc:
        # Antes que PyJWTError (es su subclase): JWKS caído = 500, no 401. Solo el tipo.
        logger.error("No se pudo consultar el JWKS: %s", type(exc).__name__)
        raise AuthUnavailableError("JWKS no disponible") from None
    except jwt.PyJWTError as exc:
        # Solo el tipo de error: ni el token ni sus claims van al log.
        logger.info("Token rechazado: %s", type(exc).__name__)
        raise InvalidTokenError("token inválido") from None
    return claims
