"""Reglas de alertas y consejos (RN-XIV-07, RN-XIV-08, RN-XV-05, RN-XV-07, DC-24, DC-25, DC-32).

`app.domain.alert_rules`: puro, con los textos de `config_files/textos-backend.es-CO.json` y los
umbrales de `config_files/umbrales-estado.v1.json` leídos aquí y pasados por parámetro. Los casos
con consumo usan los promedios reales de las 5 personalidades (`tests/helpers/personalities.py`):
referencia de la zona = `zone_kwh_for_hour(zona, hora)`; +30 % = elevado; +60 % = crítico.
"""

import json
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path
from uuid import UUID

import pytest

from app.domain import alert_rules as R
from app.domain import formats as F
from app.domain import states as S
from app.domain.simulator import TIMEZONE
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities
from tests.simulator.support import stable_id

CONFIG_DIR = Path(__file__).resolve().parents[2] / "app" / "config_files"
DAY = date(2026, 11, 3)  # martes
HOGAR = UUID(int=100)
COCINA = UUID(int=1)
SALA = UUID(int=2)
OTRA = UUID(int=3)
ZONES = {COCINA: R.ZoneInfo(COCINA, "cocina"), SALA: R.ZoneInfo(SALA, "sala")}

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


@cache
def texts() -> F.BackendTexts:
    raw = json.loads((CONFIG_DIR / "textos-backend.es-CO.json").read_text(encoding="utf-8"))
    return F.parse_backend_texts(raw)


@cache
def thresholds() -> S.StateThresholds:
    raw = json.loads((CONFIG_DIR / "umbrales-estado.v1.json").read_text(encoding="utf-8"))
    return S.parse_thresholds(raw)


def at(day: date, hour: int, tz=TIMEZONE) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=TIMEZONE).astimezone(tz)


def zh(zona_id: UUID, hour_start: datetime, state: str, power: float | None = 0.9):
    return S.ZoneHourState(zona_id, hour_start, power, state)


def catalog_tip(regla: str, zona: str | None, variante: int) -> F.TipTemplate:
    return next(t for t in texts().tips
                if (t.regla_origen, t.zona, t.variante) == (regla, zona, variante))


# ------------------------------------------------------------------ A-01 · alertas de consumo
def test_critical_zone_twice_same_day_is_one_decision() -> None:
    hours = [zh(COCINA, at(DAY, 9), "critico"), zh(COCINA, at(DAY, 15), "critico")]
    decisions = R.evaluate_alert_rules(hours, ZONES, set(), texts())
    assert len(decisions) == 1
    assert decisions[0].alert.clave_evento == f"consumo_critico:{COCINA}:2026-11-03"


def test_critical_and_elevated_same_day_are_two_rules() -> None:
    hours = [zh(COCINA, at(DAY, 9), "elevado"), zh(COCINA, at(DAY, 10), "critico"),
             zh(COCINA, at(DAY, 11), "elevado")]
    decisions = R.evaluate_alert_rules(hours, ZONES, set(), texts())
    assert [d.alert.regla_origen for d in decisions] == ["consumo_elevado", "consumo_critico"]
    assert [d.alert.clave_evento for d in decisions] == [
        f"consumo_elevado:{COCINA}:2026-11-03", f"consumo_critico:{COCINA}:2026-11-03"]


def test_other_day_is_another_decision() -> None:
    hours = [zh(COCINA, at(DAY, 9), "critico"), zh(COCINA, at(DAY + timedelta(days=1), 0),
                                                    "critico")]
    keys = [d.alert.clave_evento for d in R.evaluate_alert_rules(hours, ZONES, set(), texts())]
    assert keys == [f"consumo_critico:{COCINA}:2026-11-03", f"consumo_critico:{COCINA}:2026-11-04"]


def test_other_zone_same_day_is_another_decision() -> None:
    hours = [zh(COCINA, at(DAY, 9), "critico"), zh(SALA, at(DAY, 9), "critico")]
    assert len(R.evaluate_alert_rules(hours, ZONES, set(), texts())) == 2


