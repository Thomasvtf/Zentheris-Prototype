"""Lo que promete cada personalidad, comprobado con lo que genera el simulador.

RN-IV-01, RN-IV-04, RN-IV-07, RN-X-04 y condiciones de validez de la sección 5. Los promedios
salen de `docs/datos/perfiles/` (helper con SHA-256 comprobado). Ningún margen es inventado:

- Bandas de humor, fin de semana y forma horaria: cotas exactas del modelo. Con |ε| ≤ 1 se cumple
  |n| ≤ m = σ/(1−φ) < 1, así que Q ∈ [w·(1−m)/(1+m), w·(1+m)/(1−m)].
- `CONSERVATION_TOLERANCE` (1e-10, CT06) para comparar sumas en coma flotante.
- CE01, CE03, CE11 y CE15: criterios congelados del Avance 03 (`congelamiento_referencias.json`).
- Totales por semilla y perfil horario: resultados publicados por la referencia (copias exactas).
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cache

import pytest

from app.domain.simulator import generate_backfill, hour_index
from app.domain.simulator.constants import CONSERVATION_TOLERANCE
from app.domain.simulator.engine import regular_day, simulate_household
from app.domain.simulator.validation import noise_margin, validate_profile
from app.domain.zone_rules import EXTRA_ZONES
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities
from tests.simulator.support import (
    bogota,
    create_household,
    final_profiles,
    frozen_references,
    idx,
    read_csv,
    stable_id,
)
from tests.zones.selections import applicable_zones

NOW = bogota(2026, 11, 22, 15, 23)
# Lunes 2 a domingo 29 de noviembre de 2026: 4 semanas completas.
DAYS = [date(2026, 11, 2) + timedelta(days=offset) for offset in range(28)]
# Ventana y semillas de la validación ciega de la referencia.
VALIDATION_START, VALIDATION_END = idx(2026, 11, 1), idx(2026, 12, 1)
REFERENCE_SEEDS = 100

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


def full_household(personality: PersonalityAverages, label: str = "a"):
    """Hogar (id y sensores) con todas las zonas que contempla la personalidad."""
    hogar_id = stable_id("hogar", "personalidad", personality.name, label)
    sensors = {
        zone: stable_id("sensor", personality.name, label, zone)
        for zone in personality.zone_kwh_per_day
    }
    return hogar_id, sensors


def backfill(personality: PersonalityAverages, label: str = "a"):
    hogar_id, sensors = full_household(personality, label)
    return generate_backfill(hogar_id, final_profiles()[personality.name], sensors, NOW)


# ------------------------------------------------------------------ zonas
@each_personality
def test_contemplated_zones_are_the_ones_it_can_receive(personality):
    """Una personalidad solo tiene consumo en las zonas que RN-X-04 le puede asignar."""
    assert set(personality.zone_kwh_per_day) == applicable_zones()[personality.name]


def test_compact_never_receives_extra_zones():
    compact = load_personalities()["Consumo compacto"]
    assert not set(compact.zone_kwh_per_day) & set(EXTRA_ZONES)


@each_personality
def test_backfill_only_generates_the_zones_of_the_household(personality):
    _, sensors = full_household(personality)
    rows = backfill(personality)
    per_sensor = defaultdict(list)
    for row in rows:
        per_sensor[row["sensor_id"]].append(row["consumo_kwh"])
    assert set(per_sensor) == set(sensors.values())
    for values in per_sensor.values():
        assert len(values) == 720
        assert sum(values) > 0
    assert {row["calidad"] for row in rows} == {"simulada"}


@each_personality
def test_fewer_zones_mean_less_consumption_without_redistribution(personality):
    """RN-IV-07: quitar una zona no cambia ninguna lectura de las demás."""
    hogar_id, sensors = full_household(personality)
    absent = sensors["sala"]
    remaining = {zone: sensor for zone, sensor in sensors.items() if sensor != absent}
    partial = generate_backfill(hogar_id, final_profiles()[personality.name], remaining, NOW)
    assert partial == [row for row in backfill(personality) if row["sensor_id"] != absent]


# ------------------------------------------------------------------ orden
@pytest.mark.parametrize("label", ["a", "b", "c", "d", "e"])
def test_monthly_consumption_of_a_full_household_respects_the_order(label):
    """compacto < eficiente < intermedio < familiar < amplio (condición de validez 6)."""
    totals = [
        sum(row["consumo_kwh"] for row in backfill(personality, label))
        for personality in load_personalities().values()
    ]
    assert totals == sorted(totals)
    assert len(set(totals)) == 5


# ------------------------------------------------------------------ banda diaria y forma
@each_personality
def test_daily_regular_consumption_stays_in_the_humor_and_weekend_band(personality):
    hogar_id, sensors = full_household(personality)
    profile = final_profiles()[personality.name]
    start, end = idx(2026, 11, 2), idx(2026, 11, 30)
    series = simulate_household(hogar_id, profile, sensors, start, end)
    humors = set()
    for day in DAYS:
        hours = range(day.toordinal() * 24, day.toordinal() * 24 + 24)
        regular = math.fsum(
            readings[index - start].regular for readings in series.values() for index in hours
        )
        factor = personality.weekend_factor if day.weekday() >= 5 else 1.0
        expected = personality.kwh_per_day * factor
        low = expected * personality.humor_min * (1 - CONSERVATION_TOLERANCE)
        high = expected * personality.humor_max * (1 + CONSERVATION_TOLERANCE)
        assert low <= regular <= high, day
        humors.add(round(regular / expected, 9))
    assert len(humors) == len(DAYS)  # el humor se sortea cada día


@each_personality
def test_events_only_add_to_the_zones_and_hours_of_the_profile(personality):
    """Condición de validez 4: lo que excede el consumo regular sale de `picos_config`."""
    hogar_id, sensors = full_household(personality)
    profile = final_profiles()[personality.name]
    series = simulate_household(hogar_id, profile, sensors, VALIDATION_START, VALIDATION_END)
    for zone, readings in series.items():
        assert all(r.events >= 0 and r.total == r.regular + r.events for r in readings)
        if zone not in profile["picos_config"]:
            assert {r.events for r in readings} == {0.0}, zone


@each_personality
def test_hourly_shape_follows_the_curve_within_the_noise_bounds(personality):
    hogar_id, sensors = full_household(personality)
    profile = final_profiles()[personality.name]
    margin = noise_margin(profile)
    for zone in sensors:
        curve = personality.hourly_share.get(zone, personality.hourly_share["base"])
        for day in DAYS:
            result = regular_day(hogar_id, day, zone, profile)
            for share, weight in zip(result.weights, curve, strict=True):
                low = weight * (1 - margin) / (1 + margin) - CONSERVATION_TOLERANCE
                high = weight * (1 + margin) / (1 - margin) + CONSERVATION_TOLERANCE
                assert low <= share <= high, (zone, day)


@each_personality
def test_without_noise_every_hour_is_the_average_of_the_personality(personality):
    """Sin ruido, la hora vale promedio de la zona × humor × factor de calendario."""
    hogar_id, sensors = full_household(personality)
    profile = final_profiles()[personality.name]
    profile["ruido_config"]["intensidad"] = 0.0
    for zone in sensors:
        for day in DAYS[:7]:
            result = regular_day(hogar_id, day, zone, profile)
            scale = result.humor * result.calendar_factor
            for hour, kwh in enumerate(result.regular):
                expected = personality.zone_kwh_for_hour(zone, hour) * scale
                # La curva suma 1 ± 1e-10 (CT03) y Q la renormaliza.
                assert math.isclose(kwh, expected, rel_tol=2 * CONSERVATION_TOLERANCE), zone


# ------------------------------------------------------------------ reproducibilidad
@each_personality
def test_same_household_and_date_give_identical_rows(personality):
    assert backfill(personality) == backfill(personality)
    assert backfill(personality, "a") != backfill(personality, "b")


@each_personality
def test_a_shifted_backfill_repeats_the_regular_consumption_of_the_shared_hours(personality):
    """La semilla es por hogar y fecha: la misma hora vale igual en dos ventanas distintas.

    Se quitan los picos porque la frontera (A10) descarta los eventos anteriores a la primera hora.
    """
    hogar_id, sensors = full_household(personality)
    profile = final_profiles()[personality.name]
    profile["picos_config"] = {}
    first = generate_backfill(hogar_id, profile, sensors, NOW)
    second = generate_backfill(hogar_id, profile, sensors, NOW + timedelta(hours=37))
    values = {(row["sensor_id"], row["fecha_hora"]): row["consumo_kwh"] for row in first}
    shared = [row for row in second if (row["sensor_id"], row["fecha_hora"]) in values]
    assert len(shared) == (720 - 37) * len(sensors)
    for row in shared:
        assert row["consumo_kwh"] == values[(row["sensor_id"], row["fecha_hora"])]


# ------------------------------------------------------------------ equivalencia con la referencia
@dataclass
class ReferenceRun:
    """Agregados de los 100 hogares de validación de una personalidad."""

    totals: list[float] = field(default_factory=list)  # kWh del mes, por semilla
    hourly: dict[str, list[float]] = field(  # kWh acumulados por tipo de día y hora
        default_factory=lambda: {"laboral": [0.0] * 24, "fin_semana": [0.0] * 24}
    )
    daily_regular: dict[str, list[float]] = field(  # kWh regulares de cada hogar y día
        default_factory=lambda: {"laboral": [], "fin_semana": []}
    )


def day_kind(ordinal: int) -> str:
    return "fin_semana" if date.fromordinal(ordinal).weekday() >= 5 else "laboral"


@cache
def run_reference(name: str) -> ReferenceRun:
    """Repite la validación ciega del Avance 03 para una personalidad: 100 hogares × 30 días.

    En caché por personalidad: ejecutar las pruebas de una sola no calcula las cinco.
    """
    profile = final_profiles()[name]
    reference = frozen_references()[name]
    run = ReferenceRun()
    for number in range(REFERENCE_SEEDS):
        label = f"val|{name}|val-{number:03d}"
        household = create_household(label, reference["vivienda"], reference["zonas"])
        series = simulate_household(
            household.id, profile, household.zones, VALIDATION_START, VALIDATION_END
        )
        run.totals.append(math.fsum(r.total for readings in series.values() for r in readings))
        regular = defaultdict(float)
        for readings in series.values():
            for reading in readings:
                ordinal, hour = divmod(reading.index, 24)
                regular[ordinal] += reading.regular
                run.hourly[day_kind(ordinal)][hour] += reading.total
        for ordinal, kwh in regular.items():
            run.daily_regular[day_kind(ordinal)].append(kwh)
    return run


@each_personality
def test_totals_are_identical_to_the_published_reference(personality):
    """El port da, bit a bit, los totales que publicó el Avance 03 con las mismas semillas."""
    published = [
        float(row["total_kwh"])
        for row in read_csv("validacion_totales_por_semilla.csv")
        if row["personalidad"] == personality.name
    ]
    assert len(published) == REFERENCE_SEEDS
    assert run_reference(personality.name).totals == published


@each_personality
def test_hourly_profile_is_the_published_one(personality):
    """kWh medios por hora, en laboral y en fin de semana, iguales a los publicados."""
    rows = [
        row
        for row in read_csv("validacion_perfil_horario.csv")
        if row["personalidad"] == personality.name
    ]
    assert {row["tipo_dia"] for row in rows} == {"laboral", "fin_semana"}
    run = run_reference(personality.name)
    for row in rows:
        days = len(run.daily_regular[row["tipo_dia"]])
        for hour, kwh in enumerate(run.hourly[row["tipo_dia"]]):
            expected = float(row[f"h{hour:02d}_kwh"])
            assert math.isclose(kwh / days, expected, rel_tol=CONSERVATION_TOLERANCE), hour


@each_personality
def test_mean_realizations_and_weekend_ratio_meet_the_frozen_criteria(personality):
    """CE01: media a ±3 %; CE03: >= 95 de 100 a ±10 %; CE15: razón fin de semana a ±5 %."""
    reference = frozen_references()[personality.name]
    run = run_reference(personality.name)
    target = float(reference["objetivo_validacion_kwh"])
    assert abs(math.fsum(run.totals) / len(run.totals) / target - 1) <= 0.03
    assert sum(abs(total / target - 1) <= 0.10 for total in run.totals) >= 95

    averages = {k: math.fsum(values) / len(values) for k, values in run.daily_regular.items()}
    ratio = averages["fin_semana"] / averages["laboral"]
    assert abs(ratio / float(reference["razon_fin_semana_laboral_objetivo"]) - 1) <= 0.05


def test_means_of_the_reference_households_respect_the_order():
    """CE11: compacto < eficiente < intermedio < familiar < amplio."""
    means = [math.fsum(run_reference(name).totals) for name in PERSONALITY_ORDER]
    assert means == sorted(means)
    assert len(set(means)) == 5


# ------------------------------------------------------------------ perfil como dato
@each_personality
def test_official_profile_is_valid_and_not_modified_by_the_simulator(personality):
    """El perfil entra por parámetro: se valida y no se altera."""
    profile = final_profiles()[personality.name]
    assert validate_profile(profile) == []
    hogar_id, sensors = full_household(personality)
    rows = generate_backfill(hogar_id, profile, sensors, NOW)
    assert profile == final_profiles()[personality.name]
    assert max(hour_index(row["fecha_hora"]) for row in rows) == idx(2026, 11, 22, 14)
