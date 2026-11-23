"""B-04 · Recuperación: Servidor apagado 5 h y luego una consulta.

Esperado: 5 h × zonas nuevas, idénticas a las de una generación continua **[ref]**. Regla: RN-IV-05, DC-34.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Parte de dominio: las filas que genera la recuperación. La consulta y la base no se prueban aquí."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.simulator import (
    TIMEZONE,
    SensorGaps,
    generate_backfill,
    generate_missing_readings,
    generate_readings_for_gaps,
    hour_from_index,
    recovery_end_hour,
)
from app.domain.simulator.engine import simulate_household, to_reading_rows
from tests.helpers.personalities import load_personalities
from tests.simulator.support import bogota, final_profiles, idx, stable_id

HOURS_OFF = 5
NOW = bogota(2026, 11, 21, 22, 10)  # el apagado cruza la medianoche de sábado a domingo
LATER = NOW + timedelta(hours=HOURS_OFF)
END = idx(2026, 11, 21, 22)
START = END - 720

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


class Household:
    """Hogar con todas las zonas de la personalidad y su backfill ya guardado."""

    def __init__(self, personality, profile=None):
        self.id = stable_id("hogar", "b04", personality.name)
        self.sensors = {
            zone: stable_id("sensor", "b04", personality.name, zone)
            for zone in personality.zone_kwh_per_day
        }
        self.profile = profile or final_profiles()[personality.name]
        self.rows = generate_backfill(self.id, self.profile, self.sensors, NOW)

    def existing_hours(self, rows=None):
        rows = self.rows if rows is None else rows
        return {
            zone: [row["fecha_hora"] for row in rows if row["sensor_id"] == sensor]
            for zone, sensor in self.sensors.items()
        }

    def recover(self, existing, now=LATER):
        return generate_missing_readings(self.id, self.profile, self.sensors, existing, now)

    def continuous(self, end):
        """Lo que habría generado sin apagarse, con la misma frontera (primera lectura)."""
        series = simulate_household(self.id, self.profile, self.sensors, START, end, START)
        return to_reading_rows(self.sensors, series)


def by_key(rows):
    return {(row["sensor_id"], row["fecha_hora"]): row for row in rows}


@each_personality
def test_five_hours_off_generate_exactly_the_continuous_rows(personality):
    household = Household(personality)
    recovered = household.recover(household.existing_hours())
    assert len(recovered) == HOURS_OFF * len(household.sensors)
    off_hours = {hour_from_index(index) for index in range(END, END + HOURS_OFF)}
    expected = [
        row for row in household.continuous(END + HOURS_OFF) if row["fecha_hora"] in off_hours
    ]
    assert by_key(recovered) == by_key(expected)
    assert len(by_key(recovered)) == len(recovered)
    # Backfill + recuperación = generación continua completa.
    assert by_key(household.rows + recovered) == by_key(household.continuous(END + HOURS_OFF))


@each_personality
def test_hour_by_hour_equals_recovering_the_five_hours_at_once(personality):
    household = Household(personality)
    rows = list(household.rows)
    for hour in range(1, HOURS_OFF + 1):
        new = household.recover(household.existing_hours(rows), NOW + timedelta(hours=hour))
        assert len(new) == len(household.sensors)
        rows += new
    at_once = household.recover(household.existing_hours())
    assert by_key(rows) == by_key(household.rows + at_once)


@each_personality
def test_recovery_twice_generates_nothing_the_second_time(personality):
    household = Household(personality)
    recovered = household.recover(household.existing_hours())
    assert household.recover(household.existing_hours(household.rows + recovered)) == []


@each_personality
def test_internal_gaps_are_filled_with_the_original_rows(personality):
    """A13: también completa huecos internos, sin repetir lo que existe."""
    household = Household(personality)
    sensor = household.sensors["cocina"]
    gaps = {hour_from_index(START + offset) for offset in (1, 100, 101, 719)}
    removed = [
        row for row in household.rows if row["sensor_id"] == sensor and row["fecha_hora"] in gaps
    ]
    kept = [row for row in household.rows if row not in removed]
    assert household.recover(household.existing_hours(kept), NOW) == removed


def test_the_tail_of_an_event_before_the_shutdown_is_recovered():
    """Un evento de la última hora guardada aporta su sobrante a la primera recuperada (A09)."""
    personality = load_personalities()["Consumo amplio"]
    profile = final_profiles()[personality.name]
    profile["picos_config"] = {
        "cocina": {
            "probabilidad": 1.0,
            "franjas": [
                {"desde": 0, "hasta": 21, "multiplicador": 0.0},
                {"desde": 22, "hasta": 24, "multiplicador": 0.0},
            ],
            "potencia_w": [1200, 1200],
            "duracion_min": [30, 30],
            "minuto_inicio": [50, 50],
            "fraccion_uso": [1.0, 1.0],
        }
    }
    household = Household(personality, profile)
    recovered = household.recover(household.existing_hours())
    assert by_key(recovered).items() <= by_key(household.continuous(END + HOURS_OFF)).items()
    quiet = Household(personality, {**profile, "picos_config": {}})
    key = (household.sensors["cocina"], hour_from_index(END))
    tail = (
        by_key(recovered)[key]["consumo_kwh"]
        - by_key(quiet.recover(quiet.existing_hours()))[key]["consumo_kwh"]
    )
    assert float(tail) == pytest.approx(1.2 * 0.5 * 2 / 3, abs=0.0001)  # dos redondeos a 4 dec.


def test_hours_stored_in_utc_are_recognized():
    """La base devuelve `timestamptz` en otra zona horaria: es el mismo instante."""
    household = Household(load_personalities()["Consumo familiar"])
    in_utc = {
        zone: [moment.astimezone(UTC) for moment in moments]
        for zone, moments in household.existing_hours().items()
    }
    assert household.recover(in_utc, LATER.astimezone(UTC)) == household.recover(
        household.existing_hours()
    )


def test_a_zone_without_readings_generates_nothing():
    household = Household(load_personalities()["Consumo familiar"])
    existing = household.existing_hours()
    existing["sala"] = []
    del existing["bano"]
    recovered = household.recover(existing)
    silent = {household.sensors["sala"], household.sensors["bano"]}
    assert not silent & {row["sensor_id"] for row in recovered}
    assert len(recovered) == HOURS_OFF * (len(household.sensors) - 2)


def test_before_the_next_complete_hour_there_is_nothing_to_recover():
    household = Household(load_personalities()["Consumo familiar"])
    existing = household.existing_hours()
    assert household.recover(existing, bogota(2026, 11, 21, 22, 59)) == []
    assert len(household.recover(existing, bogota(2026, 11, 21, 23))) == len(household.sensors)


# ------------------------------------------------------------ variante por huecos (fase 5)
# La capa de datos entrega, por sensor, su primera lectura y las horas sin lectura hasta
# `recovery_end_hour(now)` (no todas las horas guardadas). Estas pruebas demuestran que esa
# variante da lo mismo que la recuperación a partir de las horas existentes.


def gaps_from_rows(household, rows, now=LATER):
    """Los huecos tal como los calcularía la base: paso de 1 h desde la primera lectura."""
    end_hour = recovery_end_hour(now)
    gaps = {}
    for zone, sensor in household.sensors.items():
        stored = {row["fecha_hora"] for row in rows if row["sensor_id"] == sensor}
        if not stored:
            gaps[zone] = SensorGaps(sensor, None, [])
            continue
        first = min(stored)
        missing, moment = [], first
        while moment <= end_hour:
            if moment not in stored:
                missing.append(moment)
            moment += timedelta(hours=1)
        gaps[zone] = SensorGaps(sensor, first, missing)
    return gaps


def recover_gaps(household, gaps, now=LATER):
    return generate_readings_for_gaps(household.id, household.profile, gaps, now)


@each_personality
def test_gaps_of_five_hours_off_equal_the_recovery_from_existing_hours(personality):
    """B-04 por huecos: las 5 h de apagado cruzan la medianoche de sábado a domingo."""
    household = Household(personality)
    gaps = gaps_from_rows(household, household.rows)
    assert all(len(gap.missing_hours) == HOURS_OFF for gap in gaps.values())
    off_days = {moment.date() for gap in gaps.values() for moment in gap.missing_hours}
    assert len(off_days) == 2  # cruza la medianoche
    recovered = recover_gaps(household, gaps)
    assert recovered == household.recover(household.existing_hours())
    assert len(recovered) == HOURS_OFF * len(household.sensors)
    assert by_key(household.rows + recovered) == by_key(household.continuous(END + HOURS_OFF))


@each_personality
def test_gaps_with_internal_holes_equal_the_recovery_from_existing_hours(personality):
    """A13 por huecos: huecos internos (incluida la hora siguiente a la frontera) y apagado."""
    household = Household(personality)
    holes = {hour_from_index(START + offset) for offset in (1, 100, 101, 719)}
    kept = [row for row in household.rows if row["fecha_hora"] not in holes]
    recovered = recover_gaps(household, gaps_from_rows(household, kept))
    assert recovered == household.recover(household.existing_hours(kept))
    assert len(recovered) == (len(holes) + HOURS_OFF) * len(household.sensors)
    assert by_key(kept + recovered) == by_key(household.continuous(END + HOURS_OFF))


@each_personality
def test_gaps_hour_by_hour_equal_the_continuous_generation(personality):
    household = Household(personality)
    rows = list(household.rows)
    for hour in range(1, HOURS_OFF + 1):
        now = NOW + timedelta(hours=hour)
        new = recover_gaps(household, gaps_from_rows(household, rows, now), now)
        assert len(new) == len(household.sensors)
        rows += new
    assert by_key(rows) == by_key(household.continuous(END + HOURS_OFF))


@each_personality
def test_hours_outside_the_range_are_ignored(personality):
    """Antes de la frontera o después de la última hora completa no se genera nada."""
    household = Household(personality)
    gaps = gaps_from_rows(household, household.rows)
    outside = [
        hour_from_index(START - 1),
        hour_from_index(START - 48),
        hour_from_index(END + HOURS_OFF),  # aún no está completa en LATER
        hour_from_index(END + HOURS_OFF + 30),
    ]
    widened = {
        zone: gap._replace(missing_hours=[*outside, *gap.missing_hours])
        for zone, gap in gaps.items()
    }
    assert recover_gaps(household, widened) == recover_gaps(household, gaps)
    only_outside = {zone: gap._replace(missing_hours=outside) for zone, gap in gaps.items()}
    assert recover_gaps(household, only_outside) == []


@each_personality
def test_repeated_missing_hours_do_not_duplicate_rows(personality):
    household = Household(personality)
    gaps = gaps_from_rows(household, household.rows)
    repeated = {
        zone: gap._replace(
            missing_hours=[
                *reversed(gap.missing_hours),
                *gap.missing_hours,
                *(moment.astimezone(UTC) for moment in gap.missing_hours),  # mismo instante
            ]
        )
        for zone, gap in gaps.items()
    }
    recovered = recover_gaps(household, repeated)
    assert recovered == recover_gaps(household, gaps)
    assert len(by_key(recovered)) == len(recovered) == HOURS_OFF * len(household.sensors)


def test_rows_are_ordered_by_zone_and_then_by_hour():
    household = Household(load_personalities()["Consumo amplio"])
    gaps = gaps_from_rows(household, household.rows)
    shuffled = {
        zone: gaps[zone]._replace(missing_hours=list(reversed(gaps[zone].missing_hours)))
        for zone in reversed(list(gaps))
    }
    recovered = recover_gaps(household, shuffled)
    zone_of = {sensor: zone for zone, sensor in household.sensors.items()}
    keys = [(zone_of[row["sensor_id"]], row["fecha_hora"]) for row in recovered]
    assert keys == sorted(keys)


def test_a_sensor_without_readings_generates_nothing():
    household = Household(load_personalities()["Consumo familiar"])
    gaps = gaps_from_rows(household, household.rows)
    off_hours = list(gaps["cocina"].missing_hours)
    gaps["sala"] = SensorGaps(household.sensors["sala"], None, off_hours)
    gaps["bano"] = SensorGaps(household.sensors["bano"], None, [])
    recovered = recover_gaps(household, gaps)
    silent = {household.sensors["sala"], household.sensors["bano"]}
    assert not silent & {row["sensor_id"] for row in recovered}
    assert len(recovered) == HOURS_OFF * (len(household.sensors) - 2)
    assert recover_gaps(household, {}) == []
    only_silent = {"sala": SensorGaps(household.sensors["sala"], None, off_hours)}
    assert recover_gaps(household, only_silent) == []


def test_a_sensor_without_missing_hours_generates_nothing():
    household = Household(load_personalities()["Consumo familiar"])
    gaps = gaps_from_rows(household, household.rows, NOW)
    assert all(gap.first_hour is not None and not gap.missing_hours for gap in gaps.values())
    assert recover_gaps(household, gaps, NOW) == []


def test_gaps_in_utc_are_recognized():
    """La base devuelve `timestamptz` en UTC: son los mismos instantes."""
    household = Household(load_personalities()["Consumo familiar"])
    gaps = gaps_from_rows(household, household.rows)
    in_utc = {
        zone: SensorGaps(
            gap.sensor_id,
            gap.first_hour.astimezone(UTC),
            [moment.astimezone(UTC) for moment in gap.missing_hours],
        )
        for zone, gap in gaps.items()
    }
    recovered = recover_gaps(household, in_utc, LATER.astimezone(UTC))
    assert recovered == recover_gaps(household, gaps)
    assert all(row["fecha_hora"].tzinfo == TIMEZONE for row in recovered)


def test_recovery_end_hour_is_the_start_of_the_last_complete_hour():
    expected = bogota(2026, 11, 21, 21)
    assert recovery_end_hour(NOW) == expected
    assert recovery_end_hour(NOW).tzinfo == TIMEZONE
    assert recovery_end_hour(NOW.astimezone(UTC)) == expected  # 03:10 UTC del domingo
    assert recovery_end_hour(datetime(2026, 11, 22, 3, 10, tzinfo=UTC)).tzinfo == TIMEZONE
    assert recovery_end_hour(bogota(2026, 11, 21, 23)) == bogota(2026, 11, 21, 22)
    assert recovery_end_hour(bogota(2026, 11, 22, 0, 59)) == bogota(2026, 11, 21, 23)
    assert recovery_end_hour(datetime(2026, 11, 22, 5, 0, tzinfo=UTC)) == bogota(2026, 11, 21, 23)
    assert recovery_end_hour(LATER) == hour_from_index(END + HOURS_OFF - 1)


def test_recovery_end_hour_without_timezone_is_rejected():
    with pytest.raises(ValueError):
        recovery_end_hour(NOW.replace(tzinfo=None))
    household = Household(load_personalities()["Consumo compacto"])
    gaps = gaps_from_rows(household, household.rows)
    with pytest.raises(ValueError):
        recover_gaps(household, gaps, LATER.replace(tzinfo=None))
