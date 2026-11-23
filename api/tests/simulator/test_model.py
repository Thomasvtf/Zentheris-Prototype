"""M01 a M21 de la referencia (Avance 03, `pruebas/test_modelo.py`).

Conservación, eventos, fronteras, zonas ausentes, reproducibilidad, recuperación e idempotencia.
"""

import hashlib
import json
import math
import os
import random
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path

import pytest

from app.domain.simulator.constants import CONSERVATION_TOLERANCE, TIMEZONE, VERSION_MODELO
from app.domain.simulator.engine import (
    DegenerateRealizationError,
    Event,
    calculate_weights,
    day_events,
    hour_from_index,
    hour_index,
    household_total,
    noise_epsilons,
    regular_day,
    round_kwh,
    simulate_backfill,
    simulate_household,
    simulate_zone,
    simulate_zone_detail,
    spread_event,
    to_reading_rows,
)
from app.domain.simulator.seeds import canonical_serialization, derive_seed
from app.domain.zone_rules import BASIC_ZONES, ZONE_TYPES
from tests.simulator.support import (
    MemoryStore,
    Profile,
    almost_equal,
    bogota,
    create_household,
    generate_and_store,
    idx,
    recover,
    sample_profile,
    sample_profiles,
    stable_id,
)

API_ROOT = Path(__file__).resolve().parents[2]
HOUSEHOLD = create_household("modelo-9", "duplex", ZONE_TYPES)
START = idx(2026, 9, 1)
END = idx(2026, 10, 1)
DAYS = [date.fromordinal(ordinal) for ordinal in range(START // 24, END // 24)]


@pytest.fixture(scope="module")
def profiles() -> dict[str, Profile]:
    return sample_profiles()


@pytest.fixture(scope="module")
def series(profiles):
    return {
        name: simulate_household(HOUSEHOLD.id, profile, ZONE_TYPES, START, END)
        for name, profile in profiles.items()
    }


def midnight_profile() -> Profile:
    """Un único evento diario de 30 min que empieza a las 23:50 en cocina.

    Probabilidad 1 con multiplicador 0 en 0–23 h y 1 en 23–24 h.
    """
    profile = sample_profile()
    profile["picos_config"] = {
        "cocina": {
            "probabilidad": 1.0,
            "franjas": [{"desde": 0, "hasta": 23, "multiplicador": 0.0}],
            "potencia_w": [1200, 1200],
            "duracion_min": [30, 30],
            "minuto_inicio": [50, 50],
            "fraccion_uso": [0.5, 0.5],
        }
    }
    return profile


def test_m01_finite_and_not_negative(series):
    """M01 Toda lectura es finita y >= 0 (validez 1)."""
    for name, zones in series.items():
        for zone, readings in zones.items():
            assert len(readings) == 720, (name, zone)
            for reading in readings:
                assert math.isfinite(reading.total), (name, zone)
                assert min(reading.regular, reading.events, reading.total) >= 0, (name, zone)


def test_m02_weights_add_up_to_one_and_regular_to_target(profiles):
    """M02 Q suma 1 por zona y día y la suma regular diaria es T (validez 2 y 3, CT06)."""
    worst = 0.0
    for profile in profiles.values():
        for day in DAYS:
            for zone in ZONE_TYPES:
                result = regular_day(HOUSEHOLD.id, day, zone, profile)
                assert abs(math.fsum(result.weights) - 1.0) <= 1e-12
                error = abs(math.fsum(result.regular) - result.target) / max(1.0, result.target)
                worst = max(worst, error)
    assert worst <= CONSERVATION_TOLERANCE


def test_m03_humor_and_factor(profiles):
    """M03 H único por hogar-día dentro del rango; F solo sábado y domingo."""
    profile = profiles["Consumo amplio"]
    for day in DAYS:
        results = [regular_day(HOUSEHOLD.id, day, zone, profile) for zone in ZONE_TYPES]
        humors = {result.humor for result in results}
        assert len(humors) == 1
        assert profile["humor_min"] <= humors.pop() <= profile["humor_max"]
        expected = profile["factor_fin_semana"] if day.weekday() >= 5 else 1.0
        assert {result.calendar_factor for result in results} == {expected}


def test_m04_noise_restarts_every_day(profiles):
    """M04 n[0] = σ·ε0 (n[−1]=0, A07) y la recurrencia n(t)=φn(t−1)+σε."""
    profile = profiles["Consumo familiar"]
    config = profile["ruido_config"]
    day = date(2026, 9, 3)
    epsilons = noise_epsilons(HOUSEHOLD.id, day, "cocina")
    noise = regular_day(HOUSEHOLD.id, day, "cocina", profile).noise
    assert noise[0] == config["intensidad"] * epsilons[0]
    for hour in range(1, 24):
        expected = config["memoria"] * noise[hour - 1] + config["intensidad"] * epsilons[hour]
        assert almost_equal(noise[hour], expected, 15)


def test_m05_event_energy_and_spread(profiles):
    """M05 E = P·(D/60)·f/1000 y reparto por minutos entre horas (CT07)."""
    energy = 1200 * (20 / 60) * 0.5 / 1000
    event = Event("cocina", 1000 * 1440 + 10 * 60 + 50, 20.0, 1200.0, 0.5, energy)
    shares = spread_event(event)
    assert almost_equal(event.energy_kwh, 0.2, 15)
    assert sorted(shares) == [1000 * 24 + 10, 1000 * 24 + 11]
    assert almost_equal(shares[1000 * 24 + 10], 0.1, 15)
    assert almost_equal(shares[1000 * 24 + 11], 0.1, 15)
    worst, count = 0.0, 0
    for profile in profiles.values():
        for day in DAYS:
            for zone in ZONE_TYPES:
                for drawn in day_events(HOUSEHOLD.id, day, zone, profile):
                    count += 1
                    config = profile["picos_config"][zone]
                    low, high = config["potencia_w"]
                    assert low <= drawn.power_w <= high
                    low, high = config["duracion_min"]
                    assert low <= drawn.duration_min <= high
                    minute = (drawn.start_min % 1440) % 60
                    low, high = config["minuto_inicio"]
                    assert low <= minute <= high
                    assert minute == int(minute)
                    low, high = config["fraccion_uso"]
                    assert low <= drawn.usage_fraction <= high
                    closed = drawn.power_w * (drawn.duration_min / 60) * drawn.usage_fraction / 1000
                    worst = max(worst, abs(math.fsum(spread_event(drawn).values()) - closed))
    assert count > 50
    assert worst <= 1e-10


def test_m06_midnight():
    """M06 Un evento 23:50 + 30 min aporta 1/3 a las 23 h y 2/3 a las 00 h del día siguiente."""
    energy = 1200 * 0.5 * 0.5 / 1000
    midnight = idx(2026, 9, 10)
    readings = simulate_zone(
        HOUSEHOLD.id, midnight_profile(), "cocina", midnight - 1, midnight + 1, START
    )
    events = {reading.index: reading.events for reading in readings}
    assert almost_equal(events[midnight - 1], energy / 3, 14)
    assert almost_equal(events[midnight], 2 * energy / 3, 14)


def test_m07_backfill_frontiers():
    """M07 Backfill: 720 h contiguas; sin cola izquierda (A10); cola derecha descartada
    y recuperada por la hora siguiente (A09); conservación evento exportado + descartado."""
    profile = midnight_profile()
    household = create_household("fronteras", "apartamento", BASIC_ZONES)
    series = simulate_backfill(household.id, profile, household.zones, bogota(2026, 11, 1, 0, 30))
    end = idx(2026, 11, 1)
    start = end - 720
    readings = series["cocina"]
    assert [reading.index for reading in readings] == list(range(start, end))
    assert readings[0].events == 0.0  # 00 h del primer día: sin cola previa
    energy = 1200 * 0.5 * 0.5 / 1000
    exported = math.fsum(reading.events for reading in readings)
    assert almost_equal(exported, 30 * energy - 2 * energy / 3, 12)
    following = simulate_zone(household.id, profile, "cocina", end, end + 1, start)[0]
    assert almost_equal(following.events, 2 * energy / 3, 14)
    assert almost_equal(exported + following.events, 30 * energy, 12)


def test_m08_fallback_curve():
    """M08 Zona sin curva propia usa base; con σ=0, Q es exactamente la curva."""
    profile = sample_profile()
    profile["ruido_config"]["intensidad"] = 0.0
    day = date(2026, 9, 5)
    living_room = regular_day(HOUSEHOLD.id, day, "sala", profile).weights
    bedroom = regular_day(HOUSEHOLD.id, day, "dormitorio", profile).weights
    base = profile["curva_horaria"]["base"]
    own = profile["curva_horaria"]["dormitorio"]
    for hour in range(24):
        assert almost_equal(living_room[hour], base[hour] / math.fsum(base), 15)
        assert almost_equal(bedroom[hour], own[hour] / math.fsum(own), 15)


def test_m09_absent_zone(profiles, series):
    """M09 Zona ausente: cero filas, sin redistribución, demás zonas idénticas (RN-IV-07, CT09)."""
    profile = profiles["Consumo amplio"]
    full = series["Consumo amplio"]
    absent = {"oficina", "garaje"}
    partial = simulate_household(HOUSEHOLD.id, profile, set(ZONE_TYPES) - absent, START, END)
    assert set(partial) == set(ZONE_TYPES) - absent
    for zone, readings in partial.items():
        assert readings == full[zone]
    total_full = math.fsum(household_total(full).values())
    total_partial = math.fsum(household_total(partial).values())
    removed = math.fsum(reading.total for zone in absent for reading in full[zone])
    assert almost_equal(total_full - total_partial, removed, 9)


def test_m10_total_is_the_sum_of_zones(series):
    """M10 Total horario del hogar = suma de zonas; no hay lectura extra."""
    zones = series["Consumo familiar"]
    totals = household_total(zones)
    assert len(totals) == 720
    for index in (START, START + 100, END - 1):
        expected = math.fsum(
            {reading.index: reading.total for reading in readings}[index]
            for readings in zones.values()
        )
        assert almost_equal(totals[index], expected, 12)


HASHSEED_SCRIPT = """
import sys
sys.path.insert(0, sys.argv[1])
import hashlib, json
from app.domain.simulator.engine import simulate_household
from app.domain.zone_rules import ZONE_TYPES
from tests.simulator.support import create_household, idx, sample_profile
household = create_household("modelo-9", "duplex", ZONE_TYPES)
start = idx(2026, 9, 1)
profile = sample_profile("Consumo amplio")
series = simulate_household(household.id, profile, household.zones, start, start + 72)
print(hashlib.sha256(json.dumps(series, sort_keys=True).encode()).hexdigest())
"""


def test_m11_reproducibility_and_hashseed(profiles):
    """M11 Misma entrada => resultado idéntico, también con distinto PYTHONHASHSEED

    (validez 5, CT10). El subproceso solo ejecuta código de este repositorio.
    """
    profile = profiles["Consumo intermedio"]

    def run(hogar_id):
        return simulate_household(hogar_id, profile, ZONE_TYPES, START, START + 48)

    first = run(HOUSEHOLD.id)
    assert first == run(HOUSEHOLD.id)
    assert first != run(create_household("otro", "duplex", ZONE_TYPES).id)

    digests = set()
    for seed in ("0", "1", "12345", "random"):
        result = subprocess.run(
            [sys.executable, "-P", "-c", HASHSEED_SCRIPT, str(API_ROOT)],
            env=dict(os.environ, PYTHONHASHSEED=seed),
            capture_output=True,
            text=True,
            check=True,
        )
        digests.add(result.stdout.strip())
    in_process = simulate_household(
        HOUSEHOLD.id, sample_profile("Consumo amplio"), ZONE_TYPES, START, START + 72
    )
    text = json.dumps(in_process, sort_keys=True)
    assert digests == {hashlib.sha256(text.encode()).hexdigest()}


def test_m12_canonical_seed():
    """M12 Semilla SHA-256 canónica: dominios y zonas separados; valor de referencia fijo."""
    hogar_id, day, version = str(HOUSEHOLD.id), date(2026, 9, 1), "zentheris-4.3-ref-1"
    assert version == VERSION_MODELO
    seeds = {derive_seed(hogar_id, day, version, zone, "ruido") for zone in ZONE_TYPES}
    assert len(seeds) == 9
    noise = derive_seed(hogar_id, day, version, "cocina", "ruido")
    assert noise != derive_seed(hogar_id, day, version, "cocina", "eventos")
    living_room = derive_seed(hogar_id, day, version, "sala", "ruido")
    assert derive_seed(hogar_id.upper(), day, version, "sala", "ruido") == living_room
    assert derive_seed(HOUSEHOLD.id, day, version, "sala", "ruido") == living_room
    fixed_id = "00000000-0000-4000-8000-000000000001"
    canonical = (
        b'{"dominio":"humor","fecha":"2026-09-01",'
        b'"hogar_id":"00000000-0000-4000-8000-000000000001",'
        b'"version":"zentheris-4.3-ref-1","zona":null}'
    )
    assert canonical_serialization(fixed_id, day, version, None, "humor") == canonical
    expected = int(hashlib.sha256(canonical).hexdigest(), 16)
    assert derive_seed(fixed_id, day, version, None, "humor") == expected


def test_m13_degenerate():
    """M13 Σw' <= 0 se detecta y rechaza; con σ/(1−φ)<1 nunca ocurre (A08, CT05)."""
    curve = [1.0] + [0.0] * 23
    with pytest.raises(DegenerateRealizationError):
        calculate_weights(curve, [-1.0] + [0.0] * 23, 0.0, 1.0)
    rng = random.Random(7)
    base = sample_profile()["curva_horaria"]["base"]
    for _ in range(3000):
        memory = rng.uniform(0, 0.95)
        intensity = rng.uniform(0, 0.999) * (1 - memory)
        epsilons = [rng.choice((-1.0, 1.0)) for _ in range(24)]
        weights, noise = calculate_weights(base, epsilons, memory, intensity)
        assert all(abs(value) < 1 for value in noise)
        assert all(weight > 0 for weight in weights)


def test_m14_probability_zero_and_one():
    """M14 p=0 no genera eventos; p=1 genera exactamente uno por hora."""
    profile = sample_profile()
    config = profile["picos_config"]["cocina"]
    day = date(2026, 9, 2)
    config["probabilidad"] = 0.0
    assert day_events(HOUSEHOLD.id, day, "cocina", profile) == []
    config["probabilidad"] = 0.5  # ×2 en 18–21 => p=1 allí
    events = day_events(HOUSEHOLD.id, day, "cocina", profile)
    assert {18, 19, 20} <= {(event.start_min % 1440) // 60 for event in events}
    config["probabilidad"] = 1.0
    config["franjas"] = []
    assert len(day_events(HOUSEHOLD.id, day, "cocina", profile)) == 24


def test_m15_common_random_numbers():
    """M15 Cambiar picos no altera humor ni ruido: el componente regular es idéntico."""
    other = sample_profile()
    other["picos_config"]["cocina"]["probabilidad"] = 0.3
    a = simulate_zone(HOUSEHOLD.id, sample_profile(), "cocina", START, START + 96, START)
    b = simulate_zone(HOUSEHOLD.id, other, "cocina", START, START + 96, START)
    assert [reading.regular for reading in a] == [reading.regular for reading in b]
    assert [reading.events for reading in a] != [reading.events for reading in b]


def test_m16_incremental_equals_backfill(profiles):
    """M16 Generar hora a hora da lo mismo que el lote (A09/A11)."""
    profile = profiles["Consumo amplio"]
    batch = simulate_zone(HOUSEHOLD.id, profile, "lavanderia", START, START + 96, START)
    for expected in batch:
        index = expected.index
        single = simulate_zone(HOUSEHOLD.id, profile, "lavanderia", index, index + 1, START)[0]
        assert single.regular == expected.regular
        assert almost_equal(single.total, expected.total, 13)


def test_m17_recovery_and_idempotence(profiles):
    """M17 Rellena huecos y horas pendientes; no duplica ni reescribe (RN-IV-05, A13, CT11)."""
    profile = profiles["Consumo familiar"]
    household = create_household(
        "recuperacion", "apartamento", (*BASIC_ZONES, "oficina", "lavanderia")
    )
    store = MemoryStore()
    now = bogota(2026, 10, 20, 8, 15)
    end = idx(2026, 10, 20, 7) + 1
    start = end - 720
    assert generate_and_store(store, household, profile, start, end, start) == 720 * 6
    sensor_id = household.sensors["cocina"]
    gaps = random.Random(3).sample(range(start + 1, end), 15)
    for index in gaps:
        del store.rows[(sensor_id, hour_from_index(index))]
    tampered = (household.sensors["sala"], hour_from_index(start + 5))
    store.rows[tampered]["consumo_kwh"] = Decimal("9.9999")
    later = now + timedelta(hours=6)
    assert recover(store, household, profile, later) == 15 + 6 * 6
    assert store.rows[tampered]["consumo_kwh"] == Decimal("9.9999")
    new_end = end + 6
    for reading in simulate_zone(household.id, profile, "cocina", start, new_end, start):
        row = store.rows[(sensor_id, hour_from_index(reading.index))]
        assert row["consumo_kwh"] == round_kwh(reading.total)
    assert recover(store, household, profile, later) == 0
    assert len(store.rows) == 6 * (720 + 6)
    assert generate_and_store(store, household, profile, start, new_end, start) == 0


def test_m18_rounding_and_rows(series):
    """M18 NUMERIC(12,4): error <= 0,00005 por lectura y <= 0,036 por 720; calidad 'simulada';
    fecha_hora en America/Bogota (−05:00), una por hora (CT12, A12)."""
    zones = series["Consumo amplio"]
    sensors = {zone: stable_id("sensor", "m18", zone) for zone in zones}
    rows = to_reading_rows(sensors, zones)
    assert len(rows) == 720 * 9
    for zone, readings in zones.items():
        zone_rows = [row for row in rows if row["sensor_id"] == sensors[zone]]
        total_error = 0.0
        for reading, row in zip(readings, zone_rows, strict=True):
            error = abs(float(row["consumo_kwh"]) - reading.total)
            assert error <= 0.00005 + 1e-12
            assert row["consumo_kwh"].as_tuple().exponent == -4
            total_error += error
        assert total_error <= 0.036
    assert {row["calidad"] for row in rows} == {"simulada"}
    assert {row["fecha_hora"].utcoffset() for row in rows} == {timedelta(hours=-5)}
    assert {row["fecha_hora"].tzinfo for row in rows} == {TIMEZONE}
    hours = sorted({row["fecha_hora"] for row in rows})
    assert len(hours) == 720
    assert all(b - a == timedelta(hours=1) for a, b in pairwise(hours))


def test_m19_last_complete_hour():
    """M19 El backfill termina en la última hora completa (RN-XI-01) y tiene 720 horas."""
    household = create_household("ultima", "apartamento", BASIC_ZONES)
    for minute in (23, 0):
        now = bogota(2026, 10, 28, 15, minute)
        series = simulate_backfill(household.id, sample_profile(), household.zones, now)
        indexes = [reading.index for reading in series["sala"]]
        assert len(indexes) == 720
        assert indexes[-1] == idx(2026, 10, 28, 14)


def test_m20_traceable_events(profiles):
    """M20 Toda energía adicional proviene de eventos sorteados (validez 4, A16)."""
    detail = simulate_zone_detail(
        HOUSEHOLD.id, profiles["Consumo amplio"], "lavanderia", START, END, START
    )
    rebuilt: dict[int, float] = {}
    for event in detail.events:
        for index, kwh in spread_event(event).items():
            if START <= index < END:
                rebuilt[index] = rebuilt.get(index, 0.0) + kwh
    for reading in detail.readings:
        assert almost_equal(reading.events, rebuilt.get(reading.index, 0.0), 12)
    without_peaks = sample_profile("Consumo amplio")
    without_peaks["picos_config"] = {}
    readings = simulate_zone(HOUSEHOLD.id, without_peaks, "lavanderia", START, END, START)
    assert {reading.events for reading in readings} == {0.0}


def test_m21_frontier_in_the_middle_of_the_day():
    """M21 Backfill que empieza a las 15 h: un evento de las 14:50 del primer día no entra (A10),
    el de los días siguientes sí aporta 2/3 a las 15 h."""
    profile = sample_profile()
    profile["picos_config"] = {
        "sala": {
            "probabilidad": 1.0,
            "franjas": [
                {"desde": 0, "hasta": 14, "multiplicador": 0.0},
                {"desde": 15, "hasta": 24, "multiplicador": 0.0},
            ],
            "potencia_w": [600, 600],
            "duracion_min": [30, 30],
            "minuto_inicio": [50, 50],
            "fraccion_uso": [1.0, 1.0],
        }
    }
    household = create_household("frontera-15h", "apartamento", BASIC_ZONES)
    now = bogota(2026, 10, 28, 15, 23)
    readings = simulate_backfill(household.id, profile, household.zones, now)["sala"]
    energy = 600 * 0.5 / 1000
    assert readings[0].index == idx(2026, 9, 28, 15)
    assert readings[0].events == 0.0
    assert almost_equal(readings[24].events, 2 * energy / 3, 14)
    exported = math.fsum(reading.events for reading in readings)
    assert almost_equal(exported, 29 * energy + energy / 3, 12)


# ------------------------------------------------ fuera de la referencia
def test_naive_datetime_is_rejected():
    """Sin zona horaria se interpretaría con la hora del servidor (UTC en Render)."""
    with pytest.raises(ValueError, match="zona horaria"):
        hour_index(bogota(2026, 10, 28, 15).replace(tzinfo=None))


def test_unknown_draw_domain_is_rejected():
    with pytest.raises(ValueError, match="dominio desconocido"):
        derive_seed(HOUSEHOLD.id, date(2026, 9, 1), VERSION_MODELO, None, "otro")


def test_frontier_after_start_is_rejected():
    with pytest.raises(ValueError, match="frontier"):
        simulate_zone(HOUSEHOLD.id, sample_profile(), "sala", START, START + 1, START + 1)


@pytest.mark.parametrize(("duration", "energy"), [(0.0, 0.0), (0.0, 1.0), (30.0, 0.0)])
def test_event_without_duration_or_energy_spreads_nothing(duration, energy):
    assert spread_event(Event("cocina", 1440, duration, 1200.0, 0.5, energy)) == {}
