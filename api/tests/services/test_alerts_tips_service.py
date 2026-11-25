"""Pruebas de app.services.alerts_tips con `app.data.*` falso en memoria (sin base ni red).

Los 5 casos de uso: `listarAlertas`, `contarAlertasNoLeidas`, `marcarAlertasLeidas`,
`listarConsejos` y `actualizarEstadoConsejo` (RN-XIV-03, RN-XIV-05, RN-VI-05, RN-XV-02 a
RN-XV-06; RN-IV-05 y DC-34: las consultas recuperan primero y, si la recuperación falla,
responden con lo guardado). La evaluación en vivo se prueba en `test_live_alerts_service.py`.
Los dobles están en `alerts_fakes.py` (recuperación real sobre el almacén en memoria).
"""

import logging
from datetime import timedelta

import pytest
from sqlalchemy.exc import OperationalError

from app.errors import NOT_FOUND_MESSAGE, ApiError, CodigoError
from app.schemas.alerts_tips import (
    AlertasMarcar,
    CategoriaAlerta,
    ConsejoEstadoActualizar,
)
from app.services import alerts_tips as service
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

OTHER = stable_id("usuario", "otro")
NOW = bogota(2026, 11, 23, 10, 0)
SECRET = "DETAIL: Key (hogar_id)=(secreto) already exists"


class PgError(Exception):
    pgcode = "40001"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeAlertsDatabase:
    return install_fake_alerts_database(monkeypatch)


# ================================================================== casos de uso
@pytest.fixture
def home(db: FakeAlertsDatabase) -> FakeHousehold:
    """Hogar sin lecturas (la recuperación no genera nada) con el admin y otro miembro."""
    return db.register(
        FakeHousehold("Consumo familiar", tag="casos"), BACKFILL_AT,
        [Member(ADMIN, rol="administrador"), Member(OTHER)],
    )


@pytest.fixture
def elsewhere(db: FakeAlertsDatabase) -> FakeHousehold:
    return db.register(FakeHousehold("Consumo amplio", tag="otro-hogar"), BACKFILL_AT,
                       [Member(ADMIN, rol="administrador")])


def break_recovery(db: FakeAlertsDatabase) -> None:
    db.failures["profile"] = OperationalError("SELECT", {}, PgError(SECRET))


def check_recovery_warning(caplog: pytest.LogCaptureFixture) -> None:
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert [r.getMessage() for r in warnings] == [hour_recovery.RECOVERY_SKIPPED_MESSAGE]
    assert SECRET not in caplog.text


# ------------------------------------------------------------------ listarAlertas
def seed_inbox(db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold) -> dict:
    cocina = zone_id(home, "cocina")
    ids = {
        "unread_old": db.seed_alert(home.id, created_at=NOW - timedelta(days=20), zona_id=cocina),
        "read_6d": db.seed_alert(home.id, created_at=NOW - timedelta(days=9),
                                 categoria="informacion", severidad="informativa"),
        "read_8d": db.seed_alert(home.id, created_at=NOW - timedelta(days=10)),
        "tip_notice": db.seed_alert(home.id, created_at=NOW - timedelta(hours=2),
                                    categoria="consejo", severidad="informativa"),
        "newest": db.seed_alert(home.id, created_at=NOW - timedelta(hours=1), zona_id=cocina,
                                severidad="advertencia"),
        "not_mine": db.seed_alert(home.id, created_at=NOW),
        "other_home": db.seed_alert(elsewhere.id, created_at=NOW),
    }
    db.seed_delivery(ids["unread_old"], ADMIN)
    db.seed_delivery(ids["read_6d"], ADMIN, NOW - timedelta(days=6))
    db.seed_delivery(ids["read_8d"], ADMIN, NOW - timedelta(days=8))
    db.seed_delivery(ids["tip_notice"], ADMIN)
    db.seed_delivery(ids["newest"], ADMIN)
    db.seed_delivery(ids["not_mine"], OTHER)
    db.seed_delivery(ids["other_home"], ADMIN)
    return ids


