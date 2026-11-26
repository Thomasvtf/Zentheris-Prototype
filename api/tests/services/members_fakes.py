"""Doble en memoria de `app.data` para miembros, invitaciones y la baja de la cuenta (fase 9).

`FakeMembersDatabase` guarda las tablas CONFIRMADAS (`committed`). Cada `FakeMembersSession` lee
lo confirmado hasta su primera escritura; desde ahí trabaja sobre una copia propia (`work`) que
`commit()` confirma y `rollback()` descarta (lectura confirmada simplificada: una sesión ve los
commits de otra mientras no haya escrito). Así se puede simular otra transacción que confirma
«mientras se espera un bloqueo» con un gancho (`db.hooks[nombre]`), que se ejecuta una sola vez
justo antes de la función de datos con ese nombre.

Cada llamada a datos, `commit`, `rollback` y Supabase queda en `db.events` en orden, con sus
argumentos clave, para comprobar el orden de comprobaciones y de bloqueo (hogar → membresía →
usuario). Las funciones imitan las sentencias: filtros por hogar (R-01), `lower()` en los
correos, vencida ⇔ `expira_en < now` (RN-X-05), `ON CONFLICT (clave_evento) DO NOTHING`, la verificación miembros_activo_con_usuario al
borrar la ficha y el índice único de membresía activa por usuario. No demuestra compatibilidad
con PostgreSQL.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.data import alerts as alerts_data
from app.data import households as households_data
from app.data import invitations as invitations_data
from app.data import memberships as memberships_data
from app.data import users as users_data
from app.data.households import PERMISSION_COLUMNS, HouseholdRow
from app.data.invitations import InvitationRow, PendingInvitationExistsError, ReceivedInvitationRow
from app.data.memberships import (
    ActiveMembershipExistsError,
    AlertMemberRow,
    MemberRow,
    MembershipRow,
    MembershipSummaryRow,
)
from app.data.users import PreferencesRow, UserProfileRow
from app.services import email as email_service
from app.services import supabase_admin

DEFAULT_PREFERENCES = PreferencesRow(
    notif_consumo=True, notif_consejos=True, base_comparacion="promedio"
)


@dataclass
class FakeMembership:
    membresia_id: UUID
    hogar_id: UUID
    usuario_id: UUID | None
    rol: str
    estado: str
    fecha_ingreso: datetime
    fecha_salida: datetime | None = None


@dataclass
class FakeInvitation:
    id: UUID
    hogar_id: UUID
    correo_invitado: str
    invitado_por: UUID | None
    estado: str
    expira_en: datetime
    created_at: datetime
    token_hash: str
    respondida_en: datetime | None = None


@dataclass
class Tables:
    households: dict[UUID, HouseholdRow] = field(default_factory=dict)
    profiles: dict[UUID, UserProfileRow] = field(default_factory=dict)
    memberships: dict[UUID, FakeMembership] = field(default_factory=dict)
    invitations: dict[UUID, FakeInvitation] = field(default_factory=dict)
    alerts: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    deliveries: list[tuple[UUID, UUID]] = field(default_factory=list)


@dataclass
class SentEmail:
    correo_invitado: str
    asunto: str
    texto: str
    html: str
    enlace: str


class FakeMembersSession:
    """Sesión con commit, rollback y copia de trabajo perezosa. No ejecuta SQL."""

    def __init__(self, db: FakeMembersDatabase, name: str = "A") -> None:
        self.db = db
        self.name = name
        self.work: Tables | None = None
        self.commits = 0
        self.rollbacks = 0

    def read(self) -> Tables:
        return self.work if self.work is not None else self.db.committed

    def write(self) -> Tables:
        if self.work is None:
            self.work = copy.deepcopy(self.db.committed)
        return self.work

    def commit(self) -> None:
        self.commits += 1
        self.db.events.append(("commit",))
        if self.work is not None:
            self.db.committed = self.work
            self.work = None

    def rollback(self) -> None:
        self.rollbacks += 1
        self.db.events.append(("rollback",))
        self.work = None

    def exec(self, *_args: Any, **_kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("el servicio no debe ejecutar SQL directamente")


@dataclass
class FakeMembersDatabase:
    committed: Tables = field(default_factory=Tables)
    auth_emails: dict[UUID, str] = field(default_factory=dict)
    events: list[tuple[Any, ...]] = field(default_factory=list)
    hooks: dict[str, Callable[[], None]] = field(default_factory=dict)
    sent_emails: list[SentEmail] = field(default_factory=list)
    email_error: Exception | None = None
    auth_error: Exception | None = None

    # --- utilidades de las pruebas ---------------------------------------------------------
    def session(self, name: str = "A") -> FakeMembersSession:
        return FakeMembersSession(self, name)

    def names(self) -> list[str]:
        return [event[0] for event in self.events]

    def add_household(
        self, hogar_id: UUID, nombre: str = "Casa Pérez", *, recibir_alertas: bool = True
    ) -> HouseholdRow:
        row = HouseholdRow(
            id=hogar_id,
            nombre=nombre,
            tipo_vivienda="apartamento",
            permiso_ver_consumo_actual=True,
            permiso_ver_historial=True,
            permiso_recibir_alertas=recibir_alertas,
            permiso_modificar_metas=False,
        )
        self.committed.households[hogar_id] = row
        return row

    def add_user(
        self,
        usuario_id: UUID,
        nombre: str,
        correo: str,
        *,
        notif_consumo: bool = True,
        with_profile: bool = True,
    ) -> None:
        self.auth_emails[usuario_id] = correo
        if with_profile:
            self.committed.profiles[usuario_id] = UserProfileRow(
                id=usuario_id,
                nombre_completo=nombre,
                telefono=None,
                avatar_url=None,
                preferencias=replace(DEFAULT_PREFERENCES, notif_consumo=notif_consumo),
            )

    def add_membership(
        self,
        hogar_id: UUID,
        usuario_id: UUID | None,
        rol: str = "miembro",
        *,
        estado: str = "activo",
        fecha_ingreso: datetime,
        membresia_id: UUID | None = None,
    ) -> UUID:
        membresia_id = membresia_id or uuid4()
        self.committed.memberships[membresia_id] = FakeMembership(
            membresia_id, hogar_id, usuario_id, rol, estado, fecha_ingreso
        )
        return membresia_id

    def add_invitation(
        self,
        hogar_id: UUID,
        correo: str,
        *,
        invitado_por: UUID | None,
        expira_en: datetime,
        estado: str = "pendiente",
        token_hash: str | None = None,
        created_at: datetime | None = None,
        invitacion_id: UUID | None = None,
    ) -> UUID:
        invitacion_id = invitacion_id or uuid4()
        self.committed.invitations[invitacion_id] = FakeInvitation(
            id=invitacion_id,
            hogar_id=hogar_id,
            correo_invitado=correo,
            invitado_por=invitado_por,
            estado=estado,
            expira_en=expira_en,
            created_at=created_at or expira_en - timedelta(days=7),
            token_hash=token_hash or uuid4().hex,
        )
        return invitacion_id

    def active_memberships_of(self, usuario_id: UUID) -> list[FakeMembership]:
        return [
            m
            for m in self.committed.memberships.values()
            if m.usuario_id == usuario_id and m.estado == "activo"
        ]

    def _hook(self, name: str) -> None:
        hook = self.hooks.pop(name, None)
        if hook is not None:
            hook()


def _tables(session: Any) -> Tables:
    return session.read()


def _invitation_row(inv: FakeInvitation) -> InvitationRow:
    return InvitationRow(
        id=inv.id,
        hogar_id=inv.hogar_id,
        correo_invitado=inv.correo_invitado,
        invitado_por=inv.invitado_por,
        estado=inv.estado,  # type: ignore[arg-type]
        expira_en=inv.expira_en,
        respondida_en=inv.respondida_en,
        created_at=inv.created_at,
    )


def _membership_row(m: FakeMembership) -> MembershipRow:
    return MembershipRow(
        membresia_id=m.membresia_id,
        hogar_id=m.hogar_id,
        usuario_id=m.usuario_id,
        rol=m.rol,  # type: ignore[arg-type]
        estado=m.estado,  # type: ignore[arg-type]
    )


def _active(tables: Tables, hogar_id: UUID) -> list[FakeMembership]:
    return [
        m for m in tables.memberships.values() if m.hogar_id == hogar_id and m.estado == "activo"
    ]


def _received_row(tables: Tables, inv: FakeInvitation) -> ReceivedInvitationRow:
    inviter = tables.profiles.get(inv.invitado_por) if inv.invitado_por else None
    name = inviter.nombre_completo if inviter else None
    if name is None:
        admins = [m for m in _active(tables, inv.hogar_id) if m.rol == "administrador"]
        if admins and admins[0].usuario_id in tables.profiles:
            name = tables.profiles[admins[0].usuario_id].nombre_completo  # type: ignore[index]
    return ReceivedInvitationRow(
        id=inv.id,
        hogar_id=inv.hogar_id,
        hogar_nombre=tables.households[inv.hogar_id].nombre,
        invitado_por_nombre=name,
        expira_en=inv.expira_en,
    )


def install_fake_members_database(monkeypatch: pytest.MonkeyPatch, db: FakeMembersDatabase) -> None:
    """Sustituye en `app.data.*`, `supabase_admin` y `services.email` lo que usan estos casos."""
    ev = db.events

    # --- hogares --------------------------------------------------------------------------
    def lock_household(session: Any, hogar_id: UUID) -> None:
        db._hook("lock_household")
        ev.append(("lock_household", hogar_id))

    def get_household(session: Any, hogar_id: UUID) -> HouseholdRow | None:
        ev.append(("get_household", hogar_id))
        return _tables(session).households.get(hogar_id)

    def update_permissions(session: Any, hogar_id: UUID, changes: dict[str, bool]) -> Any:
        ev.append(("update_permissions", hogar_id, dict(changes)))
        if not changes or set(changes) - set(PERMISSION_COLUMNS):
            raise ValueError("cambios inválidos")
        tables = session.write()
        row = tables.households.get(hogar_id)
        if row is None:
            return None
        updated = replace(row, **{PERMISSION_COLUMNS[k]: v for k, v in changes.items()})
        tables.households[hogar_id] = updated
        return updated

    def delete_household(session: Any, hogar_id: UUID) -> None:
        ev.append(("delete_household", hogar_id))
        tables = session.write()
        tables.households.pop(hogar_id, None)
        for key in [k for k, m in tables.memberships.items() if m.hogar_id == hogar_id]:
            del tables.memberships[key]
        for key in [k for k, i in tables.invitations.items() if i.hogar_id == hogar_id]:
            del tables.invitations[key]

    # --- membresías -----------------------------------------------------------------------
    def get_active_membership_of_user(
        session: Any, usuario_id: UUID, *, for_update: bool = False
    ) -> MembershipSummaryRow | None:
        db._hook("get_active_membership_of_user")
        ev.append(("get_active_membership_of_user", usuario_id, for_update))
        for m in _tables(session).memberships.values():
            if m.usuario_id == usuario_id and m.estado == "activo":
                return MembershipSummaryRow(m.membresia_id, m.hogar_id, m.rol)  # type: ignore[arg-type]
        return None

    def count_other_active_members(session: Any, hogar_id: UUID, usuario_id: UUID) -> int:
        ev.append(("count_other_active_members", hogar_id, usuario_id))
        return sum(1 for m in _active(_tables(session), hogar_id) if m.usuario_id != usuario_id)

    def close_membership(session: Any, membresia_id: UUID, closed_at: datetime) -> None:
        ev.append(("close_membership", membresia_id, closed_at))
        m = session.write().memberships[membresia_id]
        m.estado = "inactivo"
        m.fecha_salida = closed_at

    def list_active_members(session: Any, hogar_id: UUID) -> list[MemberRow]:
        ev.append(("list_active_members", hogar_id))
        tables = _tables(session)
        rows = sorted(
            _active(tables, hogar_id),
            key=lambda m: (m.rol != "administrador", m.fecha_ingreso, str(m.membresia_id)),
        )
        return [
            MemberRow(
                membresia_id=m.membresia_id,
                usuario_id=m.usuario_id,  # type: ignore[arg-type]
                nombre_completo=tables.profiles[m.usuario_id].nombre_completo,  # type: ignore[index]
                avatar_url=tables.profiles[m.usuario_id].avatar_url,  # type: ignore[index]
                rol=m.rol,  # type: ignore[arg-type]
                fecha_ingreso=m.fecha_ingreso,
            )
            for m in rows
        ]

    def count_active_members(session: Any, hogar_id: UUID) -> int:
        ev.append(("count_active_members", hogar_id))
        return len(_active(_tables(session), hogar_id))

    def get_household_membership(
        session: Any, hogar_id: UUID, membresia_id: UUID, *, for_update: bool = False
    ) -> MembershipRow | None:
        ev.append(("get_household_membership", hogar_id, membresia_id, for_update))
        m = _tables(session).memberships.get(membresia_id)
        return None if m is None or m.hogar_id != hogar_id else _membership_row(m)

    def get_user_membership_in_household(
        session: Any, hogar_id: UUID, usuario_id: UUID, *, for_update: bool = False
    ) -> MembershipRow | None:
        ev.append(("get_user_membership_in_household", hogar_id, usuario_id, for_update))
        for m in _active(_tables(session), hogar_id):
            if m.usuario_id == usuario_id:
                return _membership_row(m)
        return None

    def set_membership_role(session: Any, membresia_id: UUID, rol: str) -> None:
        ev.append(("set_membership_role", membresia_id, rol))
        tables = session.write()
        m = tables.memberships[membresia_id]
        if rol == "administrador" and any(
            o.rol == "administrador" and o.membresia_id != membresia_id
            for o in _active(tables, m.hogar_id)
        ):
            raise AssertionError("uq_miembros_admin_activo: ya hay un administrador activo")
        m.rol = rol

    def insert_member_membership(
        session: Any, *, hogar_id: UUID, usuario_id: UUID, fecha_ingreso: datetime
    ) -> UUID:
        ev.append(("insert_member_membership", hogar_id, usuario_id, fecha_ingreso))
        tables = session.write()
        if usuario_id not in tables.profiles:
            raise AssertionError("FK hogar_miembros.usuario_id → usuarios: no hay ficha")
        if any(
            m.usuario_id == usuario_id and m.estado == "activo" for m in tables.memberships.values()
        ):
            raise ActiveMembershipExistsError("El usuario ya tiene un hogar activo.")
        if len(_active(tables, hogar_id)) >= 5:
            raise AssertionError("trigger de 5 miembros activos")
        membresia_id = uuid4()
        tables.memberships[membresia_id] = FakeMembership(
            membresia_id, hogar_id, usuario_id, "miembro", "activo", fecha_ingreso
        )
        return membresia_id

    def is_active_member_email(session: Any, hogar_id: UUID, correo: str) -> bool:
        ev.append(("is_active_member_email", hogar_id, correo))
        return any(
            db.auth_emails.get(m.usuario_id, "").lower() == correo.lower()  # type: ignore[arg-type]
            for m in _active(_tables(session), hogar_id)
        )

    def list_alert_members(session: Any, hogar_id: UUID) -> list[AlertMemberRow]:
        ev.append(("list_alert_members", hogar_id))
        tables = _tables(session)
        rows = []
        for m in sorted(_active(tables, hogar_id), key=lambda m: str(m.usuario_id)):
            prefs = tables.profiles[m.usuario_id].preferencias  # type: ignore[index]
            rows.append(
                AlertMemberRow(
                    usuario_id=m.usuario_id,  # type: ignore[arg-type]
                    rol=m.rol,  # type: ignore[arg-type]
                    notif_consumo=prefs.notif_consumo,
                    notif_consejos=prefs.notif_consejos,
                    fecha_ingreso=m.fecha_ingreso,
                )
            )
        return rows

    def get_alert_permission(session: Any, hogar_id: UUID) -> bool | None:
        ev.append(("get_alert_permission", hogar_id))
        row = _tables(session).households.get(hogar_id)
        return None if row is None else row.permiso_recibir_alertas

    # --- invitaciones ---------------------------------------------------------------------
    def _expire(session: Any, predicate: Callable[[FakeInvitation], bool], now: datetime) -> int:
        stale = [
            i.id
            for i in _tables(session).invitations.values()
            if i.estado == "pendiente" and i.expira_en < now and predicate(i)
        ]
        if stale:
            tables = session.write()
            for invitacion_id in stale:
                tables.invitations[invitacion_id].estado = "expirada"
        return len(stale)

    def expire_stale_pending(session: Any, hogar_id: UUID, correo: str, now: datetime) -> int:
        ev.append(("expire_stale_pending", hogar_id, correo, now))
        return _expire(
            session,
            lambda i: i.hogar_id == hogar_id and i.correo_invitado.lower() == correo.lower(),
            now,
        )

    def expire_stale_pending_for_email(session: Any, correo: str, now: datetime) -> int:
        ev.append(("expire_stale_pending_for_email", correo, now))
        return _expire(session, lambda i: i.correo_invitado.lower() == correo.lower(), now)

    def _pending(session: Any, now: datetime) -> list[FakeInvitation]:
        return [
            i
            for i in _tables(session).invitations.values()
            if i.estado == "pendiente" and i.expira_en >= now
        ]

    def has_pending_invitation(session: Any, hogar_id: UUID, correo: str, now: datetime) -> bool:
        ev.append(("has_pending_invitation", hogar_id, correo, now))
        return any(
            i.hogar_id == hogar_id and i.correo_invitado.lower() == correo.lower()
            for i in _pending(session, now)
        )

    def count_pending_invitations(session: Any, hogar_id: UUID, now: datetime) -> int:
        ev.append(("count_pending_invitations", hogar_id, now))
        return sum(1 for i in _pending(session, now) if i.hogar_id == hogar_id)

    def insert_invitation(
        session: Any,
        *,
        hogar_id: UUID,
        correo_invitado: str,
        invitado_por: UUID,
        token_hash: str,
        expira_en: datetime,
        created_at: datetime,
    ) -> InvitationRow:
        ev.append(("insert_invitation", hogar_id, correo_invitado, token_hash, expira_en))
        tables = session.write()
        if any(
            i.hogar_id == hogar_id
            and i.estado == "pendiente"
            and i.correo_invitado.lower() == correo_invitado.lower()
            for i in tables.invitations.values()
        ):
            raise PendingInvitationExistsError("pendiente existente")
        inv = FakeInvitation(
            id=uuid4(),
            hogar_id=hogar_id,
            correo_invitado=correo_invitado,
            invitado_por=invitado_por,
            estado="pendiente",
            expira_en=expira_en,
            created_at=created_at,
            token_hash=token_hash,
        )
        tables.invitations[inv.id] = inv
        return _invitation_row(inv)

    def list_pending_invitations(
        session: Any, hogar_id: UUID, now: datetime
    ) -> list[InvitationRow]:
        ev.append(("list_pending_invitations", hogar_id, now))
        rows = [i for i in _pending(session, now) if i.hogar_id == hogar_id]
        rows.sort(key=lambda i: (-i.created_at.timestamp(), str(i.id)))
        return [_invitation_row(i) for i in rows]

    def get_invitation(
        session: Any, invitacion_id: UUID, *, for_update: bool = False
    ) -> InvitationRow | None:
        ev.append(("get_invitation", invitacion_id, for_update))
        inv = _tables(session).invitations.get(invitacion_id)
        return None if inv is None else _invitation_row(inv)

    def get_invitation_by_token_hash(session: Any, token_hash: str) -> InvitationRow | None:
        ev.append(("get_invitation_by_token_hash", token_hash))
        for inv in _tables(session).invitations.values():
            if inv.token_hash == token_hash:
                return _invitation_row(inv)
        return None

    def set_invitation_state(
        session: Any, invitacion_id: UUID, estado: str, respondida_en: datetime | None
    ) -> bool:
        ev.append(("set_invitation_state", invitacion_id, estado, respondida_en))
        tables = session.write()
        inv = tables.invitations.get(invitacion_id)
        if inv is None or inv.estado != "pendiente":
            return False
        inv.estado = estado
        inv.respondida_en = respondida_en
        return True

    def list_received_invitations(
        session: Any, correo: str, now: datetime
    ) -> list[ReceivedInvitationRow]:
        ev.append(("list_received_invitations", correo, now))
        tables = _tables(session)
        rows = [i for i in _pending(session, now) if i.correo_invitado.lower() == correo.lower()]
        rows.sort(key=lambda i: (-i.created_at.timestamp(), str(i.id)))
        return [_received_row(tables, i) for i in rows]

    def get_received_invitation(session: Any, invitacion_id: UUID) -> ReceivedInvitationRow | None:
        ev.append(("get_received_invitation", invitacion_id))
        tables = _tables(session)
        inv = tables.invitations.get(invitacion_id)
        return None if inv is None else _received_row(tables, inv)

    # --- usuarios -------------------------------------------------------------------------
    def get_user_profile(session: Any, usuario_id: UUID) -> UserProfileRow | None:
        ev.append(("get_user_profile", usuario_id))
        return _tables(session).profiles.get(usuario_id)

    def lock_user_profile(session: Any, usuario_id: UUID) -> UserProfileRow | None:
        db._hook("lock_user_profile")
        ev.append(("lock_user_profile", usuario_id))
        return _tables(session).profiles.get(usuario_id)

    def delete_user_profile(session: Any, usuario_id: UUID) -> bool:
        ev.append(("delete_user_profile", usuario_id))
        tables = session.write()
        if usuario_id not in tables.profiles:
            return False
        if any(
            m.usuario_id == usuario_id and m.estado == "activo" for m in tables.memberships.values()
        ):
            raise AssertionError("miembros_activo_con_usuario: membresía activa sin usuario")
        del tables.profiles[usuario_id]
        for m in tables.memberships.values():
            if m.usuario_id == usuario_id:
                m.usuario_id = None
        for inv in tables.invitations.values():
            if inv.invitado_por == usuario_id:
                inv.invitado_por = None
        tables.deliveries = [d for d in tables.deliveries if d[1] != usuario_id]
        return True

    # --- alertas --------------------------------------------------------------------------
    def insert_alert(session: Any, *, hogar_id: UUID, **values: Any) -> UUID | None:
        ev.append(("insert_alert", hogar_id, values["clave_evento"]))
        if values["created_at"].utcoffset() is None:
            raise ValueError("`created_at` debe llevar zona horaria.")
        tables = session.write()
        if any(a["clave_evento"] == values["clave_evento"] for a in tables.alerts.values()):
            return None
        alerta_id = uuid4()
        tables.alerts[alerta_id] = {"hogar_id": hogar_id, **values}
        return alerta_id

    def insert_alert_deliveries(session: Any, alerta_id: UUID, usuario_ids: list[UUID]) -> int:
        ev.append(("insert_alert_deliveries", alerta_id, list(usuario_ids)))
        if not usuario_ids:
            return 0
        tables = session.write()
        hogar_id = tables.alerts[alerta_id]["hogar_id"]
        active = {m.usuario_id for m in _active(tables, hogar_id)}
        added = 0
        for usuario_id in usuario_ids:
            if usuario_id in active and (alerta_id, usuario_id) not in tables.deliveries:
                tables.deliveries.append((alerta_id, usuario_id))
                added += 1
        return added

    # --- Supabase y correo ----------------------------------------------------------------
    def delete_auth_user(_settings: Any, usuario_id: UUID) -> None:
        ev.append(("delete_auth_user", usuario_id))
        db._hook("delete_auth_user")
        if db.auth_error is not None:
            raise db.auth_error
        db.auth_emails.pop(usuario_id, None)

    def delete_avatar_files(_settings: Any, usuario_id: UUID) -> None:
        ev.append(("delete_avatar_files", usuario_id))

    def send_invitation_email(
        _settings: Any, *, correo_invitado: str, email: Any, enlace: str
    ) -> None:
        ev.append(("send_invitation_email",))
        if db.email_error is not None:
            raise db.email_error
        db.sent_emails.append(
            SentEmail(correo_invitado, email.asunto, email.texto, email.html, enlace)
        )

    for module, functions in (
        (households_data, (lock_household, get_household, update_permissions, delete_household)),
        (
            memberships_data,
            (
                get_active_membership_of_user,
                count_other_active_members,
                close_membership,
                list_active_members,
                count_active_members,
                get_household_membership,
                get_user_membership_in_household,
                set_membership_role,
                insert_member_membership,
                is_active_member_email,
                list_alert_members,
                get_alert_permission,
            ),
        ),
        (
            invitations_data,
            (
                expire_stale_pending,
                expire_stale_pending_for_email,
                has_pending_invitation,
                count_pending_invitations,
                insert_invitation,
                list_pending_invitations,
                get_invitation,
                get_invitation_by_token_hash,
                set_invitation_state,
                list_received_invitations,
                get_received_invitation,
            ),
        ),
        (users_data, (get_user_profile, lock_user_profile, delete_user_profile)),
        (alerts_data, (insert_alert, insert_alert_deliveries)),
        (supabase_admin, (delete_auth_user, delete_avatar_files)),
        (email_service, (send_invitation_email,)),
    ):
        for function in functions:
            assert hasattr(module, function.__name__), (module.__name__, function.__name__)
            monkeypatch.setattr(module, function.__name__, function)
