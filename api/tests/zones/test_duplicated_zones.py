"""`ZONAS_DUPLICADAS` y valores fuera de catálogo (RN-X-02, contrato `POST /onboarding`)."""

from typing import get_args

import pytest

from app.domain.zone_rules import (
    BASIC_ZONES,
    HOUSING_TYPES,
    ZoneErrorCode,
    ZoneRuleError,
    assign_personality,
    validate_zones,
)
from app.errors import CodigoError


@pytest.mark.parametrize("housing", HOUSING_TYPES)
def test_repeated_zone(housing: str) -> None:
    with pytest.raises(ZoneRuleError) as error:
        validate_zones(housing, [*BASIC_ZONES, "cocina"])
    assert error.value.code == "ZONAS_DUPLICADAS"


@pytest.mark.parametrize(
    ("housing", "zones"),
    [
        pytest.param("apartaestudio", [*BASIC_ZONES, "terraza", "terraza"], id="y-no-permitida"),
        pytest.param("apartaestudio", ["cocina", "cocina"], id="y-cantidad"),
        pytest.param("apartamento", ["cocina", "sala", "sala"], id="y-faltan-basicas"),
    ],
)
def test_duplicates_go_first(housing: str, zones: list[str]) -> None:
    with pytest.raises(ZoneRuleError) as error:
        validate_zones(housing, zones)
    assert error.value.code == "ZONAS_DUPLICADAS"


def test_assign_personality_validates_first() -> None:
    with pytest.raises(ZoneRuleError) as error:
        assign_personality("casa", [*BASIC_ZONES, "cocina"])
    assert error.value.code == "ZONAS_DUPLICADAS"


@pytest.mark.parametrize(
    ("housing", "zones"),
    [
        pytest.param("loft", list(BASIC_ZONES), id="vivienda"),
        pytest.param("apartamento", [*BASIC_ZONES, "patio"], id="zona"),
        pytest.param("apartamento", [*BASIC_ZONES, "patio", "patio"], id="zona-repetida"),
        pytest.param("apartamento", "cocina", id="texto-en-vez-de-lista"),
    ],
)
def test_out_of_catalog_is_a_plain_value_error(housing: str, zones: list[str]) -> None:
    """Sin `CodigoError` propio en el contrato: no es un `ZoneRuleError`."""
    with pytest.raises(ValueError) as error:
        validate_zones(housing, zones)
    assert type(error.value) is ValueError


def test_codes_exist_in_the_contract() -> None:
    codes = get_args(ZoneErrorCode)
    assert len(codes) == 4
    assert set(codes) <= {code.value for code in CodigoError}
