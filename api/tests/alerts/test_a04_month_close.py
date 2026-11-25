"""A-04 · Alertas: Cierre de mes por encima de la referencia.

Esperado: Alerta de advertencia + consejo general de prioridad baja. Regla: RN-XIV-07, XV-07
(y DC-32, RN-XIV-07: se cierra cuando la recuperación en vivo genera la hora 23:00 del último día;
referencia = meta vigente el último día o promedio de los días completos anteriores × días del
mes; DC-35: consejo y aviso «Nuevo consejo» con la alerta; created_at = momento del evento,
00:00 del día 1 siguiente).
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Con las 5 personalidades: backfill real de 70 días que termina el 30/11/2026 a las 22:00 y una
recuperación el 01/12 a las 00:10 (genera la hora 23:00 del 30). Para fijar el resultado sin
depender del azar se usa una meta (1 kWh: encima; 1 000 000 kWh: dentro) o se escalan las
lecturas guardadas de noviembre (×1,5: encima del promedio; ×0,5: dentro).
"""

from decimal import Decimal

import pytest

from app.domain.formats import format_kwh
from app.services import hour_recovery
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.services.alerts_fakes import (
    ADMIN,
    FakeAlertsDatabase,
    Member,
    install_fake_alerts_database,
)
from tests.services.recovery_fakes import FakeHousehold
from tests.simulator.support import bogota, stable_id

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)
BACKFILL_END = bogota(2026, 11, 30, 23, 10)  # última hora del backfill: 30/11 22:00
LONG_BACKFILL = 720 + 24 * 40  # días completos de octubre para el promedio
CLOSE_RUN = bogota(2026, 12, 1, 0, 10)  # genera la hora 23:00 del 30/11
MONTH_END = bogota(2026, 12, 1)
CREATED = bogota(2026, 10, 1)
MEMBER = stable_id("usuario", "miembro-a04")
NOV = (2026, 11)


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeAlertsDatabase:
    return install_fake_alerts_database(monkeypatch)


def prepare(db: FakeAlertsDatabase, name: str, tag: str, hours: int = LONG_BACKFILL,
            created_at=CREATED, end=BACKFILL_END) -> FakeHousehold:
    members = [Member(ADMIN, rol="administrador"), Member(MEMBER)]
    household = db.register(FakeHousehold(name, tag=tag), created_at, members)
    db.add_backfill(household, end, hours)
    return household


def scale_november(db: FakeAlertsDatabase, household: FakeHousehold, factor: str) -> None:
    sensors = set(household.sensors.values())
    for key, row in list(db.saved.items()):
        if key[0] in sensors and (key[1].year, key[1].month) == NOV:
            db.saved[key] = {**row, "consumo_kwh": row["consumo_kwh"] * Decimal(factor)}


def november_total(db: FakeAlertsDatabase, household: FakeHousehold) -> float:
    sensors = set(household.sensors.values())
    return sum(
        float(row["consumo_kwh"])
        for (sensor, moment), row in db.saved.items()
        if sensor in sensors and (moment.year, moment.month) == NOV
    )


def close_alerts(db: FakeAlertsDatabase, household: FakeHousehold) -> list[dict]:
    return [a for a in db.alerts(household.id) if a["regla_origen"].startswith("cierre_mes")]


def general_tips(db: FakeAlertsDatabase, household: FakeHousehold) -> list[dict]:
    return [t for t in db.tips(household.id) if t["regla_origen"] == "cierre_mes_encima"]


def check_above(db: FakeAlertsDatabase, household: FakeHousehold, phrase: str) -> None:
    (alert,) = close_alerts(db, household)
    assert alert["regla_origen"] == "cierre_mes_encima"
    assert alert["severidad"] == "advertencia" and alert["categoria"] == "informacion"
    assert alert["clave_evento"] == f"cierre_mes_encima:{household.id}:2026-11"
    assert alert["zona_id"] is None and alert["created_at"] == MONTH_END
    assert alert["titulo"] == "Cierre de noviembre: por encima de tu referencia"
    total = format_kwh(november_total(db, household))
    assert alert["mensaje"].startswith(f"Cerraste noviembre con {total} kWh, por encima de {phrase}")
    assert db.deliveries(alert["id"]) == {ADMIN, MEMBER}
    # Consejo general de prioridad baja, con una fila pendiente por miembro activo.
    (tip,) = general_tips(db, household)
    assert tip["categoria"] == "general" and tip["prioridad"] == "baja"
    assert tip["zona_id"] is None and tip["created_at"] == MONTH_END
    assert set(db.assignments(tip["id"])) == {ADMIN, MEMBER}
    # Aviso «Nuevo consejo» general con la clave del consejo y el mismo momento.
    notice = next(a for a in db.alerts(household.id)
                  if a["clave_evento"] == f"nuevo_consejo:{tip['id']}")
    assert notice["regla_origen"] == "nuevo_consejo_general"
    assert notice["categoria"] == "consejo" and notice["created_at"] == MONTH_END
    assert db.deliveries(notice["id"]) == {ADMIN, MEMBER}


