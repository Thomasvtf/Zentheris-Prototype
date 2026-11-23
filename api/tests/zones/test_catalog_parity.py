"""Los catálogos del dominio son los enums del contrato (`TipoVivienda`, `TipoZona`).

El dominio no importa `app.schemas` (prueba de pureza): esta prueba evita que se separen.
"""

from app.domain.zone_rules import HOUSING_TYPES, ZONE_TYPES
from app.schemas.common import TipoVivienda, TipoZona


def test_zone_types_match_the_contract() -> None:
    assert ZONE_TYPES == tuple(zone.value for zone in TipoZona)


def test_housing_types_match_the_contract() -> None:
    assert HOUSING_TYPES == tuple(housing.value for housing in TipoVivienda)
