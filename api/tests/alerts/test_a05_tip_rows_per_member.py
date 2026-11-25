"""A-05 · Consejos: Consejo creado con 3 miembros activos.

Esperado: 3 filas `pendiente`. Regla: RN-XV-06 (y RN-VI-03: sin mirar permiso ni interruptor;
un miembro que ingresa después no recibe consejos anteriores).
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Escenario real: backfill del simulador y una recuperación en vivo con la cocina en crítico, que
crea el consejo `zona_critica` de la cocina.
"""

import pytest

from app.services import hour_recovery
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

ZONE = "cocina"
PEAK = bogota(2026, 11, 22, 19)
SECOND = stable_id("usuario", "segundo")
THIRD = stable_id("usuario", "tercero")
FORMER = stable_id("usuario", "se-fue")
LATECOMER = stable_id("usuario", "llega-despues")


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeAlertsDatabase:
    return install_fake_alerts_database(monkeypatch)


def test_a05_three_active_members_get_three_pending_rows(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    members = [
        Member(ADMIN, rol="administrador"),
        Member(SECOND, notif_consejos=False),  # el interruptor no cambia el consejo
        Member(THIRD, notif_consumo=False),
        Member(FORMER, estado="inactivo"),
    ]
    household = db.register(
        FakeHousehold("Consumo amplio", tag="a05"), BACKFILL_AT, members, permission=False
    )
    db.add_backfill(household, BACKFILL_AT)
    sensor = household.sensors[ZONE]
    install_spikes(
        monkeypatch, {(sensor, PEAK): critical_value(db.same_hour_average(household, ZONE, PEAK))}
    )

    hour_recovery.fill_missing_hours(db.session(), household.id, bogota(2026, 11, 22, 20, 10))

    (tip,) = [
        t for t in db.tips(household.id)
        if (t["regla_origen"], t["zona_id"]) == ("zona_critica", zone_id(household, ZONE))
    ]
    rows = db.assignments(tip["id"])
    assert set(rows) == {ADMIN, SECOND, THIRD}  # 3 filas: ni el inactivo
    assert all(row == {"estado": "pendiente", "completada_en": None} for row in rows.values())
    # Cada consejo creado en la recuperación tiene sus 3 filas.
    for other in db.tips(household.id):
        assert set(db.assignments(other["id"])) == {ADMIN, SECOND, THIRD}

    # Quien ingresa después no recibe el consejo anterior (RN-XV-06).
    db.members[household.id].append(Member(LATECOMER))
    hour_recovery.fill_missing_hours(db.session(), household.id, bogota(2026, 11, 22, 21, 10))
    assert set(db.assignments(tip["id"])) == {ADMIN, SECOND, THIRD}