def test_list_alerts_hides_old_read_ones_and_orders_newest_first(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold
) -> None:
    """RN-XIV-04, RN-XIV-05: no leídas siempre; leídas solo 7 días; solo las de la persona."""
    ids = seed_inbox(db, home, elsewhere)
    result = service.list_alerts(db.session(), ADMIN, home.id, None, 50, NOW)

    assert [a.id for a in result.alertas] == [
        ids["newest"], ids["tip_notice"], ids["read_6d"], ids["unread_old"]
    ]
    newest = result.alertas[0]
    assert newest.zona_nombre == "Cocina" and newest.zona_id == zone_id(home, "cocina")
    assert newest.leida_en is None and newest.creada_en == NOW - timedelta(hours=1)
    assert result.alertas[2].zona_nombre is None and result.alertas[2].zona_id is None
    assert result.alertas[2].leida_en == NOW - timedelta(days=6)


def test_list_alerts_filters_by_category_and_limit(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold
) -> None:
    ids = seed_inbox(db, home, elsewhere)
    consejo = service.list_alerts(db.session(), ADMIN, home.id, CategoriaAlerta.CONSEJO, 50, NOW)
    assert [a.id for a in consejo.alertas] == [ids["tip_notice"]]
    consumo = service.list_alerts(db.session(), ADMIN, home.id, CategoriaAlerta.CONSUMO, 50, NOW)
    assert [a.id for a in consumo.alertas] == [ids["newest"], ids["unread_old"]]
    limited = service.list_alerts(db.session(), ADMIN, home.id, None, 2, NOW)
    assert [a.id for a in limited.alertas] == [ids["newest"], ids["tip_notice"]]


def test_an_alert_read_exactly_7_days_ago_is_hidden(
    db: FakeAlertsDatabase, home: FakeHousehold
) -> None:
    """RN-XIV-05: visible solo si `leida_en > now − 7 días`; justo 7 días después se oculta."""
    edge = db.seed_alert(home.id, created_at=NOW - timedelta(days=10))
    inside = db.seed_alert(home.id, created_at=NOW - timedelta(days=10))
    db.seed_delivery(edge, ADMIN, NOW - timedelta(days=7))
    db.seed_delivery(inside, ADMIN, NOW - timedelta(days=7) + timedelta(seconds=1))
    result = service.list_alerts(db.session(), ADMIN, home.id, None, 50, NOW)
    assert [a.id for a in result.alertas] == [inside]


def test_list_alerts_recovers_first(db: FakeAlertsDatabase, home: FakeHousehold) -> None:
    """RN-IV-05, DC-34: la recuperación corre antes de leer las alertas."""
    service.list_alerts(db.session(), ADMIN, home.id, None, 50, NOW)
    assert db.calls.index("lock") < db.calls.index("list_user_alerts")
    assert db.locked == [home.id]


