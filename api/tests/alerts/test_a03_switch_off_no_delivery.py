"""A-03 · Alertas: Miembro con el interruptor apagado al disparar.

Esperado: Sin fila en `alertas_usuario` para él. Regla: RN-VI-02, XIV-06 (y RN-VI-04:
`notif_consumo` para consumo e información, `notif_consejos` para el aviso «Nuevo consejo»;
miembros solo con `hogares.permiso_recibir_alertas`; el administrador siempre, si su interruptor
está encendido; los consejos van a todos los miembros activos, RN-VI-03, RN-XV-06).
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Escenario real: backfill del simulador y una recuperación en vivo con la cocina en crítico.
"""

import pytest

from app.services import hour_recovery
from tests.services.alerts_fakes import (
    ADMIN,
    BACKFILL_AT,
    DAY,
    FakeAlertsDatabase,
    Member,
    critical_value,
    install_fake_alerts_database,
    install_spikes,
    zone_id,
)
from tests.services.recovery_fakes import FakeHousehold
from tests.simulator.support import bogota, stable_id

ZONE = "cocina"
PEAK = bogota(2026, 11, 22, 19)
CONSUMPTION_OFF = stable_id("usuario", "sin-consumo")
TIPS_OFF = stable_id("usuario", "sin-consejos")
ALL_ON = stable_id("usuario", "todo")
FORMER = stable_id("usuario", "inactivo")


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeAlertsDatabase:
    return install_fake_alerts_database(monkeypatch)


def run_peak(
    db: FakeAlertsDatabase,
    monkeypatch: pytest.MonkeyPatch,
    members: list[Member],
    permission: bool,
) -> tuple[dict, dict, dict]:
    """(alerta de consumo, aviso «Nuevo consejo», consejo) de la cocina tras la recuperación."""
    household = db.register(
        FakeHousehold("Consumo familiar", tag="a03"), BACKFILL_AT, members, permission
    )
    db.add_backfill(household, BACKFILL_AT)
    sensor = household.sensors[ZONE]
    install_spikes(
        monkeypatch, {(sensor, PEAK): critical_value(db.same_hour_average(household, ZONE, PEAK))}
    )
    hour_recovery.fill_missing_hours(db.session(), household.id, bogota(2026, 11, 22, 20, 10))
    zona = zone_id(household, ZONE)
    by_key = {alert["clave_evento"]: alert for alert in db.alerts(household.id)}
    alert = by_key[f"consumo_critico:{zona}:{DAY}"]
    (tip,) = [t for t in db.tips(household.id) if (t["regla_origen"], t["zona_id"]) == (
        "zona_critica", zona)]
    notice = by_key[f"nuevo_consejo:{tip['id']}"]
    return alert, notice, tip


def household_members() -> list[Member]:
    return [
        Member(ADMIN, rol="administrador"),
        Member(CONSUMPTION_OFF, notif_consumo=False),
        Member(TIPS_OFF, notif_consejos=False),
        Member(ALL_ON),
        Member(FORMER, estado="inactivo"),
    ]


def test_a03_switch_off_means_no_delivery(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert, notice, tip = run_peak(db, monkeypatch, household_members(), permission=True)

    # Consumo: sin fila para quien tiene `notif_consumo` apagado (ni para el inactivo).
    assert db.deliveries(alert["id"]) == {ADMIN, TIPS_OFF, ALL_ON}
    # Aviso «Nuevo consejo» (categoría consejo): manda `notif_consejos`.
    assert notice["categoria"] == "consejo" and notice["created_at"] == alert["created_at"]
    assert db.deliveries(notice["id"]) == {ADMIN, CONSUMPTION_OFF, ALL_ON}
    # El consejo es de todos los miembros activos, con o sin interruptor (RN-VI-03, RN-XV-06).
    assert set(db.assignments(tip["id"])) == {ADMIN, CONSUMPTION_OFF, TIPS_OFF, ALL_ON}
    # Las entregas nacen sin leer.
    assert {db.tables["alertas_usuario"][(alert["id"], user)] for user in
            db.deliveries(alert["id"])} == {None}


def test_a03_without_household_permission_only_the_admin_receives(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert, notice, tip = run_peak(db, monkeypatch, household_members(), permission=False)

    assert db.deliveries(alert["id"]) == {ADMIN}
    assert db.deliveries(notice["id"]) == {ADMIN}
    assert set(db.assignments(tip["id"])) == {ADMIN, CONSUMPTION_OFF, TIPS_OFF, ALL_ON}


def test_a03_the_admin_with_the_switch_off_receives_nothing(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    members = [
        Member(ADMIN, rol="administrador", notif_consumo=False, notif_consejos=False),
        Member(ALL_ON),
    ]
    alert, notice, tip = run_peak(db, monkeypatch, members, permission=True)

    assert db.deliveries(alert["id"]) == {ALL_ON}
    assert db.deliveries(notice["id"]) == {ALL_ON}
    assert set(db.assignments(tip["id"])) == {ADMIN, ALL_ON}
