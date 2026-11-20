"""Comprueba el helper de promedios de personalidades contra la regla de negocio.

Regla (reglas v4.9, sección de personalidades): el consumo mensual de un hogar con todas sus
zonas respeta el orden compacto < eficiente < intermedio < familiar < amplio.
"""

import math

import pytest

from tests.helpers.personalities import (
    PERSONALITY_ORDER,
    PROFILES_SHA256,
    load_personalities,
)


def test_has_the_five_personalities_in_order():
    assert tuple(load_personalities()) == PERSONALITY_ORDER


def test_monthly_consumption_respects_the_business_order():
    monthly = [p.kwh_per_month for p in load_personalities().values()]
    assert monthly == sorted(monthly)
    assert len(set(monthly)) == 5


@pytest.mark.parametrize("personality", load_personalities().values(), ids=lambda p: p.name)
def test_every_hourly_curve_sums_to_one(personality):
    for key, curve in personality.hourly_share.items():
        assert len(curve) == 24, f"{personality.name}/{key}"
        assert math.isclose(sum(curve), 1.0, abs_tol=1e-6), f"{personality.name}/{key}"


@pytest.mark.parametrize("personality", load_personalities().values(), ids=lambda p: p.name)
def test_hourly_values_add_up_to_the_daily_base(personality):
    daily = sum(personality.household_kwh_for_hour(hour) for hour in range(24))
    assert math.isclose(daily, personality.kwh_per_day, rel_tol=1e-6)


def test_zone_not_contemplated_by_the_personality_is_rejected():
    compact = load_personalities()["Consumo compacto"]
    assert "terraza" not in compact.zone_kwh_per_day
    with pytest.raises(KeyError):
        compact.zone_kwh_for_hour("terraza", 12)


def test_sha256_constant_matches_supabase_claude_md():
    # Prefijo y sufijo documentados en supabase/CLAUDE.md: 6cfa9715…0a90922
    assert PROFILES_SHA256.startswith("6cfa9715")
    assert PROFILES_SHA256.endswith("a90922")
