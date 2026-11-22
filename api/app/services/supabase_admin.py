"""Supabase Auth y Storage con la clave de servicio (RN-IX-09, RN-I-02, DC-36, DC-43).

Solo el backend usa la clave de servicio (DC-40); la app nunca la ve. Llamadas síncronas con
httpx y tiempo máximo fijo. Los errores se convierten en SupabaseAdminError, que es interna:
el manejador genérico responde 500 ERROR_INTERNO. Este módulo no escribe logs (el fallo lo
registra el manejador genérico o el servicio) y el mensaje del error solo lleva la operación
y, como mucho, el estado HTTP: nunca la clave, el cuerpo de la respuesta ni datos personales.
"""

from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from app.config import Settings

AVATAR_BUCKET = "avatares"
AVATAR_EXTENSIONS = ("jpg", "png", "webp")
TIMEOUT_SECONDS = 10.0

# Hosts de desarrollo local (`supabase start`) a los que se permite http sin TLS.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})
# Código de Supabase Auth cuando la cuenta ya no existe (404 idempotente).
_AUTH_USER_NOT_FOUND = "user_not_found"

_AUTH_OPERATION = "borrar usuario de Auth"
_STORAGE_OPERATION = "borrar avatares de Storage"


class SupabaseAdminError(RuntimeError):
    """Fallo al llamar la API de administración de Supabase. Nunca llega a la respuesta."""


def delete_auth_user(settings: Settings, usuario_id: UUID) -> None:
    """Borra la cuenta en Supabase Auth (RN-IX-09, DC-36).

    `DELETE {SUPABASE_URL}/auth/v1/admin/users/{usuario_id}`. Borrar auth.users borra en
    cascada usuarios, preferencias_usuario, alertas_usuario y consejos_usuario, y deja en nulo
    hogar_miembros.usuario_id.

    200/204 → éxito. 404 → éxito solo si el JSON trae `error_code == "user_not_found"` (la
    cuenta ya no existía; reintentar es seguro). Un 404 sin ese código (por ejemplo, una
    SUPABASE_URL mal configurada), la falta de configuración, un error de red o cualquier
    otro estado lanzan SupabaseAdminError.
    """
    user_id = _as_uuid(usuario_id)
    response = _send(
        settings,
        path=f"/auth/v1/admin/users/{user_id}",
        operation=_AUTH_OPERATION,
    )
    if response.status_code in (200, 204):
        return
    if response.status_code == 404 and _is_auth_user_not_found(response):
        return
    raise SupabaseAdminError(f"Supabase respondió {response.status_code} ({_AUTH_OPERATION}).")


def delete_avatar_files(settings: Settings, usuario_id: UUID) -> None:
    """Borra las fotos del usuario en el bucket privado `avatares` (RN-I-02, DC-43).

    `DELETE {SUPABASE_URL}/storage/v1/object/avatares` con
    `{"prefixes": ["{id}/avatar.jpg", "{id}/avatar.png", "{id}/avatar.webp"]}`: las únicas
    rutas que permite la política de la migración 0005. El borrado por prefijos responde 200
    aunque no exista ningún objeto, así que un 404 (bucket o URL equivocados) es un error.
    Falta de configuración, error de red o cualquier estado distinto de 200/204 lanzan
    SupabaseAdminError.
    """
    user_id = _as_uuid(usuario_id)
    prefixes = [f"{user_id}/avatar.{extension}" for extension in AVATAR_EXTENSIONS]
    response = _send(
        settings,
        path=f"/storage/v1/object/{AVATAR_BUCKET}",
        operation=_STORAGE_OPERATION,
        json={"prefixes": prefixes},
    )
    if response.status_code not in (200, 204):
        raise SupabaseAdminError(
            f"Supabase respondió {response.status_code} ({_STORAGE_OPERATION})."
        )


def _build_client() -> httpx.Client:
    """Cliente HTTP síncrono con el tiempo máximo fijo. Las pruebas lo reemplazan."""
    return httpx.Client(timeout=TIMEOUT_SECONDS)


def _send(
    settings: Settings,
    *,
    path: str,
    operation: str,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    """Envía un DELETE autenticado con la clave de servicio; SupabaseAdminError si no llega."""
    base_url, service_key = _admin_config(settings, operation)
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    try:
        with _build_client() as client:
            return client.request("DELETE", base_url + path, headers=headers, json=json)
    except httpx.HTTPError, httpx.InvalidURL:
        # `from None`: la excepción de httpx puede llevar la URL con el id del usuario.
        raise SupabaseAdminError(f"Supabase no respondió ({operation}).") from None


def _is_auth_user_not_found(response: httpx.Response) -> bool:
    """True si el cuerpo JSON trae `error_code == "user_not_found"`. Solo se lee en memoria."""
    try:
        body = response.json()
    except ValueError:
        return False
    return isinstance(body, dict) and body.get("error_code") == _AUTH_USER_NOT_FOUND


def _admin_config(settings: Settings, operation: str) -> tuple[str, str]:
    """URL base (https, salvo localhost) sin barra final y clave de servicio.

    SupabaseAdminError si falta alguna o si la URL no usa https fuera de desarrollo local:
    la clave de servicio nunca viaja sin TLS a un host remoto.
    """
    base_url = (settings.supabase_url or "").strip().rstrip("/")
    secret = settings.supabase_service_role_key
    service_key = secret.get_secret_value().strip() if secret is not None else ""
    if not base_url or not service_key:
        raise SupabaseAdminError(f"Falta configuración de Supabase ({operation}).")
    if not _is_allowed_base_url(base_url):
        raise SupabaseAdminError(f"SUPABASE_URL no permitida: se exige https ({operation}).")
    return base_url, service_key


def _is_allowed_base_url(base_url: str) -> bool:
    """https con host, o http solo hacia localhost / 127.0.0.1."""
    try:
        parts = urlsplit(base_url)
        hostname = parts.hostname
    except ValueError:
        return False
    if not hostname:
        return False
    scheme = parts.scheme.lower()
    return scheme == "https" or (scheme == "http" and hostname in _LOCAL_HOSTS)


def _as_uuid(value: UUID | str) -> UUID:
    """Normaliza el id: solo un UUID válido entra en la ruta de la URL."""
    return value if isinstance(value, UUID) else UUID(str(value))