def test_existing_key_is_not_repeated() -> None:
    existing = {f"consumo_critico:{COCINA}:2026-11-03"}
    hours = [zh(COCINA, at(DAY, 20), "critico"), zh(COCINA, at(DAY, 21), "elevado")]
    decisions = R.evaluate_alert_rules(hours, ZONES, existing, texts())
    assert [d.alert.regla_origen for d in decisions] == ["consumo_elevado"]


@pytest.mark.parametrize("state", ["normal", "sin_referencia", "sin_datos"])
def test_other_states_create_nothing(state: str) -> None:
    assert R.evaluate_alert_rules([zh(COCINA, at(DAY, 9), state)], ZONES, set(), texts()) == []


def test_zone_outside_counting_zones_is_ignored() -> None:
    assert R.evaluate_alert_rules([zh(OTRA, at(DAY, 9), "critico")], ZONES, set(), texts()) == []


def test_alert_fields_and_texts() -> None:
    decision = R.evaluate_alert_rules([zh(COCINA, at(DAY, 19), "critico", 1234.5)], ZONES, set(),
                                      texts())[0]
    alert = decision.alert
    assert alert == R.PlannedAlert(
        regla_origen="consumo_critico",
        categoria="consumo",
        severidad="critica",
        titulo="Consumo crítico en Cocina",
        mensaje=("Entre las 19:00 y las 20:00, Cocina tuvo un promedio de 1.234,50 kW, muy por "
                 "encima de lo habitual para esa hora."),
        zona_id=COCINA,
        clave_evento=f"consumo_critico:{COCINA}:2026-11-03",
        created_at=at(DAY, 20),
    )
    assert decision.tip_trigger == R.TipTrigger("zona_critica", COCINA, "cocina", at(DAY, 20),
                                                None)


def test_elevated_alert_fields() -> None:
    decision = R.evaluate_alert_rules([zh(SALA, at(DAY, 7), "elevado", 0.256)], ZONES, set(),
                                      texts())[0]
    assert (decision.alert.categoria, decision.alert.severidad) == ("consumo", "advertencia")
    assert decision.alert.titulo == "Consumo elevado en Sala"
    assert "Entre las 07:00 y las 08:00, Sala tuvo un promedio de 0,26 kW" in decision.alert.mensaje
    assert decision.tip_trigger.regla_origen == "zona_elevada"


def test_hour_23_ends_at_midnight_and_keeps_its_day() -> None:
    decision = R.evaluate_alert_rules([zh(COCINA, at(DAY, 23), "elevado")], ZONES, set(),
                                      texts())[0]
    assert decision.alert.mensaje.startswith("Entre las 23:00 y las 00:00,")
    assert decision.alert.clave_evento.endswith(":2026-11-03")
    assert decision.alert.created_at == at(DAY + timedelta(days=1), 0)


def test_day_of_the_key_is_bogota_day() -> None:
    # 03:00 UTC del 4 de nov. = 22:00 Bogotá del 3.
    decision = R.evaluate_alert_rules([zh(COCINA, at(DAY, 22, UTC), "critico")], ZONES, set(),
                                      texts())[0]
    assert decision.alert.clave_evento.endswith(":2026-11-03")
    assert decision.alert.mensaje.startswith("Entre las 22:00 y las 23:00,")
    assert decision.alert.created_at.tzinfo == TIMEZONE


def test_chronological_order_keeps_first_hour_of_the_day() -> None:
    hours = [zh(COCINA, at(DAY, 15), "critico", 2.0), zh(SALA, at(DAY, 8), "elevado"),
             zh(COCINA, at(DAY, 9), "critico", 1.0)]
    decisions = R.evaluate_alert_rules(hours, ZONES, set(), texts())
    assert [d.alert.created_at for d in decisions] == [at(DAY, 9), at(DAY, 10)]
    assert "1,00 kW" in decisions[1].alert.mensaje