def test_list_alerts_answers_with_saved_data_when_recovery_fails(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """RN-IV-05, DC-34: si la recuperación falla, 200 con lo guardado y un WARNING sin datos."""
    ids = seed_inbox(db, home, elsewhere)
    break_recovery(db)
    result = service.list_alerts(db.session(), ADMIN, home.id, None, 50, NOW)
    assert ids["newest"] in {a.id for a in result.alertas}
    check_recovery_warning(caplog)


# ------------------------------------------------------------------ contarAlertasNoLeidas
def test_count_unread_counts_only_my_unread_alerts(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold
) -> None:
    seed_inbox(db, home, elsewhere)
    assert service.count_unread_alerts(db.session(), ADMIN, home.id, NOW).cantidad == 3
    assert service.count_unread_alerts(db.session(), OTHER, home.id, NOW).cantidad == 1
    assert db.calls.index("lock") < db.calls.index("count_unread_alerts")


def test_count_unread_answers_when_recovery_fails(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold,
    caplog: pytest.LogCaptureFixture,
) -> None:
    seed_inbox(db, home, elsewhere)
    break_recovery(db)
    assert service.count_unread_alerts(db.session(), ADMIN, home.id, NOW).cantidad == 3
    check_recovery_warning(caplog)


def test_count_unread_includes_alerts_created_by_the_recovery(
    db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La campana ya cuenta lo que genera la recuperación de esa misma consulta."""
    household = db.register(FakeHousehold("Consumo familiar", tag="campana"), BACKFILL_AT)
    db.add_backfill(household, BACKFILL_AT)
    peak = bogota(2026, 11, 22, 19)
    install_spikes(monkeypatch, {
        (household.sensors["cocina"], peak):
            critical_value(db.same_hour_average(household, "cocina", peak))
    })
    count = service.count_unread_alerts(db.session(), ADMIN, household.id,
                                        bogota(2026, 11, 22, 20, 10))
    assert count.cantidad == len(db.alerts(household.id)) >= 2  # alerta + aviso del consejo


# ------------------------------------------------------------------ marcarAlertasLeidas
def test_mark_read_only_touches_my_unread_alerts(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold
) -> None:
    """RN-XIV-03, RN-VI-05: ya leídas, ajenas o de otro hogar se ignoran; sin recuperación."""
    ids = seed_inbox(db, home, elsewhere)
    session = db.session()
    payload = AlertasMarcar(alerta_ids=[ids["newest"], ids["read_6d"], ids["not_mine"],
                                        ids["other_home"], ids["unread_old"]])

    result = service.mark_alerts_read(session, ADMIN, home.id, payload, NOW)

    assert result.marcadas == 2
    assert session.commits == 1
    deliveries = db.tables["alertas_usuario"]
    assert deliveries[(ids["newest"], ADMIN)] == NOW
    assert deliveries[(ids["unread_old"], ADMIN)] == NOW
    assert deliveries[(ids["read_6d"], ADMIN)] == NOW - timedelta(days=6)  # conserva su fecha
    assert deliveries[(ids["not_mine"], OTHER)] is None  # la bandeja de otro no cambia
    assert deliveries[(ids["other_home"], ADMIN)] is None
    assert "lock" not in db.calls


def test_mark_read_without_now_uses_the_clock(db: FakeAlertsDatabase, home: FakeHousehold) -> None:
    alerta = db.seed_alert(home.id)
    db.seed_delivery(alerta, ADMIN)
    service.mark_alerts_read(db.session(), ADMIN, home.id, AlertasMarcar(alerta_ids=[alerta]))
    read_at = db.tables["alertas_usuario"][(alerta, ADMIN)]
    assert read_at is not None and read_at.utcoffset() is not None


# ------------------------------------------------------------------ listarConsejos
def seed_tips(db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold) -> dict:
    cocina = zone_id(home, "cocina")
    ids = {
        "baja": db.seed_tip(home.id, prioridad="baja", created_at=NOW - timedelta(days=1)),
        "alta_old": db.seed_tip(home.id, prioridad="alta", categoria="zona", zona_id=cocina,
                                regla_origen="zona_critica", created_at=NOW - timedelta(days=5)),
        "alta_new": db.seed_tip(home.id, prioridad="alta", categoria="zona", zona_id=cocina,
                                regla_origen="zona_critica", created_at=NOW - timedelta(days=2)),
        "media": db.seed_tip(home.id, prioridad="media", categoria="zona", zona_id=cocina,
                             regla_origen="zona_elevada", created_at=NOW - timedelta(days=3)),
        "expired": db.seed_tip(home.id, prioridad="alta", created_at=NOW - timedelta(days=8)),
        "done_recent": db.seed_tip(home.id, created_at=NOW - timedelta(days=20)),
        "done_old": db.seed_tip(home.id, created_at=NOW - timedelta(days=20)),
        "done_newer": db.seed_tip(home.id, created_at=NOW - timedelta(days=4)),
        "other_home": db.seed_tip(elsewhere.id, created_at=NOW),
    }
    for key in ("baja", "alta_old", "alta_new", "media", "expired"):
        db.seed_assignment(ids[key], ADMIN)
    db.seed_assignment(ids["done_recent"], ADMIN, "completada", NOW - timedelta(days=2))
    db.seed_assignment(ids["done_newer"], ADMIN, "completada", NOW - timedelta(hours=3))
    db.seed_assignment(ids["done_old"], ADMIN, "completada", NOW - timedelta(days=8))
    db.seed_assignment(ids["other_home"], ADMIN)
    db.seed_assignment(ids["baja"], OTHER, "completada", NOW - timedelta(days=1))
    return ids


def test_list_tips_orders_by_priority_with_completed_at_the_end(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold
) -> None:
    """RN-XV-02 a RN-XV-05: pendientes vigentes alta/media/baja; completados recientes al final."""
    ids = seed_tips(db, home, elsewhere)
    result = service.list_tips(db.session(), ADMIN, home.id, NOW)

    assert [t.id for t in result.consejos] == [
        ids["alta_new"], ids["alta_old"], ids["media"], ids["baja"],
        ids["done_newer"], ids["done_recent"],
    ]
    first = result.consejos[0]
    assert first.zona_nombre == "Cocina" and first.estado == "pendiente"
    assert first.completada_en is None and first.creado_en == NOW - timedelta(days=2)
    done = result.consejos[-1]
    assert done.estado == "completada" and done.completada_en == NOW - timedelta(days=2)
    assert done.zona_nombre is None
    # Seguimiento independiente (RN-VI-05): para el otro miembro «baja» está completado.
    other = service.list_tips(db.session(), OTHER, home.id, NOW)
    assert [(t.id, t.estado) for t in other.consejos] == [(ids["baja"], "completada")]


def test_list_tips_recovers_first_and_survives_a_failed_recovery(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold,
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = seed_tips(db, home, elsewhere)
    service.list_tips(db.session(), ADMIN, home.id, NOW)
    assert db.calls.index("lock") < db.calls.index("list_user_tips")
    break_recovery(db)
    result = service.list_tips(db.session(), ADMIN, home.id, NOW)
    assert result.consejos[0].id == ids["alta_new"]
    check_recovery_warning(caplog)


def test_list_tips_without_pending_is_the_all_under_control_case(
    db: FakeAlertsDatabase, home: FakeHousehold
) -> None:
    assert service.list_tips(db.session(), ADMIN, home.id, NOW).consejos == []


# ------------------------------------------------------------------ actualizarEstadoConsejo
def test_complete_and_uncomplete_a_tip(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold
) -> None:
    """RN-XV-03: `completada` registra completada_en = now; `pendiente` lo deja null."""
    ids = seed_tips(db, home, elsewhere)
    session = db.session()

    done = service.update_tip_status(session, ADMIN, home.id, ids["media"],
                                     ConsejoEstadoActualizar(estado="completada"), NOW)
    assert done.estado == "completada" and done.completada_en == NOW
    assert done.id == ids["media"] and done.prioridad == "media" and done.zona_nombre == "Cocina"
    assert db.tables["consejos_usuario"][(ids["media"], ADMIN)] == {
        "estado": "completada", "completada_en": NOW
    }
    assert session.commits == 1

    later = NOW + timedelta(hours=1)
    back = service.update_tip_status(session, ADMIN, home.id, ids["media"],
                                     ConsejoEstadoActualizar(estado="pendiente"), later)
    assert back.estado == "pendiente" and back.completada_en is None
    assert db.tables["consejos_usuario"][(ids["media"], ADMIN)]["completada_en"] is None
    assert session.commits == 2
    assert "lock" not in db.calls  # sin recuperación


def test_asking_for_the_current_state_changes_nothing(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold
) -> None:
    ids = seed_tips(db, home, elsewhere)
    session = db.session()
    same = service.update_tip_status(session, ADMIN, home.id, ids["done_recent"],
                                     ConsejoEstadoActualizar(estado="completada"), NOW)
    assert same.completada_en == NOW - timedelta(days=2)  # no reinicia los 7 días
    assert "update_user_tip_status" not in db.calls and session.commits == 0


@pytest.mark.parametrize("case", ["otro_hogar", "sin_fila", "no_existe"])
def test_update_a_foreign_tip_is_404(
    db: FakeAlertsDatabase, home: FakeHousehold, elsewhere: FakeHousehold, case: str
) -> None:
    """RN-XV-06: 404 NO_ENCONTRADO si la persona no tiene fila para ese consejo del hogar."""
    ids = seed_tips(db, home, elsewhere)
    user, consejo = {
        "otro_hogar": (ADMIN, ids["other_home"]),  # su fila es de otro hogar
        "sin_fila": (OTHER, ids["media"]),  # el consejo es del hogar, pero no tiene fila
        "no_existe": (ADMIN, stable_id("consejo", "inexistente")),
    }[case]
    session = db.session()
    with pytest.raises(ApiError) as raised:
        service.update_tip_status(session, user, home.id, consejo,
                                  ConsejoEstadoActualizar(estado="completada"), NOW)
    error = raised.value
    assert error.status_code == 404
    assert error.codigo == CodigoError.NO_ENCONTRADO
    assert error.mensaje == NOT_FOUND_MESSAGE
    assert session.commits == 0
    assert db.tables["consejos_usuario"].get((consejo, user), {}).get("completada_en") is None
