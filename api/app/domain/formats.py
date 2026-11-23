"""Formatos del backend: nombres, claves de evento y textos resueltos.

Nombres de zona y de la fuente principal (RN-XII-03, RN-X-03), clave de evento (DC-25) y textos
de config_files/ (RN-XI-09). La clave de evento y los textos son esqueleto: se implementan con
la sesión de alertas.
"""

from collections.abc import Mapping
from types import MappingProxyType

# RN-XII-03. Una prueba compara estos nombres con `zona.*` del catálogo es-CO.
ZONE_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "cocina": "Cocina",
        "sala": "Sala",
        "dormitorio": "Dormitorio",
        "bano": "Baño",
        "oficina": "Oficina",
        "lavanderia": "Lavandería",
        "terraza": "Terraza",
        "garaje": "Garaje",
        "cuarto_servicio": "Cuarto de servicio",
    }
)


def zone_name(tipo: str) -> str:
    """Nombre visible de una zona, tomado de su tipo (RN-XII-03).

    Raises:
        KeyError: el tipo no está en el catálogo de 9 zonas.
    """
    return ZONE_NAMES[tipo]


def main_source_name(nombre_hogar: str) -> str:
    """Nombre de la fuente principal del hogar (RN-X-03; `fuentes.principal_nombre`)."""
    return f"Fuente principal {nombre_hogar}"


def build_event_key(regla: str, *partes: str) -> str:
    """Arma `clave_evento` según DC-25 (por ejemplo, `<regla>:<zona_id>:<AAAA-MM-DD>`)."""
    raise NotImplementedError("TODO(sesión de alertas): clave_evento (DC-25)")


def render_backend_text(clave: str, variables: Mapping[str, object]) -> str:
    """Rellena la plantilla `clave` de textos-backend.es-CO.json con sus variables."""
    raise NotImplementedError("TODO(sesión de alertas): textos del backend (RN-XI-09)")
