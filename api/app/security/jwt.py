"""Validación del token de acceso de Supabase Auth (DC-44: firmas públicas por JWKS).

Esqueleto: se implementa en la sesión 3 con PyJWT y `SUPABASE_JWKS_URL`.
"""

from typing import Any

from fastapi.security import HTTPBearer

# Mismo esquema que `components.securitySchemes.supabaseJwt` del contrato.
# auto_error=False: la falta de token se responde con el formato de error del contrato
# cuando se implemente la sesión 3 (decisión pendiente, PENDIENTES #29).
bearer_scheme = HTTPBearer(
    scheme_name="supabaseJwt",
    bearerFormat="JWT",
    description="Token de acceso emitido por Supabase Auth.",
    auto_error=False,
)


def validate_jwt(token: str) -> dict[str, Any]:
    """Valida firma, emisor, audiencia y vencimiento del token y devuelve sus claims."""
    raise NotImplementedError("TODO(sesión 3): validar con JWKS (DC-44)")
