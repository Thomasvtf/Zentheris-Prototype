"""Pruebas de app.services.live_alerts con `app.data.*` falso en memoria (sin base ni red).

Evaluación en vivo de las alertas y los consejos (DC-35, DC-24, DC-25, RN-XIV-06 a RN-XIV-08,
RN-XV-05 a RN-XV-07) con las referencias exactas de las 5 personalidades
(`tests/helpers/personalities.py`), la evaluación real dentro de la recuperación (SAVEPOINT) y
la entrega solo a los miembros que ya estaban en el hogar cuando ocurrió el evento (RN-VI-02,
RN-XV-06). Los dobles están en `alerts_fakes.py` (recuperación real sobre el almacén en memoria).
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.exc import OperationalError

from app.data import alerts as alerts_data
from app.data import tips as tips_data
from app.domain.formats import format_kw
from app.services import hour_recovery, live_alerts
from app.services.backend_texts import get_backend_texts
from app.services.live_alerts import LiveEvaluationSummary
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities
from tests.services.alerts_fakes import (
    ADMIN,
    BACKFILL_AT,
    FakeAlertsDatabase,
    Member,
    critical_value,
    install_fake_alerts_database,
    install_spikes,
    zone_id,
)
from tests.services.recovery_fakes import FakeHousehold
from tests.simulator.support import bogota, stable_id

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)
SECRET = "DETAIL: Key (hogar_id)=(secreto) already exists"
EDGE = stable_id("usuario", "justo-a-tiempo")
LATE = stable_id("usuario", "tarde")


class PgError(Exception):
    pgcode = "40001"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeAlertsDatabase:
    return install_fake_alerts_database(monkeypatch)


def peak_of(personality: PersonalityAverages) -> tuple[str, int]:
    """(zona, hora) con la mayor referencia de la personalidad."""
    return max(
        ((zone, hour) for zone in personality.zone_kwh_per_day for hour in range(24)),
        key=lambda item: personality.zone_kwh_for_hour(*item),
    )


def seed_averages(
    db: FakeAlertsDatabase, household: FakeHousehold, live: datetime,
    values: dict[str, float] | None = None,
) -> None:
    """30 días con la referencia exacta de cada zona (sin ruido) y la hora en vivo `live`.

    En la hora en vivo cada zona vale su referencia salvo las de `values`.
    """
    personality = load_personalities()[household.name]
    rows = []
    moment = live - timedelta(days=30)
    while moment <= live:
        for zone, sensor in household.sensors.items():
            value = personality.zone_kwh_for_hour(zone, moment.hour)
            if moment == live and values and zone in values:
                value = values[zone]
            rows.append({"sensor_id": sensor, "fecha_hora": moment,
                         "consumo_kwh": Decimal(str(round(value, 4))), "calidad": "simulada"})
        moment += timedelta(hours=1)
    db.store(rows)


def evaluate(db: FakeAlertsDatabase, household: FakeHousehold, live: datetime,
             zones: list[str] | None = None) -> LiveEvaluationSummary:
    session = db.session()
    hours = {zone: [live] for zone in (zones or household.sensors)}
    summary = live_alerts.evaluate_live_hours(session, household.id, hours)
    session.commit()
    return summary


def kw(value: float) -> str:
    return format_kw(float(Decimal(str(round(value, 4)))))


@each_personality
def test_live_critical_zone_by_personality(db: FakeAlertsDatabase, name: str) -> None:
    """La zona de más consumo al doble de su referencia → 1 alerta crítica + consejo + aviso."""
    personality = load_personalities()[name]
    zone, hour = peak_of(personality)
    live = bogota(2026, 11, 23, hour)
    household = db.register(FakeHousehold(name, tag="vivo"), BACKFILL_AT)
    value = 2 * personality.zone_kwh_for_hour(zone, hour)
    seed_averages(db, household, live, {zone: value})

    summary = evaluate(db, household, live)

    assert summary == LiveEvaluationSummary(alerts=2, tips=1)
    zona = zone_id(household, zone)
    alert = next(a for a in db.alerts() if a["regla_origen"] == "consumo_critico")
    assert alert["clave_evento"] == f"consumo_critico:{zona}:2026-11-23"
    assert alert["zona_id"] == zona and alert["created_at"] == live + timedelta(hours=1)
    zone_label = {"cocina": "Cocina", "lavanderia": "Lavandería"}[zone]
    assert alert["titulo"] == f"Consumo crítico en {zone_label}"
    assert alert["mensaje"] == (
        f"Entre las {hour:02d}:00 y las {hour + 1:02d}:00, {zone_label} tuvo un promedio de "
        f"{kw(value)} kW, muy por encima de lo habitual para esa hora."
    )
    (tip,) = db.tips()
    assert (tip["regla_origen"], tip["categoria"], tip["prioridad"]) == ("zona_critica", "zona",
                                                                        "alta")
    template = next(t for t in get_backend_texts().tips
                    if (t.regla_origen, t.zona, t.variante) == ("zona_critica", zone, 1))
    assert tip["titulo"] == template.titulo and tip["descripcion"] == template.descripcion
    notice = next(a for a in db.alerts() if a["clave_evento"] == f"nuevo_consejo:{tip['id']}")
    assert notice["regla_origen"] == "nuevo_consejo_zona" and notice["zona_id"] == zona
    assert notice["mensaje"] == f"Tienes un consejo nuevo para {zone_label}. Revísalo en Consejos."


@each_personality
def test_live_peak_of_45_percent(db: FakeAlertsDatabase, name: str) -> None:
    """+45 % → elevado (30 % ≤ var < 60 %) solo si el exceso llega a 0,05 kWh (zona_estado).

    CONTRADICCIÓN anotada: el encargo habla de «pico del +45 % → 1 alerta»; con los umbrales
    v1 un +45 % es `elevado` (no crítico) y en «Consumo compacto» ni su zona de más consumo
    (0,088 kWh) alcanza el exceso mínimo, así que allí no hay alerta.
    """
    personality = load_personalities()[name]
    zone, hour = peak_of(personality)
    live = bogota(2026, 11, 23, hour)
    household = db.register(FakeHousehold(name, tag="vivo45"), BACKFILL_AT)
    reference = round(personality.zone_kwh_for_hour(zone, hour), 4)
    value = round(reference * 1.45, 4)
    seed_averages(db, household, live, {zone: value})

    summary = evaluate(db, household, live)

    if value - reference >= 0.05:
        assert summary == LiveEvaluationSummary(alerts=2, tips=1)
        (alert,) = [a for a in db.alerts() if a["categoria"] == "consumo"]
        assert alert["regla_origen"] == "consumo_elevado" and alert["severidad"] == "advertencia"
        (tip,) = db.tips()
        assert (tip["regla_origen"], tip["prioridad"]) == ("zona_elevada", "media")
    else:
        assert name == "Consumo compacto"
        assert summary == LiveEvaluationSummary(alerts=0, tips=0)
        assert db.alerts() == [] and db.tips() == []


@each_personality
def test_usual_hours_create_nothing(db: FakeAlertsDatabase, name: str) -> None:
    """Cada zona en su referencia exacta, a todas las horas del día → ninguna alerta."""
    household = db.register(FakeHousehold(name, tag="habitual"), BACKFILL_AT)
    last = bogota(2026, 11, 23, 23)
    seed_averages(db, household, last)
    session = db.session()
    hours = {zone: [bogota(2026, 11, 23, h) for h in range(24)] for zone in household.sensors}
    assert live_alerts.evaluate_live_hours(session, household.id, hours) == (
        LiveEvaluationSummary(alerts=0, tips=0)
    )
    assert db.alerts() == []


def test_zero_average_hour_is_a_valid_reference(db: FakeAlertsDatabase) -> None:
    """Decisión de Nicolás del 23/11/2026: con 7 o más días con dato, un promedio 0 es referencia
    válida (crítico si el exceso llega a 0,05 kWh; si no, normal)."""
    household = db.register(FakeHousehold("Consumo familiar", tag="cero"), BACKFILL_AT)
    live = bogota(2026, 11, 23, 3)
    rows = []
    for back in range(1, 31):
        for zone, sensor in household.sensors.items():
            rows.append({"sensor_id": sensor, "fecha_hora": live - timedelta(days=back),
                         "consumo_kwh": Decimal(0), "calidad": "simulada"})
    for zone, sensor in household.sensors.items():
        value = {"garaje": "0.06", "terraza": "0.04"}.get(zone, "0")
        rows.append({"sensor_id": sensor, "fecha_hora": live, "consumo_kwh": Decimal(value),
                     "calidad": "simulada"})
    db.store(rows)

    evaluate(db, household, live)

    consumption = [a for a in db.alerts() if a["categoria"] == "consumo"]
    assert [(a["regla_origen"], a["zona_id"]) for a in consumption] == [
        ("consumo_critico", zone_id(household, "garaje"))
    ]


def test_zones_that_do_not_count_are_ignored(db: FakeAlertsDatabase) -> None:
    personality = load_personalities()["Consumo amplio"]
    live = bogota(2026, 11, 23, 19)
    household = db.register(FakeHousehold("Consumo amplio", tag="inactiva"), BACKFILL_AT)
    seed_averages(db, household, live, {"cocina": 3 * personality.zone_kwh_for_hour("cocina", 19)})
    db.zones[household.id] = [
        zone if zone.tipo != "cocina" else zone.__class__(zone.id, zone.tipo, zone.nombre,
                                                          "activa", "pausado")
        for zone in db.zones[household.id]
    ]
    assert evaluate(db, household, live) == LiveEvaluationSummary(alerts=0, tips=0)


def test_an_existing_key_is_not_repeated(db: FakeAlertsDatabase) -> None:
    personality = load_personalities()["Consumo familiar"]
    live = bogota(2026, 11, 23, 12)
    household = db.register(FakeHousehold("Consumo familiar", tag="clave"), BACKFILL_AT)
    seed_averages(db, household, live, {"cocina": 3 * personality.zone_kwh_for_hour("cocina", 12)})
    zona = zone_id(household, "cocina")
    db.seed_alert(household.id, clave_evento=f"consumo_critico:{zona}:2026-11-23", zona_id=zona)

    assert evaluate(db, household, live) == LiveEvaluationSummary(alerts=0, tips=0)
    assert len(db.alerts()) == 1 and db.tips() == []


def test_a_valid_tip_blocks_a_new_one_but_not_the_alert(db: FakeAlertsDatabase) -> None:
    """RN-XV-05 (vigencia de 7 días): con un consejo vigente (3 días) de la misma regla y zona,
    solo la alerta."""
    personality = load_personalities()["Consumo familiar"]
    live = bogota(2026, 11, 23, 12)
    household = db.register(FakeHousehold("Consumo familiar", tag="vigente"), BACKFILL_AT)
    seed_averages(db, household, live, {"cocina": 3 * personality.zone_kwh_for_hour("cocina", 12)})
    zona = zone_id(household, "cocina")
    db.seed_tip(household.id, regla_origen="zona_critica", zona_id=zona, categoria="zona",
                prioridad="alta", created_at=live - timedelta(days=3))

    assert evaluate(db, household, live) == LiveEvaluationSummary(alerts=1, tips=0)
    assert len(db.tips()) == 1
    assert not any(a["regla_origen"].startswith("nuevo_consejo") for a in db.alerts())


def test_an_expired_tip_gives_the_other_variant(db: FakeAlertsDatabase) -> None:
    """DC-24 (variante alterna; la anterior se reconoce por su título): vencido el anterior
    (8 días), el nuevo usa la variante que no usó."""
    personality = load_personalities()["Consumo familiar"]
    live = bogota(2026, 11, 23, 12)
    household = db.register(FakeHousehold("Consumo familiar", tag="variante"), BACKFILL_AT)
    seed_averages(db, household, live, {"cocina": 3 * personality.zone_kwh_for_hour("cocina", 12)})
    zona = zone_id(household, "cocina")
    db.seed_tip(household.id, regla_origen="zona_critica", zona_id=zona, categoria="zona",
                prioridad="alta", titulo="Revisa ya los equipos de la cocina",
                created_at=live - timedelta(days=8))

    assert evaluate(db, household, live) == LiveEvaluationSummary(alerts=2, tips=1)
    new = max(db.tips(), key=lambda tip: tip["created_at"])
    assert new["titulo"] == "Desenchufa lo que no uses en la cocina"


def test_an_alert_lost_in_a_race_creates_no_tip(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si `insert_alert` devuelve None (otra transacción guardó la clave), no hay consejo."""
    personality = load_personalities()["Consumo familiar"]
    live = bogota(2026, 11, 23, 12)
    household = db.register(FakeHousehold("Consumo familiar", tag="carrera"), BACKFILL_AT)
    seed_averages(db, household, live, {"cocina": 3 * personality.zone_kwh_for_hour("cocina", 12)})
    monkeypatch.setattr(alerts_data, "insert_alert", lambda *args, **kwargs: None)

    assert evaluate(db, household, live) == LiveEvaluationSummary(alerts=0, tips=0)
    assert db.tips() == []


