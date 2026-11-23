"""Z-01 · Zonas: Apartaestudio con terraza.

Esperado: 422 `ZONAS_NO_PERMITIDAS`. Regla: RN-X-02.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.
Aquí se comprueba el código en el dominio; el 422 lo arma el servicio."""

import pytest

from app.domain.zone_rules import BASIC_ZONES, ZoneRuleError, validate_zones


def test_z01_studio_with_terrace() -> None:
    with pytest.raises(ZoneRuleError) as error:
        validate_zones("apartaestudio", [*BASIC_ZONES, "terraza"])
    assert error.value.code == "ZONAS_NO_PERMITIDAS"


@pytest.mark.parametrize("extra", ["terraza", "garaje", "cuarto_servicio"])
def test_studio_rejects_each_extra(extra: str) -> None:
    with pytest.raises(ZoneRuleError) as error:
        validate_zones("apartaestudio", ["cocina", "sala", "bano", extra])
    assert error.value.code == "ZONAS_NO_PERMITIDAS"


@pytest.mark.parametrize(
    "zones",
    [
        pytest.param([*BASIC_ZONES, "oficina", "terraza"], id="y-6-zonas"),
        pytest.param(["cocina", "terraza"], id="y-2-zonas"),
        pytest.param(["cocina", "sala", "terraza"], id="y-2-basicas"),
    ],
)
def test_not_allowed_goes_before_the_count(zones: list[str]) -> None:
    with pytest.raises(ZoneRuleError) as error:
        validate_zones("apartaestudio", zones)
    assert error.value.code == "ZONAS_NO_PERMITIDAS"


@pytest.mark.parametrize("housing", ["apartamento", "casa", "duplex", "casa_campestre"])
def test_other_housing_accepts_the_extras(housing: str) -> None:
    zones = [*BASIC_ZONES, "terraza", "garaje", "cuarto_servicio"]
    assert validate_zones(housing, zones) == frozenset(zones)
