"""Formatos del backend: clave de evento (DC-25) y textos de config_files/ (RN-XI-09).

Esqueleto: se implementa con la sesión de alertas.
"""

from collections.abc import Mapping


def build_event_key(regla: str, *partes: str) -> str:
    """Arma `clave_evento` según DC-25 (por ejemplo, `<regla>:<zona_id>:<AAAA-MM-DD>`)."""
    raise NotImplementedError("TODO(sesión de alertas): clave_evento (DC-25)")


def render_backend_text(clave: str, variables: Mapping[str, object]) -> str:
    """Rellena la plantilla `clave` de textos-backend.es-CO.json con sus variables."""
    raise NotImplementedError("TODO(sesión de alertas): textos del backend (RN-XI-09)")