def zone_hour_states(personality: PersonalityAverages, factor: float):
    """30 días con la curva real y hoy, a la hora de mayor referencia, la zona × factor."""
    zone, hour = max(
        ((z, h) for z in personality.zone_kwh_per_day for h in range(24)),
        key=lambda item: personality.zone_kwh_for_hour(*item),
    )
    ids = {z: stable_id("zona", "alertas", personality.name, z) for z in personality.zone_kwh_per_day}
    readings = {}
    for z, zona_id in ids.items():
        series = {}
        for offset in range(-30, 1):
            for h in range(24):
                value = personality.zone_kwh_for_hour(z, h)
                if offset == 0 and (z, h) == (zone, hour):
                    value *= factor
                series[at(DAY + timedelta(days=offset), h)] = value
        readings[zona_id] = series
    hours = {zona_id: [at(DAY, hour)] for zona_id in ids.values()}
    zones = {zona_id: R.ZoneInfo(zona_id, z) for z, zona_id in ids.items()}
    reference = personality.zone_kwh_for_hour(zone, hour)
    return S.evaluate_zone_hours(readings, hours, thresholds()), zones, ids[zone], reference


@each_personality
@pytest.mark.parametrize(("factor", "rule"), [(1.3, "consumo_elevado"), (1.6, "consumo_critico")])
def test_personality_zone_alert(personality: PersonalityAverages, factor: float, rule: str) -> None:
    """Curva real como referencia: +30 % -> elevado, +60 % -> crítico, salvo el piso de 0,05."""
    zone_hours, zones, zona_id, reference = zone_hour_states(personality, factor)
    decisions = R.evaluate_alert_rules(zone_hours, zones, set(), texts())
    if reference * (factor - 1) < thresholds().zone_state.min_excess_kwh:
        assert decisions == []  # Consumo compacto: el exceso no llega a 0,05 kWh
        return
    assert [(d.alert.regla_origen, d.alert.zona_id) for d in decisions] == [(rule, zona_id)]
    assert F.format_kw(reference * factor) in decisions[0].alert.mensaje


@each_personality
def test_personality_usual_day_creates_no_alert(personality: PersonalityAverages) -> None:
    zone_hours, zones, _, _ = zone_hour_states(personality, 1.0)
    assert R.evaluate_alert_rules(zone_hours, zones, set(), texts()) == []
    assert R.zone_alert_keys(zone_hours, zones) == []


# ------------------------------------------------------------------ claves candidatas (DC-25)
def decided_keys(hours) -> list[str]:
    return [d.alert.clave_evento for d in R.evaluate_alert_rules(hours, ZONES, set(), texts())]


ZONE_KEY_CASES = {
    "repetida_mismo_dia": [zh(COCINA, at(DAY, 9), "critico"), zh(COCINA, at(DAY, 15), "critico")],
    "elevado_y_critico": [zh(COCINA, at(DAY, 9), "elevado"), zh(COCINA, at(DAY, 10), "critico"),
                          zh(COCINA, at(DAY, 11), "elevado")],
    "desordenadas": [zh(COCINA, at(DAY, 15), "critico", 2.0), zh(SALA, at(DAY, 8), "elevado"),
                     zh(COCINA, at(DAY, 9), "critico", 1.0),
                     zh(SALA, at(DAY + timedelta(days=1), 0), "elevado")],
    "misma_hora_dos_zonas": [zh(SALA, at(DAY, 9), "critico"), zh(COCINA, at(DAY, 9), "critico")],
    "dia_bogota": [zh(COCINA, at(DAY, 22, UTC), "critico"), zh(COCINA, at(DAY, 23), "critico")],
    "ignoradas": [zh(OTRA, at(DAY, 9), "critico"), zh(COCINA, at(DAY, 9), "normal"),
                  zh(COCINA, at(DAY, 10), "sin_referencia"), zh(SALA, at(DAY, 9), "sin_datos"),
                  zh(SALA, at(DAY, 10), "critico", None), zh(SALA, at(DAY, 11), "elevado")],
    "vacio": [],
}


@pytest.mark.parametrize("hours", ZONE_KEY_CASES.values(), ids=ZONE_KEY_CASES.keys())
def test_zone_alert_keys_match_decisions(hours) -> None:
    keys = R.zone_alert_keys(hours, ZONES)
    assert keys == decided_keys(hours)
    assert len(keys) == len(set(keys))


def test_zone_alert_keys_values_and_order() -> None:
    keys = R.zone_alert_keys(ZONE_KEY_CASES["desordenadas"], ZONES)
    assert keys == [f"consumo_elevado:{SALA}:2026-11-03", f"consumo_critico:{COCINA}:2026-11-03",
                    f"consumo_elevado:{SALA}:2026-11-04"]


