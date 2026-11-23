"""Enumeración de las selecciones de zonas del onboarding (apoyo de pruebas).

Porta `enumerar_selecciones` y `zonas_aplicables` de `zentheris_sim/asignacion.py` (Avance 03)
y los 13 ejemplos de la tabla 12. Lo usan las pruebas de zonas y las del simulador (K01 a K12).
El orden es el de la referencia: `HOUSING_TYPES` × combinaciones de `ZONE_TYPES` por tamaño.
"""

from collections.abc import Iterator
from itertools import combinations

from app.domain.zone_rules import (
    BASIC_ZONES,
    FALLBACK_PERSONALITY,
    HOUSING_TYPES,
    PERSONALITIES,
    ZONE_TYPES,
    ZoneRuleError,
    assign_personality,
)

# (vivienda, zonas, válida, personalidad o None si se rechaza)
Selection = tuple[str, tuple[str, ...], bool, str | None]

# Tabla 12 de docs/reglas/reglas-de-negocio.md, «Ejemplos de comprobación» (Z-04, K04).
EXAMPLES_TABLE_12: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("apartaestudio", ("sala", "cocina", "dormitorio", "bano"), "Consumo compacto"),
    ("apartaestudio", (*BASIC_ZONES, "lavanderia"), "Consumo eficiente"),
    ("apartamento", BASIC_ZONES, "Consumo eficiente"),
    ("apartamento", (*BASIC_ZONES, "oficina"), "Consumo intermedio"),
    ("apartamento", (*BASIC_ZONES, "terraza"), "Consumo intermedio"),
    ("apartamento", (*BASIC_ZONES, "oficina", "lavanderia"), "Consumo familiar"),
    ("apartamento", (*BASIC_ZONES, "terraza", "garaje"), "Consumo familiar"),
    ("apartamento", (*BASIC_ZONES, "lavanderia", "terraza", "garaje"), "Consumo amplio"),
    ("casa", (*BASIC_ZONES, "cuarto_servicio"), "Consumo familiar"),
    ("duplex", ZONE_TYPES, "Consumo amplio"),
    ("casa_campestre", BASIC_ZONES, "Consumo intermedio"),
    ("casa_campestre", (*BASIC_ZONES, "terraza"), "Consumo familiar"),
    ("casa_campestre", (*BASIC_ZONES, "oficina", "terraza"), "Consumo amplio"),
)


def enumerate_selections() -> Iterator[Selection]:
    """Las 5 × 2^9 = 2.560 selecciones: (vivienda, zonas, válida, personalidad)."""
    for housing in HOUSING_TYPES:
        for size in range(len(ZONE_TYPES) + 1):
            for zones in combinations(ZONE_TYPES, size):
                try:
                    personality = assign_personality(housing, zones)
                except ZoneRuleError:
                    yield housing, zones, False, None
                else:
                    yield housing, zones, True, personality


def applicable_zones() -> dict[str, frozenset[str]]:
    """Zonas que puede recibir cada personalidad por asignación ordinaria.

    *Consumo eficiente* recibe las nueve, porque es el respaldo de RN-X-04 (A19).
    """
    zones_by_personality: dict[str, set[str]] = {name: set() for name in PERSONALITIES}
    for _, zones, _, personality in enumerate_selections():
        if personality is not None:
            zones_by_personality[personality].update(zones)
    zones_by_personality[FALLBACK_PERSONALITY] = set(ZONE_TYPES)
    return {name: frozenset(zones) for name, zones in zones_by_personality.items()}
