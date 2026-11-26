"""Carrera entre eliminar la cuenta y aceptar una invitación (RN-IX-09, RN-X-06, DC-36).

Antes: entre el commit de `delete_account` y el borrado en Supabase Auth la persona podía aceptar
una invitación; la cascada de Auth dejaba después una membresía activa sin usuario (o fallaba por
miembros_activo_con_usuario). Ahora, con el orden de bloqueo único hogar → membresía → usuario
(docstrings de `users.delete_account` y `members_invitations.accept_invitation`):

- `delete_account` bloquea la ficha después del hogar y la membresía, reintenta (rollback y
  nueva vuelta) si apareció una membresía activa mientras esperaba, y borra la ficha DENTRO de la
  transacción, antes del commit.
- `accept_invitation` bloquea la ficha (paso 3): si ya no existe, 404 `NO_ENCONTRADO` (el
  contrato, en components.responses.NoEncontrado, reserva `FICHA_NO_CREADA` para `/usuarios/me`).

Se simula «la otra transacción» con ganchos del doble en memoria (`db.hooks`), que confirman
cambios justo antes de una función de datos de la transacción que espera.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.config import Settings
from app.errors import ApiError, CodigoError
from app.services import members_invitations
from app.services import users as users_service
from tests.services.members_fakes import (
    FakeMembersDatabase,
    FakeMembership,
    install_fake_members_database,
)

NOW = datetime(2026, 11, 25, 15, 0, tzinfo=UTC)
JOINED = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
HOGAR = UUID("11111111-2222-4333-8444-555555555555")
OTRO_HOGAR = UUID("22222222-3333-4444-8555-666666666666")
ADMIN = UUID("aaaaaaaa-0000-4000-8000-000000000001")
OTRO_ADMIN = UUID("aaaaaaaa-0000-4000-8000-000000000009")
CARLA = UUID("cccccccc-0000-4000-8000-000000000003")
CORREO_CARLA = "carla@example.com"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeMembersDatabase:
    """Casa Pérez (Ana, administradora) invitó a Carla; Carla tiene ficha y aún no tiene hogar."""
    fake = FakeMembersDatabase()
    fake.add_household(HOGAR, "Casa Pérez")
    fake.add_household(OTRO_HOGAR, "Otra casa")
    fake.add_user(ADMIN, "Ana Pérez", "ana@example.com")
    fake.add_user(OTRO_ADMIN, "Otro Admin", "otro@example.com")
    fake.add_user(CARLA, "Carla Díaz", CORREO_CARLA)
    fake.add_membership(HOGAR, ADMIN, "administrador", fecha_ingreso=JOINED)
    fake.add_membership(OTRO_HOGAR, OTRO_ADMIN, "administrador", fecha_ingreso=JOINED)
    install_fake_members_database(monkeypatch, fake)
    return fake


@pytest.fixture
def settings() -> Settings:
    return Settings.model_construct()


def _invite_carla(db: FakeMembersDatabase) -> UUID:
    return db.add_invitation(
        HOGAR, CORREO_CARLA, invitado_por=ADMIN, expira_en=NOW + timedelta(days=5)
    )


def _membership(db: FakeMembersDatabase, membresia_id: UUID) -> FakeMembership:
    return db.committed.memberships[membresia_id]


# (1) -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("carla_has_household", [False, True])
def test_accept_in_the_gap_before_auth_deletion_is_404_no_encontrado(
    db: FakeMembersDatabase, settings: Settings, carla_has_household: bool
) -> None:
    invitation = _invite_carla(db)
    if carla_has_household:
        db.add_membership(OTRO_HOGAR, CARLA, fecha_ingreso=JOINED)
    session_delete = db.session("eliminar")
    session_accept = db.session("aceptar")
    outcome: dict[str, Any] = {}

    def accept_while_auth_is_deleted() -> None:
        # Ya hubo commit de la baja; Supabase Auth todavía no borró la cuenta.
        assert ("commit",) in db.events
        try:
            members_invitations.accept_invitation(  # type: ignore[arg-type]
                session_accept, CARLA, CORREO_CARLA, invitation, now=NOW
            )
        except ApiError as exc:
            outcome["error"] = exc

    db.hooks["delete_auth_user"] = accept_while_auth_is_deleted

    users_service.delete_account(session_delete, CARLA, settings, now=NOW)  # type: ignore[arg-type]

    error = outcome["error"]
    assert (error.status_code, error.codigo) == (404, CodigoError.NO_ENCONTRADO)
    # El 404 sale del paso 3 (ficha bloqueada y ya borrada), no de la invitación.
    assert ("lock_user_profile", CARLA) in db.events
    assert "insert_member_membership" not in db.names()
    assert session_accept.commits == 0
    assert db.active_memberships_of(CARLA) == []
    assert CARLA not in db.committed.profiles
    assert db.committed.invitations[invitation].estado == "pendiente"
    assert db.committed.alerts == {}
    assert session_delete.commits == 1


# (2) -------------------------------------------------------------------------------------------


def test_membership_accepted_while_waiting_for_profile_lock_retries_and_closes_it(
    db: FakeMembersDatabase, settings: Settings
) -> None:
    invitation = _invite_carla(db)
    session_delete = db.session("eliminar")
    session_accept = db.session("aceptar")
    accepted: dict[str, Any] = {}

    def accept_confirmed_meanwhile() -> None:
        # La aceptación tenía la ficha bloqueada y confirmó; la baja esperaba ese bloqueo.
        accepted["membership"] = members_invitations.accept_invitation(  # type: ignore[arg-type]
            session_accept, CARLA, CORREO_CARLA, invitation, now=NOW
        )
        accepted["events"] = len(db.events)

    db.hooks["lock_user_profile"] = accept_confirmed_meanwhile

    users_service.delete_account(session_delete, CARLA, settings, now=NOW)  # type: ignore[arg-type]

    membresia_id = accepted["membership"].membresia_id
    after_accept = db.events[accepted["events"] :]
    assert after_accept == [
        ("lock_user_profile", CARLA),  # el bloqueo que esperaba, ya concedido
        ("get_active_membership_of_user", CARLA, False),  # ¿apareció una membresía? sí
        ("rollback",),
        # Segunda vuelta con el orden único: hogar → membresía → ficha.
        ("get_active_membership_of_user", CARLA, False),
        ("lock_household", HOGAR),
        ("get_active_membership_of_user", CARLA, True),
        ("lock_user_profile", CARLA),
        ("count_other_active_members", HOGAR, CARLA),
        ("close_membership", membresia_id, NOW),
        ("delete_user_profile", CARLA),
        ("commit",),
        ("delete_auth_user", CARLA),
        ("delete_avatar_files", CARLA),
    ]
    assert session_delete.rollbacks == 1
    assert session_delete.commits == 1
    closed = _membership(db, membresia_id)
    assert (closed.estado, closed.fecha_salida, closed.usuario_id) == ("inactivo", NOW, None)
    assert db.active_memberships_of(CARLA) == []
    assert HOGAR in db.committed.households  # Ana sigue: el hogar no se borra
    assert CARLA not in db.committed.profiles


# (3) -------------------------------------------------------------------------------------------


def test_delete_account_order_household_membership_profile_close_delete_commit_auth(
    db: FakeMembersDatabase, settings: Settings
) -> None:
    membresia_id = db.add_membership(OTRO_HOGAR, CARLA, fecha_ingreso=JOINED)
    session = db.session()

    users_service.delete_account(session, CARLA, settings, now=NOW)  # type: ignore[arg-type]

    assert db.events == [
        ("get_active_membership_of_user", CARLA, False),
        ("lock_household", OTRO_HOGAR),
        ("get_active_membership_of_user", CARLA, True),
        ("lock_user_profile", CARLA),
        ("count_other_active_members", OTRO_HOGAR, CARLA),
        ("close_membership", membresia_id, NOW),
        ("delete_user_profile", CARLA),
        ("commit",),
        ("delete_auth_user", CARLA),
        ("delete_avatar_files", CARLA),
    ]
    assert session.rollbacks == 0


def test_delete_account_only_member_deletes_household_then_profile_before_commit(
    db: FakeMembersDatabase, settings: Settings
) -> None:
    solo = UUID("33333333-4444-4555-8666-777777777777")
    db.add_household(solo, "Casa de Carla")
    membresia_id = db.add_membership(solo, CARLA, "administrador", fecha_ingreso=JOINED)
    session = db.session()

    users_service.delete_account(session, CARLA, settings, now=NOW)  # type: ignore[arg-type]

    names = db.names()
    assert names[names.index("close_membership") :] == [
        "close_membership",
        "delete_household",
        "delete_user_profile",
        "commit",
        "delete_auth_user",
        "delete_avatar_files",
    ]
    assert solo not in db.committed.households
    assert membresia_id not in db.committed.memberships


def test_delete_account_without_membership_rechecks_and_deletes_profile(
    db: FakeMembersDatabase, settings: Settings
) -> None:
    session = db.session()

    users_service.delete_account(session, CARLA, settings, now=NOW)  # type: ignore[arg-type]

    assert db.events == [
        ("get_active_membership_of_user", CARLA, False),
        ("lock_user_profile", CARLA),
        ("get_active_membership_of_user", CARLA, False),
        ("delete_user_profile", CARLA),
        ("commit",),
        ("delete_auth_user", CARLA),
        ("delete_avatar_files", CARLA),
    ]
    assert CARLA not in db.committed.profiles


def test_delete_account_without_profile_skips_profile_deletion(
    db: FakeMembersDatabase, settings: Settings
) -> None:
    del db.committed.profiles[CARLA]
    session = db.session()

    users_service.delete_account(session, CARLA, settings, now=NOW)  # type: ignore[arg-type]

    assert "delete_user_profile" not in db.names()
    assert db.names()[-3:] == ["commit", "delete_auth_user", "delete_avatar_files"]


def test_delete_account_admin_with_others_is_409_and_keeps_profile(
    db: FakeMembersDatabase, settings: Settings
) -> None:
    db.add_membership(HOGAR, CARLA, fecha_ingreso=JOINED)
    session = db.session()

    with pytest.raises(ApiError) as caught:
        users_service.delete_account(session, ADMIN, settings, now=NOW)  # type: ignore[arg-type]

    assert caught.value.codigo == CodigoError.ADMIN_DEBE_TRANSFERIR
    assert session.commits == 0
    assert "delete_user_profile" not in db.names()
    assert ADMIN in db.committed.profiles


# (4) -------------------------------------------------------------------------------------------


def test_membership_changing_every_round_is_runtime_error_without_commit(
    db: FakeMembersDatabase, settings: Settings
) -> None:
    session = db.session()

    def accept_meanwhile() -> None:
        # Otra aceptación confirma mientras se espera la ficha (cada vuelta).
        db.add_membership(HOGAR, CARLA, fecha_ingreso=NOW)
        db.hooks["lock_user_profile"] = accept_meanwhile

    def expel_meanwhile() -> None:
        # Mientras se espera el hogar, la expulsan (otra transacción confirma).
        for membership in db.active_memberships_of(CARLA):
            membership.estado = "inactivo"
            membership.fecha_salida = NOW

    db.hooks["lock_user_profile"] = accept_meanwhile
    db.hooks["lock_household"] = expel_meanwhile

    with pytest.raises(RuntimeError):
        users_service.delete_account(session, CARLA, settings, now=NOW)  # type: ignore[arg-type]

    assert session.commits == 0
    assert session.rollbacks == users_service.LOCK_ATTEMPTS
    names = db.names()
    assert names.count("lock_user_profile") == users_service.LOCK_ATTEMPTS
    assert "delete_user_profile" not in names
    assert "delete_auth_user" not in names
    assert CARLA in db.committed.profiles