def test_zone_alert_keys_does_not_render_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("zone_alert_keys no debe renderizar textos")

    monkeypatch.setattr(R, "render_backend_text", fail)
    monkeypatch.setattr(R, "format_kw", fail)
    assert R.zone_alert_keys([zh(COCINA, at(DAY, 9), "critico")], ZONES) == [
        f"consumo_critico:{COCINA}:2026-11-03"]


@each_personality
@pytest.mark.parametrize("factor", [1.3, 1.6])
def test_personality_zone_alert_keys(personality: PersonalityAverages, factor: float) -> None:
    zone_hours, zones, _, _ = zone_hour_states(personality, factor)
    decisions = R.evaluate_alert_rules(zone_hours, zones, set(), texts())
    assert R.zone_alert_keys(zone_hours, zones) == [d.alert.clave_evento for d in decisions]


# ------------------------------------------------------------------ cierre de mes (DC-32)
def test_month_close_keys() -> None:
    assert R.month_close_keys(HOGAR, date(2026, 10, 1)) == (
        f"cierre_mes_dentro:{HOGAR}:2026-10", f"cierre_mes_encima:{HOGAR}:2026-10")


def test_month_close_keys_rejects_other_day() -> None:
    with pytest.raises(ValueError):
        R.month_close_keys(HOGAR, date(2026, 10, 2))


def test_months_to_close_last_hour_of_month() -> None:
    created = datetime(2026, 9, 15, 8, tzinfo=TIMEZONE)
    hours = [at(date(2026, 10, 31), 22), at(date(2026, 10, 31), 23, UTC),
             at(date(2026, 11, 1), 0)]
    assert R.months_to_close(hours, created) == [date(2026, 10, 1)]


def test_months_to_close_needs_hour_23_of_last_day() -> None:
    created = datetime(2026, 1, 1, tzinfo=TIMEZONE)
    hours = [at(date(2026, 10, 31), 22), at(date(2026, 10, 30), 23), at(date(2026, 11, 1), 0)]
    assert R.months_to_close(hours, created) == []


def test_months_to_close_several_months_ascending() -> None:
    created = datetime(2026, 1, 1, tzinfo=TIMEZONE)
    hours = [at(date(2026, 12, 31), 23), at(date(2026, 2, 28), 23), at(date(2026, 11, 30), 23),
             at(date(2026, 11, 30), 23, UTC)]
    assert R.months_to_close(hours, created) == [date(2026, 2, 1), date(2026, 11, 1),
                                                 date(2026, 12, 1)]


@pytest.mark.parametrize(
    ("created", "expected"),
    [
        (datetime(2026, 10, 31, 23, 30, tzinfo=TIMEZONE), [date(2026, 10, 1)]),
        (datetime(2026, 11, 1, 0, 0, tzinfo=TIMEZONE), []),  # el mes termina justo al crear
        (datetime(2026, 11, 1, 4, 59, tzinfo=UTC), [date(2026, 10, 1)]),  # 23:59 Bogotá
        (datetime(2026, 11, 5, tzinfo=TIMEZONE), []),
    ],
)
def test_months_ending_before_the_household_are_skipped(created, expected) -> None:
    assert R.months_to_close([at(date(2026, 10, 31), 23)], created) == expected


def test_months_to_close_rejects_naive() -> None:
    with pytest.raises(ValueError):
        naive = datetime(2026, 1, 1, tzinfo=TIMEZONE).replace(tzinfo=None)
        R.months_to_close([at(date(2026, 10, 31), 23)], naive)


def two_zone_days(first: date, days: int, a: float = 0.2, b: float = 0.3, skip=frozenset()):
    readings = {COCINA: {}, SALA: {}}
    for offset in range(days):
        day = first + timedelta(days=offset)
        for hour in range(24):
            readings[COCINA][at(day, hour)] = a
            if (day, hour) not in skip:
                readings[SALA][at(day, hour)] = b
    return readings


