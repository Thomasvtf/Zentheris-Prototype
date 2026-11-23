"""Z-02 · Zonas: Apartamento sin baño.

Esperado: 422 `ZONAS_BASICAS_FALTANTES`. Regla: RN-X-02.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.
Aquí se comprueba el código en el dominio; el 422 lo arma el servicio."""

import pytest

from app.domain.zone_rules import BASIC_ZONES, ZONE_TYPES, ZoneRuleError, validate_zones

HOUSING_WITH_BASICS = ["apartamento", "casa", "duplex", "casa_campestre"]


def test_z02_apartment_without_bathroom() -> None:
    with pytest.raises(ZoneRuleError) as error:
        validate_zones("apartamento", ["cocina", "sala", "dormitorio"])
    assert error.value.code == "ZONAS_BASICAS_FALTANTES"


@pytest.mark.parametrize("housing", HOUSING_WITH_BASICS)
@pytest.mark.parametrize("missing", BASIC_ZONES)
def test_each_basic_zone_is_required(housing: str, missing: str) -> None:
    # Con las otras 8 zonas: ninguna cantidad compensa una básica que falta.
    zones = [zone for zone in ZONE_TYPES if zone != missing]
    with pytest.raises(ZoneRuleError) as error:
        validate_zones(housing, zones)
    assert error.value.code == "ZONAS_BASICAS_FALTANTES"


@pytest.mark.parametrize("housing", HOUSING_WITH_BASICS)
def test_empty_selection(housing: str) -> None:
    with pytest.raises(ZoneRuleError) as error:
        validate_zones(housing, [])
    assert error.value.code == "ZONAS_BASICAS_FALTANTES"


@pytest.mark.parametrize("housing", HOUSING_WITH_BASICS)
def test_basics_only_and_all_nine_are_valid(housing: str) -> None:
    assert validate_zones(housing, list(BASIC_ZONES)) == frozenset(BASIC_ZONES)
    assert validate_zones(housing, list(ZONE_TYPES)) == frozenset(ZONE_TYPES)