def check_inside(db: FakeAlertsDatabase, household: FakeHousehold, phrase: str) -> None:
    (alert,) = close_alerts(db, household)
    assert alert["regla_origen"] == "cierre_mes_dentro"
    assert alert["severidad"] == "informativa" and alert["categoria"] == "informacion"
    assert alert["clave_evento"] == f"cierre_mes_dentro:{household.id}:2026-11"
    assert alert["created_at"] == MONTH_END
    assert alert["titulo"] == "Cierre de noviembre: dentro de tu referencia"
    total = format_kwh(november_total(db, household))
    assert alert["mensaje"] == f"Cerraste noviembre con {total} kWh, dentro de {phrase}."
    assert db.deliveries(alert["id"]) == {ADMIN, MEMBER}
    assert general_tips(db, household) == []  # dentro: sin consejo
    assert not any(a["regla_origen"] == "nuevo_consejo_general" for a in db.alerts(household.id))


@each_personality
def test_a04_above_the_goal_gives_a_warning_and_a_low_general_tip(
    db: FakeAlertsDatabase, name: str
) -> None:
    household = prepare(db, name, "a04-meta-encima")
    db.set_goal(household.id, bogota(2026, 11, 1).date(), None, 1.0)

    hour_recovery.fill_missing_hours(db.session(), household.id, CLOSE_RUN)

    check_above(db, household, "tu meta de 1,0 kWh")


@each_personality
def test_a04_inside_the_goal_is_informative_without_tip(db: FakeAlertsDatabase, name: str) -> None:
    household = prepare(db, name, "a04-meta-dentro")
    db.set_goal(household.id, bogota(2026, 11, 1).date(), None, 1_000_000.0)

    hour_recovery.fill_missing_hours(db.session(), household.id, CLOSE_RUN)

    check_inside(db, household, "tu meta de 1.000.000,0 kWh")


@each_personality
@pytest.mark.parametrize(("factor", "above"), [("1.5", True), ("0.5", False)])
def test_a04_without_goal_the_reference_is_the_average(
    db: FakeAlertsDatabase, name: str, factor: str, above: bool
) -> None:
    household = prepare(db, name, f"a04-promedio-{factor}")
    scale_november(db, household, factor)

    hour_recovery.fill_missing_hours(db.session(), household.id, CLOSE_RUN)

    (alert,) = close_alerts(db, household)
    assert "tu promedio de " in alert["mensaje"]
    if above:
        check_above(db, household, "tu promedio de ")
    else:
        assert alert["regla_origen"] == "cierre_mes_dentro"
        assert general_tips(db, household) == []


@each_personality
def test_a04_a_goal_closed_after_the_month_still_counts(db: FakeAlertsDatabase, name: str) -> None:
    """La meta vigente el último día del mes es la referencia aunque hoy ya no esté activa."""
    household = prepare(db, name, "a04-meta-cerrada")
    db.set_goal(household.id, bogota(2026, 11, 1).date(), bogota(2026, 12, 1).date(), 1.0)

    hour_recovery.fill_missing_hours(db.session(), household.id, CLOSE_RUN)

    check_above(db, household, "tu meta de 1,0 kWh")


def test_a04_the_month_is_closed_only_once(db: FakeAlertsDatabase) -> None:
    household = prepare(db, "Consumo intermedio", "a04-una-vez")
    db.set_goal(household.id, bogota(2026, 11, 1).date(), None, 1.0)
    hour_recovery.fill_missing_hours(db.session(), household.id, CLOSE_RUN)
    hour_recovery.fill_missing_hours(db.session(), household.id, bogota(2026, 12, 1, 3, 10))
    assert len(close_alerts(db, household)) == 1
    assert len(general_tips(db, household)) == 1


def test_a04_hour_by_hour_the_close_waits_for_the_23_hour(db: FakeAlertsDatabase) -> None:
    # Backfill hasta las 20:00 del 30/11; la tarea horaria genera 21:00, luego 22:00 y 23:00.
    household = prepare(db, "Consumo familiar", "a04-espera", end=bogota(2026, 11, 30, 21, 10))
    db.set_goal(household.id, bogota(2026, 11, 1).date(), None, 1.0)
    session = db.session()
    assert hour_recovery.fill_missing_hours(session, household.id, bogota(2026, 11, 30, 22, 10))
    assert close_alerts(db, household) == []  # sin la hora 23:00 del último día no hay cierre
    hour_recovery.fill_missing_hours(session, household.id, CLOSE_RUN)
    assert len(close_alerts(db, household)) == 1


def test_a04_household_created_after_the_month_has_no_close(db: FakeAlertsDatabase) -> None:
    household = prepare(db, "Consumo familiar", "a04-nuevo", created_at=MONTH_END)
    db.set_goal(household.id, bogota(2026, 11, 1).date(), None, 1.0)
    hour_recovery.fill_missing_hours(db.session(), household.id, CLOSE_RUN)
    assert close_alerts(db, household) == []


def test_a04_without_goal_nor_complete_previous_days_there_is_no_close(
    db: FakeAlertsDatabase,
) -> None:
    """DC-32, RN-XIV-07: sin meta ni días completos anteriores no hay referencia ni alerta.

    TODO(pendiente: cierre de mes sin referencia; RN-XIV-07 y DC-32 no lo definen).
    """
    household = prepare(db, "Consumo eficiente", "a04-sin-ref", hours=720)  # desde el 31/10 23:00
    hour_recovery.fill_missing_hours(db.session(), household.id, CLOSE_RUN)
    assert close_alerts(db, household) == []
    assert general_tips(db, household) == []
