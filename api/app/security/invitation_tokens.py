"""Tokens de invitación: el backend guarda solo el hash (RN-X-05, S-02).

Módulo puro: sin FastAPI ni base de datos. El token en claro solo existe en memoria y en el
enlace del correo (o en el log en local, sin SMTP: DC-04). En `invitaciones_hogar.token_hash`
se guarda `hash_invitation_token(token)`; para resolver un enlace se vuelve a calcular el hash.
"""

import hashlib
import secrets

INVITATION_TOKEN_BYTES = 32


def generate_invitation_token() -> tuple[str, str]:
    """Devuelve `(token, token_hash)`: token url-safe de 32 bytes aleatorios y su hash."""
    token = secrets.token_urlsafe(INVITATION_TOKEN_BYTES)
    return token, hash_invitation_token(token)


def hash_invitation_token(token: str) -> str:
    """SHA-256 del token en UTF-8, en hexadecimal: 64 caracteres en minúsculas."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