def test_daily_complete_totals_only_full_days() -> None:
    first = date(2026, 10, 1)
    readings = two_zone_days(first, 3, skip=frozenset({(date(2026, 10, 2), 13)}))
    totals = R.daily_complete_totals(readings)
    assert set(totals) == {date(2026, 10, 1), date(2026, 10, 3)}
    assert totals[date(2026, 10, 1)] == pytest.approx(24 * 0.5)


def test_daily_complete_totals_uses_bogota_days() -> None:
    first = date(2026, 10, 1)
    readings = two_zone_days(first, 2)
    in_utc = {z: {m.astimezone(UTC): v for m, v in s.items()} for z, s in readings.items()}
    assert R.daily_complete_totals(in_utc) == R.daily_complete_totals(readings)
    assert set(R.daily_complete_totals(in_utc)) == {first, first + timedelta(days=1)}


def test_daily_complete_totals_empty() -> None:
    assert R.daily_complete_totals({}) == {}


def test_month_total_only_hours_with_every_zone_inside_the_month() -> None:
    readings = two_zone_days(date(2026, 9, 30), 33, skip=frozenset({(date(2026, 10, 5), 3)}))
    total = R.month_total_kwh(readings, date(2026, 10, 1))
    assert total == pytest.approx(31 * 24 * 0.5 - 0.5)


def test_month_total_without_readings_is_zero() -> None:
    assert R.month_total_kwh({}, date(2026, 10, 1)) == 0.0
    assert R.month_total_kwh(two_zone_days(date(2026, 9, 1), 5), date(2026, 10, 1)) == 0.0


def test_month_close_reference_goal_wins() -> None:
    assert R.month_close_reference({date(2026, 9, 1): 10.0}, date(2026, 10, 1), 250.0) == (
        250.0, "meta")


def test_month_close_reference_average_of_last_90_complete_days() -> None:
    month = date(2026, 10, 1)
    daily = {month - timedelta(days=d): (20.0 if d > 90 else 10.0) for d in range(1, 101)}
    daily[month] = 99.0  # días del propio mes no cuentan
    daily[date(2026, 10, 20)] = 99.0
    reference, kind = R.month_close_reference(daily, month, None)
    assert (reference, kind) == (pytest.approx(10.0 * 31), "promedio")


def test_month_close_reference_with_few_days_and_february() -> None:
    month = date(2026, 2, 1)
    daily = {date(2026, 1, 10): 8.0, date(2026, 1, 20): 12.0}
    assert R.month_close_reference(daily, month, None) == (pytest.approx(10.0 * 28), "promedio")


def test_month_close_reference_max_days_parameter() -> None:
    month = date(2026, 10, 1)
    daily = {date(2026, 9, 29): 30.0, date(2026, 9, 30): 10.0}
    assert R.month_close_reference(daily, month, None, max_days=1)[0] == pytest.approx(10.0 * 31)


def test_month_close_reference_without_days() -> None:
    assert R.month_close_reference({date(2026, 10, 3): 5.0}, date(2026, 10, 1), None) == (
        None, "promedio")


def test_month_close_above_goal() -> None:
    month = date(2026, 10, 1)
    decision = R.evaluate_month_close(HOGAR, month, 1234.5, 1000.0, "meta", set(), texts())
    assert decision.alert == R.PlannedAlert(
        regla_origen="cierre_mes_encima",
        categoria="informacion",
        severidad="advertencia",
        titulo="Cierre de octubre: por encima de tu referencia",
        mensaje=("Cerraste octubre con 1.234,5 kWh, por encima de tu meta de 1.000,0 kWh. Revisa "
                 "los consejos."),
        zona_id=None,
        clave_evento=f"cierre_mes_encima:{HOGAR}:2026-10",
        created_at=datetime(2026, 11, 1, tzinfo=TIMEZONE),
    )
    assert decision.tip_trigger == R.TipTrigger(
        "cierre_mes_encima", None, None, datetime(2026, 11, 1, tzinfo=TIMEZONE), month)


