"""Reglas de zonas del onboarding y asignación de la personalidad (RN-X-02, RN-X-04).

Código puro. `ZoneRuleError` lleva el `CodigoError` del contrato como texto; el servicio lo
convierte en la respuesta 422. Un tipo de vivienda o una zona fuera de catálogo no tienen
`CodigoError` propio (los rechaza antes el esquema): aquí son un `ValueError` común.
"""

from collections.abc import Collection, Mapping, Sequence
from typing import Literal

# Catálogos cerrados (RN-II-05, RN-III-02, tabla 12). El orden de PERSONALITIES es el de la regla.
HOUSING_TYPES = ("apartamento", "casa", "apartaestudio", "duplex", "casa_campestre")
BASIC_ZONES = ("cocina", "sala", "dormitorio", "bano")
COMPLEMENTARY_ZONES = ("oficina", "lavanderia")
EXTRA_ZONES = ("terraza", "garaje", "cuarto_servicio")
ZONE_TYPES = BASIC_ZONES + COMPLEMENTARY_ZONES + EXTRA_ZONES

PERSONALITIES = (
    "Consumo compacto",
    "Consumo eficiente",
    "Consumo intermedio",
    "Consumo familiar",
    "Consumo amplio",
)
FALLBACK_PERSONALITY = "Consumo eficiente"

# Límites del apartaestudio (RN-X-02) y máximo de zonas de *Consumo compacto* (RN-X-04).
_STUDIO = "apartaestudio"
_STUDIO_MIN_ZONES = 3
_STUDIO_MAX_ZONES = 5
_STUDIO_MIN_BASIC_ZONES = 3
_COMPACT_MAX_ZONES = 4

_COMPACT, _EFFICIENT, _INTERMEDIATE, _FAMILY, _LARGE = PERSONALITIES

# Casa campestre: un nivel más que una casa, con tope en amplio (RN-X-04).
_COUNTRY_HOUSE = "casa_campestre"
_NEXT_LEVEL = {
    _EFFICIENT: _INTERMEDIATE,
    _INTERMEDIATE: _FAMILY,
    _FAMILY: _LARGE,
    _LARGE: _LARGE,
}

ZoneErrorCode = Literal[
    "ZONAS_NO_PERMITIDAS",
    "ZONAS_BASICAS_FALTANTES",
    "CANTIDAD_ZONAS_INVALIDA",
    "ZONAS_DUPLICADAS",
]


class ZoneRuleError(ValueError):
    """La selección de zonas no cumple RN-X-02; `code` es el `CodigoError` del contrato."""

    def __init__(self, code: ZoneErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: ZoneErrorCode = code


def validate_zones(tipo_vivienda: str, zonas: Sequence[str]) -> frozenset[str]:
    """Valida la selección según el tipo de vivienda (RN-X-02) y la devuelve como conjunto.

    Orden: `ZONAS_DUPLICADAS` → `ZONAS_NO_PERMITIDAS` → `CANTIDAD_ZONAS_INVALIDA` (apartaestudio)
    → `ZONAS_BASICAS_FALTANTES` (los demás tipos).

    Raises:
        ZoneRuleError: la selección incumple una restricción.
        ValueError: el tipo de vivienda o una zona no están en el catálogo.
    """
    if tipo_vivienda not in HOUSING_TYPES:
        raise ValueError("tipo de vivienda fuera del catálogo")
    if any(zona not in ZONE_TYPES for zona in zonas):
        raise ValueError("zona fuera del catálogo")

    selected = frozenset(zonas)
    if len(selected) != len(zonas):
        raise ZoneRuleError("ZONAS_DUPLICADAS", "zona repetida")

    if tipo_vivienda == _STUDIO:
        _validate_studio(selected)
    elif not selected.issuperset(BASIC_ZONES):
        raise ZoneRuleError("ZONAS_BASICAS_FALTANTES", "las 4 zonas básicas son obligatorias")
    return selected


def _validate_studio(selected: frozenset[str]) -> None:
    if not selected.isdisjoint(EXTRA_ZONES):
        raise ZoneRuleError("ZONAS_NO_PERMITIDAS", "apartaestudio no admite zonas extras")
    if not _STUDIO_MIN_ZONES <= len(selected) <= _STUDIO_MAX_ZONES:
        raise ZoneRuleError("CANTIDAD_ZONAS_INVALIDA", "apartaestudio: entre 3 y 5 zonas")
    if len(selected.intersection(BASIC_ZONES)) < _STUDIO_MIN_BASIC_ZONES:
        raise ZoneRuleError("CANTIDAD_ZONAS_INVALIDA", "apartaestudio: al menos 3 zonas básicas")


def assign_personality(tipo_vivienda: str, zonas: Collection[str]) -> str:
    """Personalidad que corresponde a la vivienda y sus zonas (RN-X-04, tabla 12).

    Valida antes de clasificar; levanta lo mismo que `validate_zones`.
    """
    selected = validate_zones(tipo_vivienda, tuple(zonas))
    if tipo_vivienda == _STUDIO:
        return _COMPACT if len(selected) <= _COMPACT_MAX_ZONES else _EFFICIENT
    personality = _personality_as_house(selected)
    return _NEXT_LEVEL[personality] if tipo_vivienda == _COUNTRY_HOUSE else personality


def _personality_as_house(selected: frozenset[str]) -> str:
    """Apartamento, casa y dúplex: se evalúa en orden y gana la primera condición."""
    c = len(selected & {"oficina", "lavanderia", "terraza", "garaje"})
    s = "cuarto_servicio" in selected
    e = len(selected.intersection(EXTRA_ZONES))
    ol = not selected.isdisjoint(COMPLEMENTARY_ZONES)
    if e >= 2 and ol:
        return _LARGE
    if c >= 2 or s:
        return _FAMILY
    if c == 1:
        return _INTERMEDIATE
    return _EFFICIENT


def resolve_active_personality(name: str, active: Mapping[str, bool]) -> str:
    """Respaldo de RN-X-04: si la asignada no existe o está inactiva, *Consumo eficiente*.

    `active` es nombre → `activo`; una personalidad ausente cuenta como inactiva.

    Raises:
        LookupError: tampoco está activo el respaldo (A20).
    """
    if active.get(name) is True:
        return name
    if active.get(FALLBACK_PERSONALITY) is True:
        return FALLBACK_PERSONALITY
    raise LookupError("ni la personalidad asignada ni el respaldo están activos")


# Estados de zona y de sensor que suman al total del hogar (RN-XI-05; decisión del 23/11/2026:
# los sensores pausados y las zonas inactivas no reciben lecturas nuevas).
_COUNTING_ZONE_STATE = "activa"
_COUNTING_SENSOR_STATE = "activo"


def counts_for_total(zone_estado: str, sensor_estado: str | None) -> bool:
    """True solo si la zona está `activa` y su sensor `activo` («zonas que cuentan»).

    Zona `inactiva`, sensor `pausado` o zona sin sensor (`None`): no suma al total del hogar.
    """
    return zone_estado == _COUNTING_ZONE_STATE and sensor_estado == _COUNTING_SENSOR_STATE
