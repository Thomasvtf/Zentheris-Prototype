"""Pruebas de app.services.members_invitations con `app.data` falso en memoria (fase 9).

Las 11 operaciones de «Miembros e invitaciones»: camino feliz y cada error en el orden que
documenta cada función de app.services.members_invitations, con el `CodigoError` exacto y sin
commit (salvo las invitaciones vencidas, que se marcan 'expirada' y se confirman antes del 409,
DC-42). Vencida ⇔ `expira_en < now` (RN-X-05): en la frontera exacta sigue vigente. Reglas:
RN-II-01..04, RN-X-05..08, RN-IX-03, RN-XIV-06/07/08, RN-VI-02, DC-04, DC-25, DC-41, DC-42.
"""

import hashlib
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.config import Settings
from app.data import alerts as alerts_data
from app.data import invitations as invitations_data
from app.data import memberships as memberships_data
from app.errors import ApiError, CodigoError
from app.schemas.households import Permisos, PermisosActualizar
from app.schemas.members_invitations import (
    InvitacionCrear,
    InvitacionesRecibidasLista,
    InvitacionPendiente,
    InvitacionRecibida,
    InvitacionToken,
    MiembrosHogar,
)
from app.schemas.users import MembresiaResumen
from app.services import email as email_service
from app.services import members_invitations as service
from app.services.email import EmailDeliveryError
from tests.services.members_fakes import (
    FakeMembersDatabase,
    FakeMembersSession,
    install_fake_members_database,
)

# El envío real, guardado antes de que el doble lo sustituya (prueba del modo local, DC-04).
REAL_SEND_INVITATION_EMAIL = email_service.send_invitation_email

NOW = datetime(2026, 11, 25, 15, 0, tzinfo=UTC)
JOINED = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
HOGAR = UUID("11111111-2222-4333-8444-555555555555")
OTRO_HOGAR = UUID("22222222-3333-4444-8555-666666666666")
ADMIN = UUID("aaaaaaaa-0000-4000-8000-000000000001")
BETO = UUID("bbbbbbbb-0000-4000-8000-000000000002")
CARLA = UUID("cccccccc-0000-4000-8000-000000000003")
ADMIN_MEMBERSHIP = UUID("a0000000-0000-4000-8000-0000000000a1")
BETO_MEMBERSHIP = UUID("b0000000-0000-4000-8000-0000000000b2")
CORREO_ADMIN = "ana@example.com"
CORREO_BETO = "beto@example.com"
CORREO_CARLA = "carla@example.com"
LINK_BASE = "zentheris://invitacion?token="
SECOND = timedelta(seconds=1)


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeMembersDatabase:
    """Casa Pérez: Ana (administradora) y Beto (miembro). Carla tiene cuenta y ficha, sin hogar."""
    fake = FakeMembersDatabase()
    fake.add_household(HOGAR, "Casa Pérez")
    fake.add_household(OTRO_HOGAR, "Otra casa")
    fake.add_user(ADMIN, "Ana Pérez", CORREO_ADMIN)
    fake.add_user(BETO, "Beto Ruiz", CORREO_BETO)
    fake.add_user(CARLA, "Carla Díaz", CORREO_CARLA)
    fake.add_membership(
        HOGAR, ADMIN, "administrador", fecha_ingreso=JOINED, membresia_id=ADMIN_MEMBERSHIP
    )
    fake.add_membership(
        HOGAR, BETO, fecha_ingreso=JOINED + timedelta(days=1), membresia_id=BETO_MEMBERSHIP
    )
    install_fake_members_database(monkeypatch, fake)
    return fake


@pytest.fixture
def session(db: FakeMembersDatabase) -> FakeMembersSession:
    return db.session()


@pytest.fixture
def settings() -> Settings:
    return Settings.model_construct(invitation_link_base=LINK_BASE)


def _assert_error(exc: ApiError, status: int, codigo: CodigoError) -> None:
    assert exc.status_code == status
    assert exc.codigo == codigo
    assert exc.mensaje


def _raises(status: int, codigo: CodigoError, call: Any, *args: Any, **kwargs: Any) -> ApiError:
    with pytest.raises(ApiError) as caught:
        call(*args, **kwargs)
    _assert_error(caught.value, status, codigo)
    return caught.value


def _guard_events(user_id: UUID = ADMIN) -> list[tuple[Any, ...]]:
    """Guardia de gestión: hogar bloqueado y membresía del que llama releída con FOR UPDATE."""
    return [
        ("lock_household", HOGAR),
        ("get_user_membership_in_household", HOGAR, user_id, True),
    ]


def _membership(db: FakeMembersDatabase, membresia_id: UUID) -> Any:
    return db.committed.memberships[membresia_id]


def _pending_invitation(db: FakeMembersDatabase, **overrides: Any) -> UUID:
    values: dict[str, Any] = {
        "hogar_id": HOGAR,
        "correo": CORREO_CARLA,
        "invitado_por": ADMIN,
        "expira_en": NOW + timedelta(days=3),
    }
    values.update(overrides)
    return db.add_invitation(
        values.pop("hogar_id"),
        values.pop("correo"),
        **values,
    )


# --- listarMiembros ---------------------------------------------------------------------------