def test_month_close_equal_is_inside_average() -> None:
    month = date(2026, 12, 1)
    decision = R.evaluate_month_close(HOGAR, month, 310.0, 310.0, "promedio", set(), texts())
    assert decision.alert.regla_origen == "cierre_mes_dentro"
    assert (decision.alert.categoria, decision.alert.severidad) == ("informacion", "informativa")
    assert decision.alert.titulo == "Cierre de diciembre: dentro de tu referencia"
    assert decision.alert.mensaje == (
        "Cerraste diciembre con 310,0 kWh, dentro de tu promedio de 310,0 kWh.")
    assert decision.alert.clave_evento == f"cierre_mes_dentro:{HOGAR}:2026-12"
    assert decision.alert.created_at == datetime(2027, 1, 1, tzinfo=TIMEZONE)
    assert decision.tip_trigger is None


def test_month_close_float_noise_is_not_above() -> None:
    decision = R.evaluate_month_close(HOGAR, date(2026, 10, 1), 300.0000000001, 300.0, "meta",
                                      set(), texts())
    assert decision.alert.regla_origen == "cierre_mes_dentro"


def test_month_close_without_reference_creates_nothing() -> None:
    assert R.evaluate_month_close(HOGAR, date(2026, 10, 1), 300.0, None, "promedio", set(),
                                  texts()) is None


@pytest.mark.parametrize("existing", [0, 1])
def test_month_close_once_per_month(existing: int) -> None:
    month = date(2026, 10, 1)
    keys = {R.month_close_keys(HOGAR, month)[existing]}
    for total in (100.0, 500.0):  # ni dentro ni encima si ya hay cualquiera de las dos
        assert R.evaluate_month_close(HOGAR, month, total, 300.0, "meta", keys, texts()) is None


def average_month(personality: PersonalityAverages, month: date) -> dict[UUID, dict]:
    """Un mes con las curvas promedio de la personalidad (sin humor, ruido ni fin de semana)."""
    readings = {}
    for zone in personality.zone_kwh_per_day:
        series = {}
        for offset in range(S.days_in_month(month)):
            day = month + timedelta(days=offset)
            for hour in range(24):
                series[at(day, hour)] = personality.zone_kwh_for_hour(zone, hour)
        readings[stable_id("zona", "cierre", personality.name, zone)] = series
    return readings


def test_month_total_follows_personality_order() -> None:
    """compacto < eficiente < intermedio < familiar < amplio en el total de noviembre."""
    month = date(2026, 11, 1)
    totals = [R.month_total_kwh(average_month(load_personalities()[name], month), month)
              for name in PERSONALITY_ORDER]
    assert totals == sorted(totals) and len(set(totals)) == len(totals)
    for name, total in zip(PERSONALITY_ORDER, totals, strict=True):
        assert total == pytest.approx(load_personalities()[name].kwh_per_month)


@each_personality
def test_personality_month_close(personality: PersonalityAverages) -> None:
    """Octubre con la curva promedio; referencia = promedio de septiembre (mismo consumo diario)."""
    september, october = date(2026, 9, 1), date(2026, 10, 1)
    previous = average_month(personality, september)
    daily = R.daily_complete_totals(previous)
    assert len(daily) == 30
    reference, kind = R.month_close_reference(daily, october, None)
    assert reference == pytest.approx(personality.kwh_per_day * 31)
    total = R.month_total_kwh(average_month(personality, october), october)
    assert total == pytest.approx(reference)
    inside = R.evaluate_month_close(HOGAR, october, total, reference, kind, set(), texts())
    assert inside.alert.regla_origen == "cierre_mes_dentro"
    above = R.evaluate_month_close(HOGAR, october, total * 1.1, reference, kind, set(), texts())
    assert above.alert.regla_origen == "cierre_mes_encima"
    assert f"tu promedio de {F.format_kwh(reference)} kWh" in above.alert.mensaje


# ------------------------------------------------------------------ consejos (RN-XV-05, DC-24)
def trigger(moment: datetime, regla: str = "zona_critica", zona_id: UUID | None = COCINA,
            zona_tipo: str | None = "cocina", month: date | None = None) -> R.TipTrigger:
    return R.TipTrigger(regla, zona_id, zona_tipo, moment, month)


def existing(created_at: datetime, variante: int, regla: str = "zona_critica",
             zona_id: UUID | None = COCINA, zona: str | None = "cocina") -> R.ExistingTip:
    return R.ExistingTip(regla, zona_id, catalog_tip(regla, zona, variante).titulo, created_at)


