"""S-02 · Seguridad: Token de invitación.

Esperado: Solo se guarda su hash. Regla: RN-X-05.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Aquí se prueba el módulo puro `app.security.invitation_tokens`: el token en claro es url-safe y
de alta entropía, y lo que se guarda (el hash SHA-256 en hexadecimal) no es el token ni lo
contiene ni permite recuperarlo. Que en la base solo quede el hash lo comprueban el servicio y el
e2e de invitaciones.
"""

import hashlib
import re

import pytest

from app.security.invitation_tokens import (
    INVITATION_TOKEN_BYTES,
    generate_invitation_token,
    hash_invitation_token,
)

URL_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")
LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
# secrets.token_urlsafe(32): 32 bytes en base64url sin relleno = 43 caracteres.
MIN_TOKEN_LENGTH = 43


def test_token_bytes_is_32() -> None:
    assert INVITATION_TOKEN_BYTES == 32


def test_generate_returns_token_and_its_hash() -> None:
    token, token_hash = generate_invitation_token()

    assert isinstance(token, str)
    assert isinstance(token_hash, str)
    assert hash_invitation_token(token) == token_hash


def test_token_is_url_safe_and_long_enough() -> None:
    token, _ = generate_invitation_token()

    assert URL_SAFE.fullmatch(token)
    assert len(token) >= MIN_TOKEN_LENGTH


def test_hash_is_64_lowercase_hex() -> None:
    token, token_hash = generate_invitation_token()

    assert LOWER_HEX_64.fullmatch(token_hash)
    assert LOWER_HEX_64.fullmatch(hash_invitation_token(token))


def test_hash_is_not_the_token_nor_contains_it() -> None:
    token, token_hash = generate_invitation_token()

    assert token_hash != token
    assert token not in token_hash


def test_hash_is_deterministic_sha256_of_utf8() -> None:
    token = "abc_DEF-123"
    expected = hashlib.sha256(token.encode("utf-8")).hexdigest()

    assert hash_invitation_token(token) == expected
    assert hash_invitation_token(token) == hash_invitation_token(token)


def test_two_tokens_in_a_row_differ_and_so_do_their_hashes() -> None:
    first_token, first_hash = generate_invitation_token()
    second_token, second_hash = generate_invitation_token()

    assert first_token != second_token
    assert first_hash != second_hash


@pytest.mark.parametrize("token", ["", "a", "token con espacios", "ñandú"])
def test_hash_accepts_any_string(token: str) -> None:
    assert LOWER_HEX_64.fullmatch(hash_invitation_token(token))
