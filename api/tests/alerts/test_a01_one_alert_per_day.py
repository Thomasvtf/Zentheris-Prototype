"""A-01 · Alertas: Zona en crítico dos veces el mismo día.

Esperado: 1 alerta. Regla: RN-XIV-08 (también DC-25: clave `<regla>:<zona_id>:<AAAA-MM-DD>`;
DC-35: solo horas en vivo, evaluadas por la recuperación dentro de un SAVEPOINT).
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Con las 5 personalidades: backfill real de 30 días (simulador oficial), y dos recuperaciones
distintas la misma noche; en cada una la cocina queda en crítico frente a su promedio real de la
misma hora (19:00 y 21:00). Los dobles de `app.data` están en tests/services/alerts_fakes.py.
"""

from datetime import timedelta

import pytest

from app.services import hour_recovery
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.services.alerts_fakes import (
    BACKFILL_AT,
    DAY,
    FakeAlertsDatabase,
    critical_value,
    install_fake_alerts_database,
    install_spikes,
    zone_id,
)
from tests.services.recovery_fakes import FakeHousehold
from tests.simulator.support import bogota

ZONE = "cocina"  # todas las personalidades la tienen
FIRST_PEAK = bogota(2026, 11, 22, 19)
SECOND_PEAK = bogota(2026, 11, 22, 21)


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeAlertsDatabase:
    return install_fake_alerts_database(monkeypatch)


def critical_alerts(db: FakeAlertsDatabase, household: FakeHousehold) -> list[dict]:
    zona = zone_id(household, ZONE)
    return [
        alert
        for alert in db.alerts(household.id)
        if alert["regla_origen"] == "consumo_critico" and alert["zona_id"] == zona
    ]


@pytest.mark.parametrize("name", PERSONALITY_ORDER)
def test_a01_critical_twice_the_same_day_in_two_recoveries_gives_one_alert(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    household = db.register(FakeHousehold(name, tag="a01"), created_at=BACKFILL_AT)
    db.add_backfill(household, BACKFILL_AT)
    sensor = household.sensors[ZONE]
    install_spikes(
        monkeypatch,
        {
            (sensor, peak): critical_value(db.same_hour_average(household, ZONE, peak))
            for peak in (FIRST_PEAK, SECOND_PEAK)
        },
    )

    # 1.ª recuperación (20:10): genera 18:00 y 19:00 → la cocina en crítico a las 19:00.
    hour_recovery.fill_missing_hours(db.session(), household.id, bogota(2026, 11, 22, 20, 10))
    (alert,) = critical_alerts(db, household)
    assert alert["clave_evento"] == f"consumo_critico:{zone_id(household, ZONE)}:{DAY}"
    assert alert["severidad"] == "critica" and alert["categoria"] == "consumo"
    assert alert["titulo"] == "Consumo crítico en Cocina"
    # created_at = momento del evento (fin de la hora que la disparó), siempre el mismo día.
    assert alert["created_at"] - timedelta(hours=1) in {bogota(2026, 11, 22, 18), FIRST_PEAK}

    # 2.ª recuperación (22:10): genera 20:00 y 21:00 → otra vez crítico a las 21:00, mismo día.
    hour_recovery.fill_missing_hours(db.session(), household.id, bogota(2026, 11, 22, 22, 10))

    assert critical_alerts(db, household) == [alert]  # una (1) alerta: RN-XIV-08
    # Tampoco se repite su consejo (vigente 7 días, RN-XV-05).
    zone_tips = [
        tip
        for tip in db.tips(household.id)
        if tip["regla_origen"] == "zona_critica" and tip["zona_id"] == zone_id(household, ZONE)
    ]
    assert len(zone_tips) == 1 and zone_tips[0]["prioridad"] == "alta"
    # Las lecturas en vivo se guardaron todas: 4 h × zonas.
    live = [key for key in db.saved if key[1] >= BACKFILL_AT.replace(minute=0)]
    assert len(live) == 4 * len(household.sensors)


@pytest.mark.parametrize("name", PERSONALITY_ORDER)
def test_a01_the_next_day_is_a_new_alert(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Otro día de Bogotá es otra clave: crítico el domingo y el lunes → 2 alertas."""
    household = db.register(FakeHousehold(name, tag="a01-dias"), created_at=BACKFILL_AT)
    db.add_backfill(household, BACKFILL_AT)
    monday = bogota(2026, 11, 23, 0)
    sensor = household.sensors[ZONE]
    install_spikes(
        monkeypatch,
        {
            (sensor, FIRST_PEAK): critical_value(db.same_hour_average(household, ZONE, FIRST_PEAK)),
            (sensor, monday): critical_value(db.same_hour_average(household, ZONE, monday)),
        },
    )

    hour_recovery.fill_missing_hours(db.session(), household.id, bogota(2026, 11, 23, 1, 10))

    keys = {alert["clave_evento"] for alert in critical_alerts(db, household)}
    zona = zone_id(household, ZONE)
    assert keys == {f"consumo_critico:{zona}:{DAY}", f"consumo_critico:{zona}:2026-11-23"}
