"""Z-04 · Zonas: Las 13 combinaciones de ejemplo de la tabla 12.

Esperado: Personalidad esperada **[ref]** (147 combinaciones en el Avance 03). Regla: RN-X-04.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.
Las 147 combinaciones están en test_reference_combinations.py (K01 a K09)."""

import pytest

from app.domain.zone_rules import PERSONALITIES, assign_personality
from tests.helpers.personalities import load_personalities
from tests.zones.selections import EXAMPLES_TABLE_12


def test_table_12_has_thirteen_examples() -> None:
    assert len(EXAMPLES_TABLE_12) == 13


@pytest.mark.parametrize(
    ("housing", "zones", "expected"),
    EXAMPLES_TABLE_12,
    ids=[f"ejemplo-{i:02}-{example[0]}" for i, example in enumerate(EXAMPLES_TABLE_12, 1)],
)
def test_z04_example_of_table_12(housing: str, zones: tuple[str, ...], expected: str) -> None:
    assert assign_personality(housing, zones) == expected


@pytest.mark.parametrize(("housing", "zones", "expected"), EXAMPLES_TABLE_12)
def test_assignment_does_not_depend_on_order_or_collection(
    housing: str, zones: tuple[str, ...], expected: str
) -> None:
    assert assign_personality(housing, zones[::-1]) == expected
    assert assign_personality(housing, frozenset(zones)) == expected


def test_personalities_are_the_seeded_profiles() -> None:
    """Los nombres exactos de la tabla 12 son los de los 5 perfiles reales, en el mismo orden."""
    assert PERSONALITIES == tuple(load_personalities())


@pytest.mark.parametrize(("housing", "zones", "expected"), EXAMPLES_TABLE_12)
def test_assigned_profile_has_consumption_in_every_zone(
    housing: str, zones: tuple[str, ...], expected: str
) -> None:
    """El perfil asignado tiene base mayor que 0 en todas las zonas del ejemplo."""
    profile = load_personalities()[assign_personality(housing, zones)]
    assert set(zones) <= set(profile.zone_kwh_per_day)