def test_list_members_admin_sees_members_pending_invitations_and_can_manage(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    _pending_invitation(db, correo="vencida@example.com", expira_en=NOW - timedelta(hours=1))

    view = service.list_members(session, ADMIN, HOGAR, now=NOW)  # type: ignore[arg-type]

    assert isinstance(view, MiembrosHogar)
    assert view.miembros_activos == 2
    assert [m.membresia_id for m in view.miembros] == [ADMIN_MEMBERSHIP, BETO_MEMBERSHIP]
    assert view.miembros[0].rol == "administrador"
    assert view.miembros[0].nombre_completo == "Ana Pérez"
    assert view.miembros[1].estado == "activo"
    assert view.invitaciones_pendientes is not None
    assert [i.id for i in view.invitaciones_pendientes] == [invitation]
    assert view.invitaciones_pendientes[0].correo_invitado == CORREO_CARLA
    assert view.permisos == Permisos(
        ver_consumo_actual=True, ver_historial=True, recibir_alertas=True, modificar_metas=False
    )
    assert view.puede_gestionar is True
    assert session.commits == 0
    assert "lock_household" not in db.names()


def test_list_members_member_does_not_get_invitations(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _pending_invitation(db)

    view = service.list_members(session, BETO, HOGAR, now=NOW)  # type: ignore[arg-type]

    assert view.invitaciones_pendientes is None
    assert view.puede_gestionar is False
    assert view.miembros_activos == 2
    assert "list_pending_invitations" not in db.names()


# --- actualizarPermisos -----------------------------------------------------------------------


def test_update_permissions_changes_only_sent_fields_and_commits(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    payload = PermisosActualizar.model_validate({"modificar_metas": True, "ver_historial": False})

    result = service.update_permissions(session, ADMIN, HOGAR, payload)  # type: ignore[arg-type]

    assert result == Permisos(
        ver_consumo_actual=True, ver_historial=False, recibir_alertas=True, modificar_metas=True
    )
    assert db.events == [
        *_guard_events(),
        ("update_permissions", HOGAR, {"ver_historial": False, "modificar_metas": True}),
        ("commit",),
    ]
    assert db.committed.households[HOGAR].permiso_modificar_metas is True


def test_update_permissions_guard_rechecks_admin_under_lock(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    # La dependencia vio a Ana como administradora, pero transfirió antes de que se bloqueara.
    _membership(db, ADMIN_MEMBERSHIP).rol = "miembro"
    _membership(db, BETO_MEMBERSHIP).rol = "administrador"
    payload = PermisosActualizar.model_validate({"modificar_metas": True})

    _raises(
        403,
        CodigoError.NO_ES_ADMINISTRADOR,
        service.update_permissions,
        session,
        ADMIN,
        HOGAR,
        payload,
    )

    assert db.events == _guard_events()
    assert session.commits == 0


def test_update_permissions_without_membership_is_404(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    payload = PermisosActualizar.model_validate({"modificar_metas": True})

    _raises(
        404, CodigoError.NO_ENCONTRADO, service.update_permissions, session, CARLA, HOGAR, payload
    )
    assert session.commits == 0


def test_update_permissions_empty_payload_is_422_without_update(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    # El esquema ya exige minProperties: 1; model_construct salta la validación para probar la
    # defensa en profundidad del servicio (model_fields_set vacío).
    payload = PermisosActualizar.model_construct()

    error = _raises(
        422, CodigoError.VALIDACION, service.update_permissions, session, ADMIN, HOGAR, payload
    )

    assert error.detalles == {
        "campos": [{"ubicacion": ["body"], "mensaje": service.EMPTY_PATCH_MESSAGE}]
    }
    assert "update_permissions" not in db.names()
    assert session.commits == 0


# --- salirDelHogar ----------------------------------------------------------------------------


def test_leave_household_member_closes_membership_and_commits(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    assert service.leave_household(session, BETO, HOGAR, now=NOW) is None  # type: ignore[arg-type]

    assert db.events == [
        ("lock_household", HOGAR),
        ("get_user_membership_in_household", HOGAR, BETO, True),
        ("close_membership", BETO_MEMBERSHIP, NOW),
        ("commit",),
    ]
    assert _membership(db, BETO_MEMBERSHIP).estado == "inactivo"
    assert _membership(db, BETO_MEMBERSHIP).fecha_salida == NOW


def test_leave_household_admin_with_others_must_transfer(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _raises(
        409,
        CodigoError.ADMIN_DEBE_TRANSFERIR,
        service.leave_household,
        session,
        ADMIN,
        HOGAR,
        now=NOW,
    )
    assert session.commits == 0
    assert "close_membership" not in db.names()


def test_leave_household_admin_alone_is_admin_unico_miembro(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _membership(db, BETO_MEMBERSHIP).estado = "inactivo"

    _raises(
        409,
        CodigoError.ADMIN_UNICO_MIEMBRO,
        service.leave_household,
        session,
        ADMIN,
        HOGAR,
        now=NOW,
    )
    assert session.commits == 0


def test_leave_household_without_membership_is_404(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _raises(404, CodigoError.NO_ENCONTRADO, service.leave_household, session, CARLA, HOGAR, now=NOW)
    assert db.events[0] == ("lock_household", HOGAR)
    assert session.commits == 0


def test_leave_household_uses_current_utc_time_by_default(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    before = datetime.now(UTC)
    service.leave_household(session, BETO, HOGAR)  # type: ignore[arg-type]
    closed_at = _membership(db, BETO_MEMBERSHIP).fecha_salida
    assert closed_at.tzinfo is not None
    assert before <= closed_at <= datetime.now(UTC)


# --- expulsarMiembro --------------------------------------------------------------------------


def test_remove_member_closes_target_and_commits(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    service.remove_member(session, ADMIN, HOGAR, BETO_MEMBERSHIP, now=NOW)  # type: ignore[arg-type]

    assert db.events == [
        *_guard_events(),
        ("get_household_membership", HOGAR, BETO_MEMBERSHIP, True),
        ("close_membership", BETO_MEMBERSHIP, NOW),
        ("commit",),
    ]
    assert _membership(db, BETO_MEMBERSHIP).estado == "inactivo"


def test_remove_member_by_non_admin_is_403(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _raises(
        403,
        CodigoError.NO_ES_ADMINISTRADOR,
        service.remove_member,
        session,
        BETO,
        HOGAR,
        ADMIN_MEMBERSHIP,
        now=NOW,
    )
    assert db.events == _guard_events(BETO)
    assert session.commits == 0


@pytest.mark.parametrize("case", ["missing", "other_household", "inactive"])
def test_remove_member_target_not_found_is_404(
    db: FakeMembersDatabase, session: FakeMembersSession, case: str
) -> None:
    if case == "missing":
        target = UUID("dddddddd-0000-4000-8000-000000000004")
    elif case == "other_household":
        target = db.add_membership(OTRO_HOGAR, CARLA, fecha_ingreso=JOINED)
    else:
        target = BETO_MEMBERSHIP
        _membership(db, BETO_MEMBERSHIP).estado = "inactivo"

    _raises(
        404,
        CodigoError.NO_ENCONTRADO,
        service.remove_member,
        session,
        ADMIN,
        HOGAR,
        target,
        now=NOW,
    )
    assert session.commits == 0
    assert "close_membership" not in db.names()


def test_remove_member_self_with_others_is_admin_debe_transferir(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _raises(
        409,
        CodigoError.ADMIN_DEBE_TRANSFERIR,
        service.remove_member,
        session,
        ADMIN,
        HOGAR,
        ADMIN_MEMBERSHIP,
        now=NOW,
    )
    assert session.commits == 0


def test_remove_member_self_alone_is_admin_unico_miembro(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _membership(db, BETO_MEMBERSHIP).estado = "inactivo"
    _raises(
        409,
        CodigoError.ADMIN_UNICO_MIEMBRO,
        service.remove_member,
        session,
        ADMIN,
        HOGAR,
        ADMIN_MEMBERSHIP,
        now=NOW,
    )
    assert session.commits == 0


# --- transferirAdministracion -----------------------------------------------------------------


def test_transfer_admin_demotes_current_admin_first_then_promotes_target(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _pending_invitation(db)

    view = service.transfer_admin(session, ADMIN, HOGAR, BETO_MEMBERSHIP, now=NOW)  # type: ignore[arg-type]

    names = db.names()
    assert db.events[:3] == [
        *_guard_events(),
        ("get_household_membership", HOGAR, BETO_MEMBERSHIP, True),
    ]
    roles = [event for event in db.events if event[0] == "set_membership_role"]
    assert roles == [
        ("set_membership_role", ADMIN_MEMBERSHIP, "miembro"),
        ("set_membership_role", BETO_MEMBERSHIP, "administrador"),
    ]
    assert names.index("set_membership_role") < names.index("commit")
    # La vista se arma ANTES del commit: después del commit nada puede fallar.
    assert names.index("list_active_members") < names.index("commit")
    assert names.index("get_household") < names.index("commit")
    assert names[-1] == "commit"
    assert session.commits == 1
    assert _membership(db, ADMIN_MEMBERSHIP).rol == "miembro"
    assert _membership(db, BETO_MEMBERSHIP).rol == "administrador"
    # La vista se arma ya como miembro: sin invitaciones y sin gestión.
    assert view.puede_gestionar is False
    assert view.invitaciones_pendientes is None
    assert view.miembros[0].membresia_id == BETO_MEMBERSHIP


def test_transfer_admin_to_self_is_422_validacion_on_membresia_id(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    error = _raises(
        422,
        CodigoError.VALIDACION,
        service.transfer_admin,
        session,
        ADMIN,
        HOGAR,
        ADMIN_MEMBERSHIP,
        now=NOW,
    )
    assert error.detalles is not None
    assert error.detalles["campos"][0]["ubicacion"] == ["path", "membresia_id"]
    assert "set_membership_role" not in db.names()
    assert session.commits == 0


@pytest.mark.parametrize("case", ["missing", "inactive", "other_household"])
def test_transfer_admin_target_not_found_is_404(
    db: FakeMembersDatabase, session: FakeMembersSession, case: str
) -> None:
    if case == "missing":
        target = UUID("dddddddd-0000-4000-8000-000000000004")
    elif case == "inactive":
        target = BETO_MEMBERSHIP
        _membership(db, BETO_MEMBERSHIP).estado = "inactivo"
    else:
        target = db.add_membership(OTRO_HOGAR, CARLA, fecha_ingreso=JOINED)

    _raises(
        404,
        CodigoError.NO_ENCONTRADO,
        service.transfer_admin,
        session,
        ADMIN,
        HOGAR,
        target,
        now=NOW,
    )
    assert "set_membership_role" not in db.names()
    assert session.commits == 0


def test_transfer_admin_by_non_admin_is_403(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _raises(
        403,
        CodigoError.NO_ES_ADMINISTRADOR,
        service.transfer_admin,
        session,
        BETO,
        HOGAR,
        ADMIN_MEMBERSHIP,
        now=NOW,
    )
    assert session.commits == 0


# --- crearInvitacion --------------------------------------------------------------------------


def test_create_invitation_normalizes_email_stores_only_hash_and_sends_link_before_commit(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    payload = InvitacionCrear.model_validate({"correo_invitado": "  Nueva.Persona@Example.COM "})

    result = service.create_invitation(session, settings, ADMIN, HOGAR, payload, now=NOW)  # type: ignore[arg-type]

    correo = "nueva.persona@example.com"
    assert isinstance(result, InvitacionPendiente)
    assert result.correo_invitado == correo
    assert result.estado == "pendiente"
    assert result.expira_en == NOW + timedelta(days=7)
    stored = db.committed.invitations[result.id]
    assert stored.correo_invitado == correo
    assert stored.invitado_por == ADMIN
    assert stored.created_at == NOW
    # S-02 a nivel de servicio: en la BD solo el hash; el enlace lleva el token que da ese hash.
    (sent,) = db.sent_emails
    assert sent.correo_invitado == correo
    assert sent.enlace.startswith(LINK_BASE)
    token = sent.enlace.removeprefix(LINK_BASE)
    assert len(token) >= 43
    assert stored.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token not in repr(db.committed)
    assert token not in result.model_dump_json()
    # Correo rellenado con la plantilla: quien invita y el hogar.
    assert "Ana Pérez" in sent.texto
    assert "Casa Pérez" in sent.texto
    assert sent.enlace in sent.texto
    assert db.events[: len(_guard_events())] == _guard_events()
    names = db.names()
    assert names.index("expire_stale_pending") < names.index("is_active_member_email")
    assert names.index("is_active_member_email") < names.index("has_pending_invitation")
    assert names.index("has_pending_invitation") < names.index("count_active_members")
    assert names.index("insert_invitation") < names.index("send_invitation_email")
    assert names.index("send_invitation_email") < names.index("commit")
    assert session.commits == 1
    for event in db.events:
        if event[0] in {"expire_stale_pending", "is_active_member_email", "has_pending_invitation"}:
            assert correo in event


def test_create_invitation_marks_stale_pending_first_dc42(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    stale = _pending_invitation(
        db, correo="Carla@Example.com", expira_en=NOW - timedelta(minutes=1)
    )
    payload = InvitacionCrear.model_validate({"correo_invitado": CORREO_CARLA})

    result = service.create_invitation(session, settings, ADMIN, HOGAR, payload, now=NOW)  # type: ignore[arg-type]

    assert db.committed.invitations[stale].estado == "expirada"
    assert db.committed.invitations[result.id].estado == "pendiente"


def test_create_invitation_for_active_member_email_is_409_ya_es_miembro(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    payload = InvitacionCrear.model_validate({"correo_invitado": "BETO@example.com"})

    _raises(
        409,
        CodigoError.YA_ES_MIEMBRO,
        service.create_invitation,
        session,
        settings,
        ADMIN,
        HOGAR,
        payload,
        now=NOW,
    )

    assert session.commits == 0
    assert db.sent_emails == []
    assert "insert_invitation" not in db.names()


def test_create_invitation_with_pending_is_409_invitacion_pendiente_existente(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    _pending_invitation(db)
    payload = InvitacionCrear.model_validate({"correo_invitado": "CARLA@example.com"})

    _raises(
        409,
        CodigoError.INVITACION_PENDIENTE_EXISTENTE,
        service.create_invitation,
        session,
        settings,
        ADMIN,
        HOGAR,
        payload,
        now=NOW,
    )
    assert session.commits == 0
    assert db.sent_emails == []


def test_create_invitation_limit_counts_active_plus_pending(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    db.add_membership(HOGAR, CARLA, fecha_ingreso=JOINED)  # 3 activos
    _pending_invitation(db, correo="uno@example.com")
    _pending_invitation(db, correo="dos@example.com")  # + 2 pendientes = 5
    payload = InvitacionCrear.model_validate({"correo_invitado": "tres@example.com"})

    _raises(
        409,
        CodigoError.LIMITE_MIEMBROS,
        service.create_invitation,
        session,
        settings,
        ADMIN,
        HOGAR,
        payload,
        now=NOW,
    )
    assert session.commits == 0
    assert "insert_invitation" not in db.names()


def test_create_invitation_four_in_total_is_still_allowed(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    _pending_invitation(db, correo="uno@example.com")
    _pending_invitation(db, correo="dos@example.com")  # 2 activos + 2 pendientes = 4
    _pending_invitation(db, correo="vieja@example.com", expira_en=NOW - SECOND)  # vencida
    payload = InvitacionCrear.model_validate({"correo_invitado": "tres@example.com"})

    service.create_invitation(session, settings, ADMIN, HOGAR, payload, now=NOW)  # type: ignore[arg-type]
    assert session.commits == 1


def test_create_invitation_unique_index_race_is_409(
    db: FakeMembersDatabase,
    session: FakeMembersSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def insert_invitation(*_args: Any, **_kwargs: Any) -> Any:
        raise invitations_data.PendingInvitationExistsError("pendiente existente")

    monkeypatch.setattr(invitations_data, "insert_invitation", insert_invitation)
    payload = InvitacionCrear.model_validate({"correo_invitado": CORREO_CARLA})

    _raises(
        409,
        CodigoError.INVITACION_PENDIENTE_EXISTENTE,
        service.create_invitation,
        session,
        settings,
        ADMIN,
        HOGAR,
        payload,
        now=NOW,
    )
    assert session.commits == 0
    assert db.sent_emails == []


def test_create_invitation_email_failure_rolls_back_and_propagates(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    db.email_error = EmailDeliveryError(
        "No se pudo enviar el correo de invitación (SMTPException)."
    )
    payload = InvitacionCrear.model_validate({"correo_invitado": CORREO_CARLA})

    with pytest.raises(EmailDeliveryError):
        service.create_invitation(session, settings, ADMIN, HOGAR, payload, now=NOW)  # type: ignore[arg-type]

    assert session.commits == 0
    assert session.rollbacks == 1
    assert db.committed.invitations == {}


def test_create_invitation_by_non_admin_is_403_before_reading_email(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    payload = InvitacionCrear.model_validate({"correo_invitado": CORREO_CARLA})

    _raises(
        403,
        CodigoError.NO_ES_ADMINISTRADOR,
        service.create_invitation,
        session,
        settings,
        BETO,
        HOGAR,
        payload,
        now=NOW,
    )
    assert db.events == _guard_events(BETO)


def test_create_invitation_without_smtp_logs_only_the_link(
    db: FakeMembersDatabase,
    session: FakeMembersSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Envío real en modo local (DC-04): sin host, usuario, clave ni remitente.
    monkeypatch.setattr(email_service, "send_invitation_email", REAL_SEND_INVITATION_EMAIL)
    settings = Settings.model_construct(
        invitation_link_base=LINK_BASE,
        smtp_host=None,
        smtp_user=None,
        smtp_password=None,
        smtp_sender=None,
    )
    payload = InvitacionCrear.model_validate({"correo_invitado": CORREO_CARLA})

    with caplog.at_level(logging.DEBUG):
        result = service.create_invitation(session, settings, ADMIN, HOGAR, payload, now=NOW)  # type: ignore[arg-type]

    stored = db.committed.invitations[result.id]
    logged = "\n".join(record.getMessage() for record in caplog.records)
    links = [word for word in logged.split() if word.startswith(LINK_BASE)]
    assert len(links) == 1
    token = links[0].removeprefix(LINK_BASE)
    assert hashlib.sha256(token.encode("utf-8")).hexdigest() == stored.token_hash
    for secret in (CORREO_CARLA, stored.token_hash, str(ADMIN), str(HOGAR), str(result.id)):
        assert secret not in logged


# --- revocarInvitacion ------------------------------------------------------------------------


def test_revoke_invitation_sets_revocada_and_commits(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)

    service.revoke_invitation(session, ADMIN, HOGAR, invitation, now=NOW)  # type: ignore[arg-type]

    assert db.events == [
        *_guard_events(),
        ("get_invitation", invitation, True),
        ("set_invitation_state", invitation, "revocada", None),
        ("commit",),
    ]
    assert db.committed.invitations[invitation].estado == "revocada"


@pytest.mark.parametrize("case", ["missing", "other_household"])
def test_revoke_invitation_not_found_is_404(
    db: FakeMembersDatabase, session: FakeMembersSession, case: str
) -> None:
    invitation = (
        UUID("eeeeeeee-0000-4000-8000-000000000005")
        if case == "missing"
        else _pending_invitation(db, hogar_id=OTRO_HOGAR)
    )
    _raises(
        404,
        CodigoError.NO_ENCONTRADO,
        service.revoke_invitation,
        session,
        ADMIN,
        HOGAR,
        invitation,
        now=NOW,
    )
    assert session.commits == 0
    assert "set_invitation_state" not in db.names()


def test_revoke_invitation_not_pending_is_409(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db, estado="aceptada")
    _raises(
        409,
        CodigoError.INVITACION_NO_PENDIENTE,
        service.revoke_invitation,
        session,
        ADMIN,
        HOGAR,
        invitation,
        now=NOW,
    )
    assert session.commits == 0


def test_revoke_invitation_expired_is_marked_then_409(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db, expira_en=NOW - SECOND)  # expira_en < now: vencida

    _raises(
        409,
        CodigoError.INVITACION_EXPIRADA,
        service.revoke_invitation,
        session,
        ADMIN,
        HOGAR,
        invitation,
        now=NOW,
    )

    assert db.events[-2:] == [
        ("set_invitation_state", invitation, "expirada", None),
        ("commit",),
    ]
    assert db.committed.invitations[invitation].estado == "expirada"


def test_revoke_invitation_by_non_admin_is_403(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    _raises(
        403,
        CodigoError.NO_ES_ADMINISTRADOR,
        service.revoke_invitation,
        session,
        BETO,
        HOGAR,
        invitation,
        now=NOW,
    )
    assert "get_invitation" not in db.names()


# --- listarInvitacionesRecibidas --------------------------------------------------------------


def test_list_received_invitations_marks_expired_and_returns_pending(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    first = _pending_invitation(db, correo="Carla@Example.com", created_at=NOW - timedelta(days=2))
    stale = _pending_invitation(db, hogar_id=OTRO_HOGAR, expira_en=NOW - timedelta(days=1))
    # Quien invitó eliminó su cuenta (invitado_por nulo): el nombre es el del administrador actual.
    orphan = _pending_invitation(db, invitado_por=None, created_at=NOW - timedelta(days=1))

    result = service.list_received_invitations(session, CARLA, CORREO_CARLA, now=NOW)  # type: ignore[arg-type]

    assert isinstance(result, InvitacionesRecibidasLista)
    assert [i.id for i in result.invitaciones] == [orphan, first]
    assert {i.invitado_por_nombre for i in result.invitaciones} == {"Ana Pérez"}
    assert result.invitaciones[0].hogar_nombre == "Casa Pérez"
    assert db.committed.invitations[stale].estado == "expirada"
    assert db.events == [
        ("expire_stale_pending_for_email", CORREO_CARLA, NOW),
        ("list_received_invitations", CORREO_CARLA, NOW),
        ("commit",),
    ]


def test_list_received_invitations_without_inviter_name_is_skipped_with_warning(
    db: FakeMembersDatabase, session: FakeMembersSession, caplog: pytest.LogCaptureFixture
) -> None:
    # Otra casa no tiene miembros con ficha y quien invitó eliminó su cuenta: sin nombre.
    nameless = _pending_invitation(db, hogar_id=OTRO_HOGAR, invitado_por=None)
    visible = _pending_invitation(db)

    with caplog.at_level(logging.WARNING, logger=service.logger.name):
        result = service.list_received_invitations(session, CARLA, CORREO_CARLA, now=NOW)  # type: ignore[arg-type]

    assert [i.id for i in result.invitaciones] == [visible]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    for secret in (str(nameless), str(OTRO_HOGAR), str(CARLA), CORREO_CARLA):
        assert secret not in message
    assert session.commits == 1


def test_list_received_invitations_empty(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    result = service.list_received_invitations(session, BETO, CORREO_BETO, now=NOW)  # type: ignore[arg-type]
    assert result.invitaciones == []


# --- resolverTokenInvitacion ------------------------------------------------------------------


TOKEN = "token-del-enlace_abc123"
TOKEN_HASH = hashlib.sha256(TOKEN.encode("utf-8")).hexdigest()


def test_resolve_invitation_token_returns_invitation_by_hash(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db, token_hash=TOKEN_HASH)

    result = service.resolve_invitation_token(  # type: ignore[arg-type]
        session, CARLA, "CARLA@example.com", InvitacionToken(token=TOKEN), now=NOW
    )

    assert result == InvitacionRecibida(
        id=invitation,
        hogar_nombre="Casa Pérez",
        invitado_por_nombre="Ana Pérez",
        expira_en=NOW + timedelta(days=3),
    )
    assert db.events[0] == ("get_invitation_by_token_hash", TOKEN_HASH)
    assert TOKEN not in repr(db.events)
    assert session.commits == 0


def test_resolve_invitation_token_unknown_is_404(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _pending_invitation(db, token_hash=TOKEN_HASH)
    _raises(
        404,
        CodigoError.NO_ENCONTRADO,
        service.resolve_invitation_token,
        session,
        CARLA,
        CORREO_CARLA,
        InvitacionToken(token="otro"),
        now=NOW,
    )


def test_resolve_invitation_token_other_email_is_403(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _pending_invitation(db, token_hash=TOKEN_HASH, estado="aceptada")  # 403 antes que 409
    _raises(
        403,
        CodigoError.CORREO_NO_COINCIDE,
        service.resolve_invitation_token,
        session,
        BETO,
        CORREO_BETO,
        InvitacionToken(token=TOKEN),
        now=NOW,
    )


def test_resolve_invitation_token_not_pending_is_409(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    _pending_invitation(
        db, token_hash=TOKEN_HASH, estado="revocada", expira_en=NOW - timedelta(days=1)
    )
    _raises(
        409,
        CodigoError.INVITACION_NO_PENDIENTE,
        service.resolve_invitation_token,
        session,
        CARLA,
        CORREO_CARLA,
        InvitacionToken(token=TOKEN),
        now=NOW,
    )
    assert session.commits == 0


def test_resolve_invitation_token_expired_is_marked_then_409(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(
        db, token_hash=TOKEN_HASH, expira_en=NOW - timedelta(seconds=1)
    )
    _raises(
        409,
        CodigoError.INVITACION_EXPIRADA,
        service.resolve_invitation_token,
        session,
        CARLA,
        CORREO_CARLA,
        InvitacionToken(token=TOKEN),
        now=NOW,
    )
    assert db.committed.invitations[invitation].estado == "expirada"
    assert session.commits == 1


# --- rechazarInvitacion -----------------------------------------------------------------------


def test_reject_invitation_sets_rechazada_with_respondida_en(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)

    service.reject_invitation(session, CARLA, CORREO_CARLA, invitation, now=NOW)  # type: ignore[arg-type]

    assert db.events == [
        ("get_invitation", invitation, False),
        ("get_invitation", invitation, True),
        ("set_invitation_state", invitation, "rechazada", NOW),
        ("commit",),
    ]
    stored = db.committed.invitations[invitation]
    assert (stored.estado, stored.respondida_en) == ("rechazada", NOW)


def test_reject_invitation_errors_in_order(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    missing = UUID("eeeeeeee-0000-4000-8000-000000000005")
    _raises(
        404,
        CodigoError.NO_ENCONTRADO,
        service.reject_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        missing,
        now=NOW,
    )

    accepted = _pending_invitation(db, estado="aceptada")
    db.events.clear()
    _raises(
        403,
        CodigoError.CORREO_NO_COINCIDE,
        service.reject_invitation,
        session,
        BETO,
        CORREO_BETO,
        accepted,
        now=NOW,
    )
    assert db.events == [("get_invitation", accepted, False)]  # sin bloquear antes del 403

    _raises(
        409,
        CodigoError.INVITACION_NO_PENDIENTE,
        service.reject_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        accepted,
        now=NOW,
    )
    assert session.commits == 0


def test_reject_invitation_expired_is_marked_then_409(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db, expira_en=NOW - SECOND)
    _raises(
        409,
        CodigoError.INVITACION_EXPIRADA,
        service.reject_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        invitation,
        now=NOW,
    )
    assert db.committed.invitations[invitation].estado == "expirada"
    assert session.commits == 1


# --- frontera de vencimiento (RN-X-05: vencida ⇔ expira_en < now) -----------------------------


def test_invitation_expiring_exactly_now_is_still_valid_everywhere(
    db: FakeMembersDatabase, settings: Settings
) -> None:
    for_resolve = _pending_invitation(db, token_hash=TOKEN_HASH, expira_en=NOW)
    for_revoke = _pending_invitation(db, correo="revocar@example.com", expira_en=NOW)
    dora = UUID("dddddddd-0000-4000-8000-000000000004")
    db.add_user(dora, "Dora", "dora@example.com")
    for_reject = _pending_invitation(db, correo="dora@example.com", expira_en=NOW)

    received = service.list_received_invitations(db.session(), CARLA, CORREO_CARLA, now=NOW)  # type: ignore[arg-type]
    assert [i.id for i in received.invitaciones] == [for_resolve]

    resolved = service.resolve_invitation_token(  # type: ignore[arg-type]
        db.session(), CARLA, CORREO_CARLA, InvitacionToken(token=TOKEN), now=NOW
    )
    assert resolved.id == for_resolve

    service.revoke_invitation(db.session(), ADMIN, HOGAR, for_revoke, now=NOW)  # type: ignore[arg-type]
    assert db.committed.invitations[for_revoke].estado == "revocada"

    service.reject_invitation(db.session(), dora, "dora@example.com", for_reject, now=NOW)  # type: ignore[arg-type]
    assert db.committed.invitations[for_reject].estado == "rechazada"

    accepted = service.accept_invitation(db.session(), CARLA, CORREO_CARLA, for_resolve, now=NOW)  # type: ignore[arg-type]
    assert accepted.hogar_id == HOGAR
    assert db.committed.invitations[for_resolve].estado == "aceptada"


def test_create_invitation_counts_a_pending_expiring_exactly_now(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    db.add_membership(HOGAR, CARLA, fecha_ingreso=JOINED)  # 3 activos
    _pending_invitation(db, correo="uno@example.com")
    _pending_invitation(db, correo="frontera@example.com", expira_en=NOW)  # vigente: cuenta
    payload = InvitacionCrear.model_validate({"correo_invitado": "tres@example.com"})

    _raises(
        409,
        CodigoError.LIMITE_MIEMBROS,
        service.create_invitation,
        session,
        settings,
        ADMIN,
        HOGAR,
        payload,
        now=NOW,
    )


def test_create_invitation_with_pending_expiring_exactly_now_is_409_pending_exists(
    db: FakeMembersDatabase, session: FakeMembersSession, settings: Settings
) -> None:
    frontera = _pending_invitation(db, expira_en=NOW)
    payload = InvitacionCrear.model_validate({"correo_invitado": CORREO_CARLA})

    _raises(
        409,
        CodigoError.INVITACION_PENDIENTE_EXISTENTE,
        service.create_invitation,
        session,
        settings,
        ADMIN,
        HOGAR,
        payload,
        now=NOW,
    )
    assert db.committed.invitations[frontera].estado == "pendiente"  # no se marcó expirada


# --- aceptarInvitacion ------------------------------------------------------------------------


def _new_member_alert(db: FakeMembersDatabase) -> tuple[UUID, dict[str, Any]]:
    ((alerta_id, alert),) = db.committed.alerts.items()
    return alerta_id, alert


def _delivered_to(db: FakeMembersDatabase, alerta_id: UUID) -> set[UUID]:
    return {usuario for alerta, usuario in db.committed.deliveries if alerta == alerta_id}


def test_accept_invitation_creates_membership_and_new_member_alert(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)

    result = service.accept_invitation(session, CARLA, "Carla@Example.com", invitation, now=NOW)  # type: ignore[arg-type]

    assert isinstance(result, MembresiaResumen)
    assert (result.hogar_id, result.rol) == (HOGAR, "miembro")
    membership = _membership(db, result.membresia_id)
    assert (membership.usuario_id, membership.estado, membership.fecha_ingreso) == (
        CARLA,
        "activo",
        NOW,
    )
    stored = db.committed.invitations[invitation]
    assert (stored.estado, stored.respondida_en) == ("aceptada", NOW)
    alerta_id, alert = _new_member_alert(db)
    assert alert["clave_evento"] == f"nuevo_miembro:{result.membresia_id}"
    assert alert["regla_origen"] == "nuevo_miembro"
    assert (alert["categoria"], alert["severidad"]) == ("informacion", "informativa")
    assert alert["titulo"] == "Carla Díaz se unió al hogar"
    assert alert["mensaje"] == "Carla Díaz ya forma parte de Casa Pérez."
    assert alert["zona_id"] is None
    assert alert["created_at"] == NOW
    # Para los demás: el nuevo miembro no recibe su propio aviso.
    assert _delivered_to(db, alerta_id) == {ADMIN, BETO}
    assert session.commits == 1
    names = db.names()
    assert names.index("insert_alert_deliveries") < names.index("commit")


def test_accept_invitation_order_of_checks_and_locks(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)

    result = service.accept_invitation(session, CARLA, CORREO_CARLA, invitation, now=NOW)  # type: ignore[arg-type]

    assert db.events[:8] == [
        ("get_invitation", invitation, False),
        ("lock_household", HOGAR),
        ("get_invitation", invitation, True),
        ("lock_user_profile", CARLA),
        ("get_active_membership_of_user", CARLA, False),
        ("count_active_members", HOGAR),
        ("insert_member_membership", HOGAR, CARLA, NOW),
        ("set_invitation_state", invitation, "aceptada", NOW),
    ]
    names = db.names()
    # Orden único de bloqueo: hogar antes que la ficha del usuario.
    assert names.index("lock_household") < names.index("lock_user_profile")
    assert ("insert_alert", HOGAR, f"nuevo_miembro:{result.membresia_id}") in db.events
    assert names[-1] == "commit"


def test_accept_invitation_recipients_respect_permission_switch_and_join_date(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    db.committed.households[HOGAR] = replace(
        db.committed.households[HOGAR], permiso_recibir_alertas=False
    )
    late = UUID("ffffffff-0000-4000-8000-000000000006")
    db.add_user(late, "Tardío", "tardio@example.com")
    db.add_membership(HOGAR, late, fecha_ingreso=NOW + timedelta(seconds=1))

    service.accept_invitation(session, CARLA, CORREO_CARLA, invitation, now=NOW)  # type: ignore[arg-type]

    alerta_id, _ = _new_member_alert(db)
    # Sin permiso del hogar solo el administrador; quien ingresó después no recibe el aviso.
    assert _delivered_to(db, alerta_id) == {ADMIN}


def test_accept_invitation_switch_off_is_excluded(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    profile = db.committed.profiles[BETO]
    db.committed.profiles[BETO] = replace(
        profile, preferencias=replace(profile.preferencias, notif_consumo=False)
    )

    service.accept_invitation(session, CARLA, CORREO_CARLA, invitation, now=NOW)  # type: ignore[arg-type]

    alerta_id, _ = _new_member_alert(db)
    assert _delivered_to(db, alerta_id) == {ADMIN}


def test_accept_invitation_existing_alert_key_creates_no_deliveries(
    db: FakeMembersDatabase, session: FakeMembersSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    invitation = _pending_invitation(db)
    monkeypatch.setattr(alerts_data, "insert_alert", lambda *_a, **_k: None)

    service.accept_invitation(session, CARLA, CORREO_CARLA, invitation, now=NOW)  # type: ignore[arg-type]

    assert "insert_alert_deliveries" not in db.names()
    assert session.commits == 1


def test_accept_invitation_unknown_is_404(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    missing = UUID("eeeeeeee-0000-4000-8000-000000000005")
    _raises(
        404,
        CodigoError.NO_ENCONTRADO,
        service.accept_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        missing,
        now=NOW,
    )
    assert "lock_household" not in db.names()


def test_accept_invitation_other_email_is_403_without_locks(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    _raises(
        403,
        CodigoError.CORREO_NO_COINCIDE,
        service.accept_invitation,
        session,
        BETO,
        CORREO_BETO,
        invitation,
        now=NOW,
    )
    assert db.events == [("get_invitation", invitation, False)]
    assert session.commits == 0


def test_accept_invitation_not_pending_is_409(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db, estado="revocada")
    _raises(
        409,
        CodigoError.INVITACION_NO_PENDIENTE,
        service.accept_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        invitation,
        now=NOW,
    )
    assert session.commits == 0
    assert "lock_user_profile" not in db.names()


def test_accept_invitation_expired_is_marked_then_409(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db, expira_en=NOW - SECOND)

    _raises(
        409,
        CodigoError.INVITACION_EXPIRADA,
        service.accept_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        invitation,
        now=NOW,
    )

    assert db.events[-2:] == [
        ("set_invitation_state", invitation, "expirada", None),
        ("commit",),
    ]
    assert db.committed.invitations[invitation].estado == "expirada"
    assert db.active_memberships_of(CARLA) == []


def test_accept_invitation_without_profile_is_404_no_encontrado(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    del db.committed.profiles[CARLA]

    _raises(
        404,
        CodigoError.NO_ENCONTRADO,
        service.accept_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        invitation,
        now=NOW,
    )
    assert session.commits == 0
    # El 404 sale del paso 3 (ficha bloqueada), después del bloqueo del hogar.
    assert ("lock_user_profile", CARLA) in db.events
    assert "insert_member_membership" not in db.names()


def test_accept_invitation_with_active_membership_is_409(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    db.add_membership(OTRO_HOGAR, CARLA, "administrador", fecha_ingreso=JOINED)

    _raises(
        409,
        CodigoError.MEMBRESIA_ACTIVA_EXISTENTE,
        service.accept_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        invitation,
        now=NOW,
    )
    assert session.commits == 0


def test_accept_invitation_unique_index_race_is_409(
    db: FakeMembersDatabase, session: FakeMembersSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    invitation = _pending_invitation(db)

    def insert_member_membership(*_args: Any, **_kwargs: Any) -> UUID:
        raise memberships_data.ActiveMembershipExistsError("El usuario ya tiene un hogar activo.")

    monkeypatch.setattr(memberships_data, "insert_member_membership", insert_member_membership)

    _raises(
        409,
        CodigoError.MEMBRESIA_ACTIVA_EXISTENTE,
        service.accept_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        invitation,
        now=NOW,
    )
    assert session.commits == 0


def test_accept_invitation_with_five_active_is_409_limite(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    for index in range(3):
        usuario = UUID(f"0000000{index}-0000-4000-8000-000000000000")
        db.add_user(usuario, f"Persona {index}", f"p{index}@example.com")
        db.add_membership(HOGAR, usuario, fecha_ingreso=JOINED)

    _raises(
        409,
        CodigoError.LIMITE_MIEMBROS,
        service.accept_invitation,
        session,
        CARLA,
        CORREO_CARLA,
        invitation,
        now=NOW,
    )
    assert session.commits == 0


def test_accept_invitation_limit_counts_only_active_members(
    db: FakeMembersDatabase, session: FakeMembersSession
) -> None:
    invitation = _pending_invitation(db)
    for index in range(2):  # 4 activos + otras pendientes: al aceptar solo cuentan los activos
        usuario = UUID(f"0000000{index}-0000-4000-8000-000000000000")
        db.add_user(usuario, f"Persona {index}", f"p{index}@example.com")
        db.add_membership(HOGAR, usuario, fecha_ingreso=JOINED)
    _pending_invitation(db, correo="x@example.com")
    _pending_invitation(db, correo="y@example.com")

    service.accept_invitation(session, CARLA, CORREO_CARLA, invitation, now=NOW)  # type: ignore[arg-type]
    assert session.commits == 1


def test_accept_invitation_alert_failure_propagates_without_commit(
    db: FakeMembersDatabase, session: FakeMembersSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    invitation = _pending_invitation(db)

    def insert_alert(*_args: Any, **_kwargs: Any) -> UUID:
        raise RuntimeError("fallo al crear la alerta")

    monkeypatch.setattr(alerts_data, "insert_alert", insert_alert)

    with pytest.raises(RuntimeError):
        service.accept_invitation(session, CARLA, CORREO_CARLA, invitation, now=NOW)  # type: ignore[arg-type]

    assert session.commits == 0
    assert db.active_memberships_of(CARLA) == []
    assert db.committed.invitations[invitation].estado == "pendiente"
