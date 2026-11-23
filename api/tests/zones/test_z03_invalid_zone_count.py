"""Z-03 · Zonas: Apartaestudio con 6 zonas o con 2 básicas.

Esperado: 422 `CANTIDAD_ZONAS_INVALIDA`. Regla: RN-X-02.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.
Aquí se comprueba el código en el dominio; el 422 lo arma el servicio."""

import pytest

from app.domain.zone_rules import BASIC_ZONES, ZoneRuleError, validate_zones


@pytest.mark.parametrize(
    "zones",
    [
        pytest.param([*BASIC_ZONES, "oficina", "lavanderia"], id="6-zonas"),
        pytest.param(["cocina", "sala", "oficina"], id="3-zonas-con-2-basicas"),
        pytest.param(["cocina", "sala", "oficina", "lavanderia"], id="4-zonas-con-2-basicas"),
        pytest.param(["cocina", "sala"], id="2-zonas"),
        pytest.param([], id="0-zonas"),
    ],
)
def test_z03_studio_invalid_count(zones: list[str]) -> None:
    with pytest.raises(ZoneRuleError) as error:
        validate_zones("apartaestudio", zones)
    assert error.value.code == "CANTIDAD_ZONAS_INVALIDA"


@pytest.mark.parametrize(
    "zones",
    [
        pytest.param(["cocina", "sala", "bano"], id="minimo-3-basicas"),
        pytest.param([*BASIC_ZONES, "oficina"], id="maximo-5-con-4-basicas"),
        pytest.param(["cocina", "sala", "bano", "oficina", "lavanderia"], id="maximo-5-con-3"),
    ],
)
def test_studio_limits_are_inclusive(zones: list[str]) -> None:
    assert validate_zones("apartaestudio", zones) == frozenset(zones)