def test_first_zone_tip_uses_variant_1() -> None:
    moment = at(DAY, 20)
    [tip] = R.build_tips([trigger(moment)], [], texts())
    template = catalog_tip("zona_critica", "cocina", 1)
    assert tip == R.PlannedTip(
        regla_origen="zona_critica",
        categoria="zona",
        prioridad="alta",
        zona_id=COCINA,
        titulo=template.titulo,
        descripcion=template.descripcion,
        variante=1,
        created_at=moment,
        notice=R.PlannedAlert(
            regla_origen="nuevo_consejo_zona",
            categoria="consejo",
            severidad="informativa",
            titulo="Nuevo consejo disponible",
            mensaje="Tienes un consejo nuevo para Cocina. Revísalo en Consejos.",
            zona_id=COCINA,
            clave_evento="",
            created_at=moment,
        ),
    )


def test_elevated_zone_tip_is_medium_priority() -> None:
    [tip] = R.build_tips([trigger(at(DAY, 9), "zona_elevada", SALA, "sala")], [], texts())
    assert (tip.prioridad, tip.categoria, tip.titulo) == (
        "media", "zona", catalog_tip("zona_elevada", "sala", 1).titulo)


def test_valid_tip_blocks_a_new_one() -> None:
    moment = at(DAY, 20)
    previous = existing(moment - timedelta(days=7) + timedelta(seconds=1), 1)
    assert R.build_tips([trigger(moment)], [previous], texts()) == []


@pytest.mark.parametrize(("previous_variant", "expected"), [(1, 2), (2, 1)])
def test_after_seven_days_the_other_variant(previous_variant: int, expected: int) -> None:
    moment = at(DAY, 20)
    previous = existing(moment - timedelta(days=7), previous_variant)
    [tip] = R.build_tips([trigger(moment)], [previous], texts())
    assert tip.variante == expected
    assert tip.titulo == catalog_tip("zona_critica", "cocina", expected).titulo


def test_unknown_previous_title_uses_variant_1() -> None:
    moment = at(DAY, 20)
    previous = R.ExistingTip("zona_critica", COCINA, "Título viejo", moment - timedelta(days=9))
    assert R.build_tips([trigger(moment)], [previous], texts())[0].variante == 1


def test_previous_title_of_another_zone_type_is_not_recognized() -> None:
    """El título se busca en el catálogo de la regla y del tipo de zona del consejo."""
    moment = at(DAY, 20)
    previous = R.ExistingTip("zona_critica", COCINA,
                             catalog_tip("zona_critica", "sala", 1).titulo,
                             moment - timedelta(days=9))
    assert R.build_tips([trigger(moment)], [previous], texts())[0].variante == 1


def test_latest_existing_tip_decides() -> None:
    moment = at(DAY, 20)
    tips = [existing(moment - timedelta(days=8), 1), existing(moment - timedelta(days=20), 2)]
    assert R.build_tips([trigger(moment)], tips, texts())[0].variante == 2
    recent = [existing(moment - timedelta(days=20), 2), existing(moment - timedelta(days=2), 1)]
    assert R.build_tips([trigger(moment)], recent, texts()) == []


def test_tips_planned_in_the_same_call_count() -> None:
    first = at(DAY, 9)
    triggers = [trigger(first + timedelta(days=8)), trigger(first + timedelta(days=3)),
                trigger(first), trigger(first + timedelta(days=16))]
    tips = R.build_tips(triggers, [], texts())
    assert [(t.created_at, t.variante) for t in tips] == [
        (first, 1), (first + timedelta(days=8), 2), (first + timedelta(days=16), 1)]


def test_other_rule_or_zone_is_independent() -> None:
    moment = at(DAY, 9)
    triggers = [trigger(moment), trigger(moment, "zona_elevada"),
                trigger(moment, zona_id=SALA, zona_tipo="sala")]
    previous = [existing(moment - timedelta(days=1), 1, zona_id=SALA, zona="sala")]
    tips = R.build_tips(triggers, previous, texts())
    assert [(t.regla_origen, t.zona_id) for t in tips] == [
        ("zona_critica", COCINA), ("zona_elevada", COCINA)]