def test_a_failing_tip_insert_propagates(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    personality = load_personalities()["Consumo familiar"]
    live = bogota(2026, 11, 23, 12)
    household = db.register(FakeHousehold("Consumo familiar", tag="falla"), BACKFILL_AT)
    seed_averages(db, household, live, {"cocina": 3 * personality.zone_kwh_for_hour("cocina", 12)})

    def broken(*_args: object, **_kwargs: object) -> UUID:
        raise ValueError("La zona del consejo no es del hogar.")

    monkeypatch.setattr(tips_data, "insert_tip", broken)
    with pytest.raises(ValueError):
        evaluate(db, household, live)


def test_empty_hours_touch_nothing(db: FakeAlertsDatabase) -> None:
    household = db.register(FakeHousehold("Consumo familiar", tag="vacio"), BACKFILL_AT)
    session = db.session()
    assert live_alerts.evaluate_live_hours(session, household.id, {"cocina": []}) == (
        LiveEvaluationSummary(alerts=0, tips=0)
    )
    assert live_alerts.evaluate_live_hours(session, household.id, {}) == (
        LiveEvaluationSummary(alerts=0, tips=0)
    )
    assert "zones" not in db.calls and "readings" not in db.calls


# ------------------------------------------------------------------ recuperación + evaluación real
@each_personality
def test_failing_evaluation_in_recovery_keeps_readings_and_drops_alerts(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    name: str,
) -> None:
    """DC-35 con la evaluación real: la alerta ya insertada se revierte con el SAVEPOINT cuando
    falla el consejo; las lecturas se guardan y queda un ERROR sin datos."""
    household = db.register(FakeHousehold(name, tag="savepoint"), BACKFILL_AT)
    db.add_backfill(household, BACKFILL_AT)
    peak = bogota(2026, 11, 22, 19)
    sensor = household.sensors["cocina"]
    install_spikes(
        monkeypatch, {(sensor, peak): critical_value(db.same_hour_average(household, "cocina",
                                                                          peak))}
    )

    def broken(*_args: object, **_kwargs: object) -> UUID:
        raise OperationalError("INSERT", {}, PgError(f"{SECRET} {household.id}"))

    monkeypatch.setattr(tips_data, "insert_tip", broken)
    session = db.session()

    saved = hour_recovery.fill_missing_hours(session, household.id, bogota(2026, 11, 22, 20, 10))

    assert saved == 2 * len(household.sensors)
    assert sum(1 for key in db.saved if key[1] >= peak - timedelta(hours=1)) == saved
    assert db.alerts() == [] and db.tips() == []  # el SAVEPOINT se revirtió entero
    assert session.commits == 1 and session.savepoint_rollbacks == 1
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and "Evaluación de alertas fallida" in errors[0].getMessage()
    assert SECRET not in caplog.text and str(household.id) not in caplog.text


# ------------------------------------------------------------------ miembros que llegaron después
@each_personality
def test_a_member_who_joined_after_the_event_gets_nothing(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """RN-XV-06, RN-VI-02: la recuperación de las 20:10 genera el pico de las 19:00 (evento a
    las 20:00). Quien entró a las 20:05 no recibe la alerta, ni la fila del consejo, ni el aviso;
    quien ya estaba (o entró justo a las 20:00) sí."""
    event = bogota(2026, 11, 22, 20)
    household = db.register(
        FakeHousehold(name, tag="ingreso"), BACKFILL_AT,
        [Member(ADMIN, rol="administrador"), Member(EDGE, fecha_ingreso=event),
         Member(LATE, fecha_ingreso=event + timedelta(minutes=5))],
    )
    db.add_backfill(household, BACKFILL_AT)
    peak = event - timedelta(hours=1)
    sensor = household.sensors["cocina"]
    install_spikes(
        monkeypatch, {(sensor, peak): critical_value(db.same_hour_average(household, "cocina",
                                                                          peak))}
    )

    hour_recovery.fill_missing_hours(db.session(), household.id, event + timedelta(minutes=10))

    alert = next(a for a in db.alerts(household.id) if a["regla_origen"] == "consumo_critico")
    assert alert["created_at"] == event
    (tip,) = db.tips(household.id)
    notice = next(a for a in db.alerts(household.id)
                  if a["clave_evento"] == f"nuevo_consejo:{tip['id']}")
    assert db.deliveries(alert["id"]) == {ADMIN, EDGE}
    assert set(db.assignments(tip["id"])) == {ADMIN, EDGE}
    assert db.deliveries(notice["id"]) == {ADMIN, EDGE}


def test_a_member_who_joined_after_the_event_has_nothing_to_read(
    db: FakeAlertsDatabase,
) -> None:
    """Directo sobre la evaluación: el miembro nuevo no tiene alertas ni consejos del evento."""
    personality = load_personalities()["Consumo familiar"]
    live = bogota(2026, 11, 23, 12)
    event = live + timedelta(hours=1)
    household = db.register(
        FakeHousehold("Consumo familiar", tag="ingreso-directo"), BACKFILL_AT,
        [Member(ADMIN, rol="administrador"), Member(LATE, fecha_ingreso=event + timedelta(days=1))],
    )
    seed_averages(db, household, live, {"cocina": 3 * personality.zone_kwh_for_hour("cocina", 12)})

    assert evaluate(db, household, live) == LiveEvaluationSummary(alerts=2, tips=1)

    alerts = db.alerts(household.id)
    assert all(db.deliveries(a["id"]) == {ADMIN} for a in alerts)
    (tip,) = db.tips(household.id)
    assert set(db.assignments(tip["id"])) == {ADMIN}
