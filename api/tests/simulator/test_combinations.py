"""K10 a K12 de la referencia (Avance 03, `pruebas/test_combinaciones.py`).

K01 a K09 no usan el simulador: están en tests/zones/.
"""

import math

from app.domain.simulator.engine import simulate_household
from app.domain.zone_rules import PERSONALITIES, ZONE_TYPES
from tests.simulator.support import (
    create_household,
    idx,
    sample_profiles,
    zones_without_parameters,
)
from tests.zones.selections import enumerate_selections


def test_k10_sample_parameters_coverage():
    """K10 Con los conjuntos de prueba, toda zona aplicable tiene base > 0."""
    profiles = sample_profiles()
    assert zones_without_parameters(profiles) == []
    profiles["Consumo eficiente"]["base_garaje_kwh_dia"] = 0
    assert zones_without_parameters(profiles) == ["Consumo eficiente:garaje"]


def test_k11_simulate_the_147():
    """K11 Cada combinación válida recibe su personalidad y simula 2 días solo de sus zonas."""
    profiles = sample_profiles()
    start = idx(2026, 9, 5)  # sábado y domingo
    valid = [(v, z, p) for v, z, ok, p in enumerate_selections() if ok]
    assert len(valid) == 147
    for number, (housing, zones, personality) in enumerate(valid):
        household = create_household(f"comb-{number}", housing, zones)
        assert household.personality == personality
        series = simulate_household(
            household.id, profiles[personality], household.zones, start, start + 48
        )
        assert set(series) == set(zones)
        for readings in series.values():
            assert len(readings) == 48
            assert all(math.isfinite(r.total) and r.total >= 0 for r in readings)


def test_k12_fallback_with_nine_zones():
    """K12 Dúplex de 9 zonas con amplio inactivo usa eficiente y simula las 9 zonas."""
    active = dict.fromkeys(PERSONALITIES, True)
    active["Consumo amplio"] = False
    household = create_household("respaldo-9", "duplex", ZONE_TYPES, active)
    assert household.assigned_personality == "Consumo amplio"
    assert household.personality == "Consumo eficiente"
    profile = sample_profiles()[household.personality]
    series = simulate_household(
        household.id, profile, household.zones, idx(2026, 9, 1), idx(2026, 9, 2)
    )
    assert set(series) == set(ZONE_TYPES)
    assert all(sum(r.total for r in readings) > 0 for readings in series.values())