def test_month_close_tip_is_general() -> None:
    moment = datetime(2026, 11, 1, tzinfo=TIMEZONE)
    month = date(2026, 10, 1)
    previous = R.ExistingTip("cierre_mes_encima", None,
                             catalog_tip("cierre_mes_encima", None, 1).titulo,
                             datetime(2026, 10, 1, tzinfo=TIMEZONE))
    [tip] = R.build_tips([trigger(moment, "cierre_mes_encima", None, None, month)], [previous],
                         texts())
    assert (tip.categoria, tip.prioridad, tip.zona_id, tip.variante) == ("general", "baja", None, 2)
    assert tip.descripcion == ("En Historial, mira qué zonas pesaron más en octubre y empieza por "
                               "la de mayor participación.")
    assert tip.notice.regla_origen == "nuevo_consejo_general"
    assert tip.notice.mensaje == ("Tienes un consejo nuevo para revisar tus hábitos del mes. "
                                  "Revísalo en Consejos.")
    assert (tip.notice.zona_id, tip.notice.clave_evento, tip.notice.created_at) == (None, "",
                                                                                    moment)


def test_month_close_tip_variant_1_fills_month() -> None:
    moment = datetime(2027, 1, 1, tzinfo=TIMEZONE)
    trig = trigger(moment, "cierre_mes_encima", None, None, date(2026, 12, 1))
    [tip] = R.build_tips([trig], [], texts())
    assert tip.descripcion.startswith("Cerraste diciembre por encima de tu referencia.")


@pytest.mark.parametrize(
    "bad",
    [
        R.TipTrigger("zona_critica", COCINA, None, at(DAY, 9), None),
        R.TipTrigger("zona_critica", None, "cocina", at(DAY, 9), None),
        R.TipTrigger("cierre_mes_encima", None, None, at(DAY, 9), None),
    ],
)
def test_incomplete_trigger_is_rejected(bad: R.TipTrigger) -> None:
    with pytest.raises(ValueError):
        R.build_tips([bad], [], texts())


def test_alerts_then_tips_over_several_days() -> None:
    """Crítico en la cocina 3 días seguidos: 3 alertas y 1 solo consejo (vigencia 7 días)."""
    hours = [zh(COCINA, at(DAY + timedelta(days=d), 19), "critico") for d in range(3)]
    decisions = R.evaluate_alert_rules(hours, ZONES, set(), texts())
    assert len(decisions) == 3
    tips = R.build_tips([d.tip_trigger for d in decisions], [], texts())
    assert [t.created_at for t in tips] == [at(DAY, 20)]


def test_tip_validity_constant() -> None:
    assert R.TIP_VALIDITY_DAYS == 7


# ------------------------------------------------------------------ entrega (RN-VI-02, RN-XIV-06)
ADMIN = R.AlertMember(UUID(int=11), "administrador", notif_consumo=True, notif_consejos=False)
MEMBER = R.AlertMember(UUID(int=12), "miembro", notif_consumo=True, notif_consejos=True)
QUIET = R.AlertMember(UUID(int=13), "miembro", notif_consumo=False, notif_consejos=False)
ADMIN_QUIET = R.AlertMember(UUID(int=14), "administrador", notif_consumo=False,
                            notif_consejos=True)
MEMBERS = [MEMBER, ADMIN, QUIET, ADMIN_QUIET]


@pytest.mark.parametrize(
    ("categoria", "permission", "expected"),
    [
        ("consumo", True, [MEMBER, ADMIN]),
        ("informacion", True, [MEMBER, ADMIN]),
        ("consejo", True, [MEMBER, ADMIN_QUIET]),
        ("consumo", False, [ADMIN]),
        ("informacion", False, [ADMIN]),
        ("consejo", False, [ADMIN_QUIET]),
    ],
)
def test_alert_recipients(categoria: str, permission: bool, expected) -> None:
    assert R.alert_recipients(categoria, MEMBERS, permission) == [m.usuario_id for m in expected]


def test_alert_recipients_empty() -> None:
    assert R.alert_recipients("consumo", [], True) == []
