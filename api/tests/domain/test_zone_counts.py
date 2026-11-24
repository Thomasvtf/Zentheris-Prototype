"""Zonas que cuentan para el total del hogar (RN-XI-05, decisión del 23/11/2026).

Solo una zona `activa` con sensor `activo` suma al total: los sensores pausados y las zonas
inactivas no reciben lecturas nuevas.
"""

import pytest

from app.domain.zone_rules import counts_for_total


@pytest.mark.parametrize(
    ("zone_estado", "sensor_estado", "expected"),
    [
        ("activa", "activo", True),
        ("activa", "pausado", False),
        ("activa", None, False),
        ("inactiva", "activo", False),
        ("inactiva", "pausado", False),
        ("inactiva", None, False),
        ("Activa", "activo", False),
        ("activa", "Activo", False),
    ],
)
def test_counts_for_total(zone_estado: str, sensor_estado: str | None, expected: bool) -> None:
    assert counts_for_total(zone_estado, sensor_estado) is expected
