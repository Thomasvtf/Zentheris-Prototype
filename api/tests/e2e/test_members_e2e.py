"""Miembros e invitaciones de punta a punta (fase 9), y la carrera al eliminar la cuenta.

El hogar se crea con el onboarding REAL por la API (`POST /api/v1/onboarding`) del hogar de
referencia de cada personalidad, sobre el almacén en memoria de los e2e (`ConsumptionStore` →
`RecoveryStore` + `LiveAlertsMixin` de `tests/e2e/alerts_store.py`, sobre el `Store` de
`test_onboarding_e2e`), ampliado aquí con las sentencias de la fase 9 (`MembersStore`). Después todo
pasa por HTTP con tokens de prueba (`tests/helpers/auth.py`): las 11 operaciones de «Miembros e
invitaciones», `crearFichaUsuario`, `obtenerUsuarioActual`, `eliminarCuenta`, `listarAlertas` y
`contarAlertasNoLeidas`. Corren de verdad la guardia, los routers, `services.members_invitations`,
`services.users.delete_account`, `services.email` (sin SMTP: el enlace va al log, DC-04),
`security.invitation_tokens`, `domain.alert_rules`, `domain.formats` y las funciones de
`app.data`: cada sentencia constante se reconoce por identidad y se resuelve sobre el almacén, que
imita las restricciones de `supabase/migrations/` 0002 y 0003 (claves foráneas con sus acciones,
`uq_miembros_usuario_activo`, `uq_miembros_admin_activo`, `uq_invitacion_pendiente_hogar_correo`,
`token_hash` único, `miembros_activo_con_usuario` y `trg_hogar_miembros_maximo`). Solo se
reemplazan Supabase Auth y Storage (`services.supabase_admin`, otro servicio) y el reloj.

Línea de tiempo (Bogotá; un solo reloj para onboarding, miembros, usuarios y alertas):
T0 = lunes 30/11/2026 12:10 → onboarding (backfill hasta las 11:00). Las operaciones ocurren en
minutos posteriores de la MISMA hora, así `listarAlertas` no tiene horas que recuperar y la
única alerta del hogar es «Nuevo miembro». Las pruebas de vencimiento saltan 7 días y no consultan
alertas después del salto.

Lo que fija la prueba (entrada controlada, no esperados ajustados): el SMTP no está configurado
en `make_test_settings()` (se comprueba); el envío real se envuelve con un espía que delega en la
función real, para leer el correo renderizado.

El SQL no se ejecuta y los bloqueos FOR UPDATE no esperan de verdad: las carreras se fuerzan con
ganchos en el orden que tendrían en PostgreSQL. Que PostgreSQL haga lo mismo (I-03, I-04, R-* y
los bloqueos reales) queda pendiente.

Reglas: RN-II-01…04, RN-IX-03, RN-IX-09, RN-X-01, RN-X-05…08, RN-XIV-06…08, RN-VI-02, RN-I-03.
Decisiones: DC-04, DC-25, DC-36, DC-41, DC-42. Matriz: P-01, P-05, S-01, S-02, I-04.
"""

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.data import households as households_data
from app.data import invitations as invitations_data
from app.data import memberships as memberships_data
from app.domain.formats import format_long_date
from app.domain.simulator import TIMEZONE
from app.main import API_PREFIX
from app.services import alerts_tips, supabase_admin
from app.services import backend_texts as backend_texts_service
from app.services import email as email_service
from app.services import members_invitations as members_service
from app.services import onboarding as onboarding_service
from app.services import users as users_service
from tests.contract.test_c01_responses_match_schema import (
    OPERATIONS,
    assert_matches_contract,
    assert_matches_error_schema,
)
from tests.data.fake_session import FakeResult
from tests.e2e.alerts_store import use_test_config
from tests.e2e.test_consumption_e2e import ConsumptionStore
from tests.e2e.test_hour_recovery_e2e import client_for, create_household
from tests.e2e.test_onboarding_e2e import HOUSEHOLD_NAME, REFERENCE_HOUSEHOLDS, Params, StoreSession
from tests.helpers.auth import auth_header, install_test_jwks, make_test_settings, make_token
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.simulator.support import stable_id

TAG = "e2e9"
T0 = datetime(2026, 11, 30, 12, 10, tzinfo=TIMEZONE)
VALIDITY = timedelta(days=7)  # RN-X-05
MAX_MEMBERS = 5  # RN-II-02
ADMIN_NAME = "Laura Gómez"  # la ficha que siembra `create_household` (Store.seed_user)
ADMIN_EMAIL = "laura.gomez@example.com"
INVITEE_NAME = "Marta Ríos"
INVITEE_EMAIL = "marta.rios@example.com"
LINK_BASE = make_test_settings().invitation_link_base
TEXTS_PATH = Path(__file__).resolve().parents[3] / "docs/textos/textos-backend.es-CO.json"
NEW_MEMBER_TEXT = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))["alertas"]["nuevo_miembro"]
NEW_MEMBER_RULE = "nuevo_miembro"
PERMISSION_COLUMNS = tuple(households_data.PERMISSION_COLUMNS.values())
HOUSEHOLD_COLUMNS = ("id", "nombre", "tipo_vivienda", *PERMISSION_COLUMNS)
DEFAULT_PERMISSIONS = {  # RN-II-03
    "ver_consumo_actual": True,
    "ver_historial": True,
    "recibir_alertas": True,
    "modificar_metas": False,
}
# Las 5 de gestión (solo el administrador, RN-X-08) y las 7 con hogar de la etiqueta.
MANAGEMENT_OPERATIONS = (
    "actualizarPermisos",
    "expulsarMiembro",
    "transferirAdministracion",
    "crearInvitacion",
    "revocarInvitacion",
)
HOUSEHOLD_OPERATIONS = ("listarMiembros", "salirDelHogar", *MANAGEMENT_OPERATIONS)
NO_BODY = object()

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)
ONE_PERSONALITY = PERSONALITY_ORDER[2]  # casos de reglas: basta un hogar


# --- reloj ----------------------------------------------------------------------------------


class Clock:
    moment = T0


class MembersClock(datetime):
    """`datetime.now()` de onboarding, miembros, usuarios y alertas en `Clock.moment`."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return Clock.moment.astimezone(tz)


def at(minutes: int = 0, *, days: int = 0) -> datetime:
    Clock.moment = T0 + timedelta(days=days, minutes=minutes)
    return Clock.moment


# --- el almacén con las sentencias de la fase 9 ---------------------------------------------


class MembersStore(ConsumptionStore):
    """`ConsumptionStore` (guardia, alertas y onboarding) más hogares, membresías e invitaciones.

    `auth_users` guarda el correo de cada cuenta (lo lee `is_active_member_email`). Las filas de
    `invitaciones_hogar` guardan `token_hash` como la tabla; ninguna sentencia lo devuelve.
    """

    def __init__(self) -> None:
        super().__init__()
        self.emails: dict[UUID, str] = {}  # correo del token de cada persona (sobrevive a Auth)
        self.sent: list[tuple[str, Any, str]] = []  # (correo, RenderedEmail, enlace) del espía
        self.gap_hooks: list[Callable[[], None]] = []  # después del commit, antes de Auth
        inv, mem, hh = invitations_data, memberships_data, households_data
        for module, name, handler in (
            (hh, "HOUSEHOLD_SQL", self._household),
            (hh, "UPDATE_PERMISSIONS_SQL", self._update_permissions),
            (mem, "ACTIVE_MEMBERS_SQL", self._active_members),
            (mem, "COUNT_ACTIVE_MEMBERS_SQL", self._count_active_members),
            (mem, "HOUSEHOLD_MEMBERSHIP_SQL", self._household_membership),
            (mem, "HOUSEHOLD_MEMBERSHIP_FOR_UPDATE_SQL", self._household_membership),
            (mem, "USER_MEMBERSHIP_IN_HOUSEHOLD_SQL", self._user_membership),
            (mem, "USER_MEMBERSHIP_IN_HOUSEHOLD_FOR_UPDATE_SQL", self._user_membership),
            (mem, "SET_MEMBERSHIP_ROLE_SQL", self._set_membership_role),
            (mem, "INSERT_MEMBER_MEMBERSHIP_SQL", self._insert_member),
            (mem, "ACTIVE_MEMBER_EMAIL_SQL", self._active_member_email),
            (inv, "EXPIRE_STALE_PENDING_SQL", self._expire_stale),
            (inv, "EXPIRE_STALE_PENDING_FOR_EMAIL_SQL", self._expire_stale),
            (inv, "HAS_PENDING_INVITATION_SQL", self._has_pending),
            (inv, "COUNT_PENDING_INVITATIONS_SQL", self._count_pending),
            (inv, "COUNT_INVITATIONS_CREATED_BETWEEN_SQL", self._count_created_between),
            (inv, "INSERT_INVITATION_SQL", self._insert_invitation),
            (inv, "LIST_PENDING_INVITATIONS_SQL", self._list_pending),
            (inv, "INVITATION_BY_ID_SQL", self._invitation_by_id),
            (inv, "INVITATION_BY_ID_FOR_UPDATE_SQL", self._invitation_by_id),
            (inv, "INVITATION_BY_TOKEN_HASH_SQL", self._invitation_by_token_hash),
            (inv, "SET_INVITATION_STATE_SQL", self._set_invitation_state),
            (inv, "LIST_RECEIVED_INVITATIONS_SQL", self._received),
            (inv, "RECEIVED_INVITATION_BY_ID_SQL", self._received),
        ):
            self.handlers[id(getattr(module, name))] = (name, handler)

    # --- semilla y ganchos -------------------------------------------------------------

    def add_account(self, usuario_id: UUID, correo: str) -> None:
        """Cuenta de Supabase Auth con su correo (sin tocar la ficha, si la hay)."""
        self.emails[usuario_id] = correo
        self.committed["auth_users"][usuario_id] = {"email": correo}

    def once_before(self, statement: str, action: Callable[[], None]) -> None:
        """`action` justo antes de la próxima ejecución de `statement` (una sola vez)."""

        def hook() -> None:
            self.before.pop(statement, None)
            action()

        self.before[statement] = hook

    def delete_auth_user(self, settings: Settings, usuario_id: UUID) -> None:
        """El hueco de la carrera: los ganchos corren tras el commit y antes de borrar en Auth."""
        hooks, self.gap_hooks = self.gap_hooks, []
        for hook in hooks:
            hook()
        super().delete_auth_user(settings, usuario_id)

    # --- lo que miran las pruebas ------------------------------------------------------

    def members_of(self, hogar_id: UUID) -> list[dict[str, Any]]:
        return [row for row in self.rows("hogar_miembros") if row["hogar_id"] == hogar_id]

    def membership(self, membresia_id: UUID) -> dict[str, Any]:
        return self.committed["hogar_miembros"][membresia_id]

    def invitation(self, invitacion_id: UUID) -> dict[str, Any]:
        return self.committed["invitaciones_hogar"][invitacion_id]

    def household_alerts(self, hogar_id: UUID) -> list[dict[str, Any]]:
        return [row for row in self.rows("alertas") if row["hogar_id"] == hogar_id]

    def household_data(self, hogar_id: UUID) -> dict[str, int]:
        """Filas del hogar que nada de la fase 9 debe tocar (zonas, sensores y lecturas)."""
        zones = {row["id"] for row in self.rows("zonas") if row["hogar_id"] == hogar_id}
        sensors = {row["id"] for row in self.rows("sensores_zona") if row["zona_id"] in zones}
        readings = [row for row in self.rows("lecturas") if row["sensor_id"] in sensors]
        return {"zonas": len(zones), "sensores": len(sensors), "lecturas": len(readings)}

    def assert_member_invariants(self) -> None:
        """Restricciones de 0002/0003 sobre lo confirmado al final de cada prueba (I-04)."""
        active = [row for row in self.rows("hogar_miembros") if row["estado"] == "activo"]
        assert all(row["usuario_id"] is not None for row in active), "miembros_activo_con_usuario"
        assert all(row["usuario_id"] in self.committed["usuarios"] for row in active)
        users = Counter(row["usuario_id"] for row in active)
        assert all(count == 1 for count in users.values()), "uq_miembros_usuario_activo"
        admins = Counter(row["hogar_id"] for row in active if row["rol"] == "administrador")
        assert all(count == 1 for count in admins.values()), "uq_miembros_admin_activo"
        per_household = Counter(row["hogar_id"] for row in active)
        assert all(count <= MAX_MEMBERS for count in per_household.values()), "RN-II-02"
        pending = Counter(
            (row["hogar_id"], row["correo_invitado"].lower())
            for row in self.rows("invitaciones_hogar")
            if row["estado"] == "pendiente"
        )
        assert all(count == 1 for count in pending.values()), "uq_invitacion_pendiente"
        hashes = [row["token_hash"] for row in self.rows("invitaciones_hogar")]
        assert len(set(hashes)) == len(hashes), "token_hash único"

    # --- hogares ------------------------------------------------------------------------

    @staticmethod
    def _household_row(row: dict[str, Any]) -> dict[str, Any]:
        return {column: row[column] for column in HOUSEHOLD_COLUMNS}

    def _household(self, session: StoreSession, params: Params) -> FakeResult:
        row = self.view(session, "hogares").get(params["hogar_id"])
        return FakeResult([] if row is None else [self._household_row(row)])

    def _update_permissions(self, session: StoreSession, params: Params) -> FakeResult:
        """`coalesce(:param, columna)` en las 4 columnas; RETURNING la fila."""
        row = self.view(session, "hogares").get(params["hogar_id"])
        if row is None:
            return FakeResult()
        changed = dict(row)
        for key, column in households_data.PERMISSION_COLUMNS.items():
            if params[key] is not None:
                changed[column] = params[key]
        self.put(session, "hogares", row["id"], changed)
        return FakeResult([self._household_row(changed)], rowcount=1)

    # --- membresías -----------------------------------------------------------------------

    def _active_in(self, session: StoreSession, hogar_id: UUID) -> list[dict[str, Any]]:
        return [
            row
            for row in self.view(session, "hogar_miembros").values()
            if row["hogar_id"] == hogar_id and row["estado"] == "activo"
        ]

    @staticmethod
    def _membership_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "membresia_id": row["id"],
            "hogar_id": row["hogar_id"],
            "usuario_id": row["usuario_id"],
            "rol": row["rol"],
            "estado": row["estado"],
        }

    def _active_members(self, session: StoreSession, params: Params) -> FakeResult:
        """JOIN usuarios; administrador primero, luego fecha_ingreso y id."""
        users = self.view(session, "usuarios")
        rows = [
            {
                "membresia_id": row["id"],
                "usuario_id": row["usuario_id"],
                "nombre_completo": users[row["usuario_id"]]["nombre_completo"],
                "avatar_url": users[row["usuario_id"]]["avatar_url"],
                "rol": row["rol"],
                "fecha_ingreso": row["fecha_ingreso"],
            }
            for row in self._active_in(session, params["hogar_id"])
            if row["usuario_id"] in users
        ]
        rows.sort(
            key=lambda r: (r["rol"] != "administrador", r["fecha_ingreso"], str(r["membresia_id"]))
        )
        return FakeResult(rows)

    def _count_active_members(self, session: StoreSession, params: Params) -> FakeResult:
        return FakeResult([{"total": len(self._active_in(session, params["hogar_id"]))}])

    def _household_membership(self, session: StoreSession, params: Params) -> FakeResult:
        row = self.view(session, "hogar_miembros").get(params["membresia_id"])
        if row is None or row["hogar_id"] != params["hogar_id"]:
            return FakeResult()
        return FakeResult([self._membership_row(row)])

    def _user_membership(self, session: StoreSession, params: Params) -> FakeResult:
        return FakeResult(
            [
                self._membership_row(row)
                for row in self._active_in(session, params["hogar_id"])
                if row["usuario_id"] == params["usuario_id"]
            ]
        )

    def _set_membership_role(self, session: StoreSession, params: Params) -> FakeResult:
        """UPDATE … WHERE estado = 'activo'; `uq_miembros_admin_activo` al subir a administrador."""
        row = self.view(session, "hogar_miembros").get(params["membresia_id"])
        if row is None or row["estado"] != "activo":
            return FakeResult(rowcount=0)
        if params["rol"] == "administrador":
            others = [
                other
                for other in self._active_in(session, row["hogar_id"])
                if other["id"] != row["id"] and other["rol"] == "administrador"
            ]
            self._require(not others, "23505", "uq_miembros_admin_activo")
        self.put(session, "hogar_miembros", row["id"], {**row, "rol": params["rol"]})
        return FakeResult(rowcount=1)

    def _insert_member(self, session: StoreSession, params: Params) -> FakeResult:
        hogar_id, usuario_id = params["hogar_id"], params["usuario_id"]
        self._claim_unique(session, ("uq_miembros_usuario_activo", usuario_id))
        active = [r for r in self.view(session, "hogar_miembros").values() if r["estado"] == "activo"]
        self._require(
            usuario_id not in {r["usuario_id"] for r in active}, "23505", "uq_miembros_usuario_activo"
        )
        self._require(
            usuario_id in self.view(session, "usuarios"), "23503", "hogar_miembros_usuario_id_fkey"
        )
        self._require(
            hogar_id in self.view(session, "hogares"), "23503", "hogar_miembros_hogar_id_fkey"
        )
        self._require(
            sum(r["hogar_id"] == hogar_id for r in active) < MAX_MEMBERS,
            "23514",
            "trg_hogar_miembros_maximo",
        )
        membresia_id = uuid4()
        row = {
            "id": membresia_id,
            "hogar_id": hogar_id,
            "usuario_id": usuario_id,
            "rol": "miembro",
            "estado": "activo",
            "fecha_ingreso": params["fecha_ingreso"],
            "fecha_salida": None,
        }
        self.put(session, "hogar_miembros", membresia_id, row)
        return FakeResult([{"id": membresia_id}], rowcount=1)

    def _active_member_email(self, session: StoreSession, params: Params) -> FakeResult:
        """JOIN auth.users; `lower()` en ambos lados."""
        accounts = self.view(session, "auth_users")
        found = any(
            accounts.get(row["usuario_id"], {}).get("email", "").lower()
            == params["correo"].lower()
            for row in self._active_in(session, params["hogar_id"])
        )
        return FakeResult([{"existe": 1}] if found else [])

    # --- invitaciones ---------------------------------------------------------------------

    @staticmethod
    def _invitation_row(row: dict[str, Any]) -> dict[str, Any]:
        """Las columnas de InvitationRow: nunca `token_hash` (RN-X-05)."""
        return {
            column: row[column]
            for column in (
                "id",
                "hogar_id",
                "correo_invitado",
                "invitado_por",
                "estado",
                "expira_en",
                "respondida_en",
                "created_at",
            )
        }

    def _expire_stale(self, session: StoreSession, params: Params) -> FakeResult:
        """DC-42: pendientes vencidas (`expira_en < now`, RN-X-05) del correo (y del hogar, si viene)."""
        changed = 0
        for key, row in self.view(session, "invitaciones_hogar").items():
            if "hogar_id" in params and row["hogar_id"] != params["hogar_id"]:
                continue
            if row["correo_invitado"].lower() != params["correo"].lower():
                continue
            if row["estado"] == "pendiente" and row["expira_en"] < params["now"]:
                self.put(session, "invitaciones_hogar", key, {**row, "estado": "expirada"})
                changed += 1
        return FakeResult(rowcount=changed)

    def _pending(self, session: StoreSession, hogar_id: UUID, now: datetime) -> list[dict]:
        return [
            row
            for row in self.view(session, "invitaciones_hogar").values()
            if row["hogar_id"] == hogar_id and row["estado"] == "pendiente" and row["expira_en"] >= now
        ]

    def _has_pending(self, session: StoreSession, params: Params) -> FakeResult:
        found = any(
            row["correo_invitado"].lower() == params["correo"].lower()
            for row in self._pending(session, params["hogar_id"], params["now"])
        )
        return FakeResult([{"existe": 1}] if found else [])

    def _count_pending(self, session: StoreSession, params: Params) -> FakeResult:
        return FakeResult([{"total": len(self._pending(session, params["hogar_id"], params["now"]))}])

    def _count_created_between(self, session: StoreSession, params: Params) -> FakeResult:
        """count(*) del hogar con `created_at >= :start and created_at < :end`, cualquier estado."""
        total = sum(
            row["hogar_id"] == params["hogar_id"]
            and params["start"] <= row["created_at"] < params["end"]
            for row in self.view(session, "invitaciones_hogar").values()
        )
        return FakeResult([{"total": total}])

    def _insert_invitation(self, session: StoreSession, params: Params) -> FakeResult:
        hogar_id, correo = params["hogar_id"], params["correo_invitado"]
        index = invitations_data.PENDING_INVITATION_INDEX
        self._claim_unique(session, (index, hogar_id, correo.lower()))
        rows = self.view(session, "invitaciones_hogar").values()
        taken = {(r["hogar_id"], r["correo_invitado"].lower()) for r in rows if r["estado"] == "pendiente"}
        self._require((hogar_id, correo.lower()) not in taken, "23505", index)
        hashes = {r["token_hash"] for r in rows}
        self._require(params["token_hash"] not in hashes, "23505", "invitaciones_hogar_token_hash_key")
        self._require(
            hogar_id in self.view(session, "hogares"), "23503", "invitaciones_hogar_hogar_id_fkey"
        )
        self._require(
            params["invitado_por"] in self.view(session, "usuarios"),
            "23503",
            "invitaciones_hogar_invitado_por_fkey",
        )
        invitacion_id = uuid4()
        row = {
            "id": invitacion_id,
            "hogar_id": hogar_id,
            "correo_invitado": correo,
            "invitado_por": params["invitado_por"],
            "token_hash": params["token_hash"],
            "estado": "pendiente",
            "expira_en": params["expira_en"],
            "respondida_en": None,
            "created_at": params["created_at"],
        }
        self.put(session, "invitaciones_hogar", invitacion_id, row)
        return FakeResult([self._invitation_row(row)], rowcount=1)

    def _list_pending(self, session: StoreSession, params: Params) -> FakeResult:
        rows = self._pending(session, params["hogar_id"], params["now"])
        rows.sort(key=lambda r: str(r["id"]))
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return FakeResult([self._invitation_row(row) for row in rows])

    def _invitation_by_id(self, session: StoreSession, params: Params) -> FakeResult:
        row = self.view(session, "invitaciones_hogar").get(params["invitacion_id"])
        return FakeResult([] if row is None else [self._invitation_row(row)])

    def _invitation_by_token_hash(self, session: StoreSession, params: Params) -> FakeResult:
        rows = self.view(session, "invitaciones_hogar").values()
        return FakeResult(
            [self._invitation_row(r) for r in rows if r["token_hash"] == params["token_hash"]]
        )

    def _set_invitation_state(self, session: StoreSession, params: Params) -> FakeResult:
        """UPDATE … WHERE id AND estado = 'pendiente' RETURNING id; check del estado."""
        self._require(
            params["estado"] in ("pendiente", "aceptada", "rechazada", "expirada", "revocada"),
            "23514",
            "invitaciones_hogar_estado_check",
        )
        row = self.view(session, "invitaciones_hogar").get(params["invitacion_id"])
        if row is None or row["estado"] != "pendiente":
            return FakeResult()
        changed = {**row, "estado": params["estado"], "respondida_en": params["respondida_en"]}
        self.put(session, "invitaciones_hogar", row["id"], changed)
        return FakeResult([{"id": row["id"]}], rowcount=1)

    def _received(self, session: StoreSession, params: Params) -> FakeResult:
        """JOIN hogares; nombre de quien invitó o, si no, del administrador activo (lateral)."""
        users = self.view(session, "usuarios")
        households = self.view(session, "hogares")
        rows = []
        for row in self.view(session, "invitaciones_hogar").values():
            if "invitacion_id" in params:
                if row["id"] != params["invitacion_id"]:
                    continue
            elif not (
                row["correo_invitado"].lower() == params["correo"].lower()
                and row["estado"] == "pendiente"
                and row["expira_en"] >= params["now"]
            ):
                continue
            inviter = users.get(row["invitado_por"]) if row["invitado_por"] else None
            admins = [
                users[m["usuario_id"]]["nombre_completo"]
                for m in self._active_in(session, row["hogar_id"])
                if m["rol"] == "administrador" and m["usuario_id"] in users
            ]
            name = inviter["nombre_completo"] if inviter else (admins[0] if admins else None)
            rows.append(
                {
                    "id": row["id"],
                    "hogar_id": row["hogar_id"],
                    "hogar_nombre": households[row["hogar_id"]]["nombre"],
                    "invitado_por_nombre": name,
                    "expira_en": row["expira_en"],
                    "created_at": row["created_at"],
                }
            )
        rows.sort(key=lambda r: str(r["id"]))
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return FakeResult(rows)


# --- fixtures -------------------------------------------------------------------------------


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> Iterator[MembersStore]:
    store = MembersStore()
    Clock.moment = T0
    for module in (onboarding_service, alerts_tips, members_service, users_service):
        monkeypatch.setattr(module, "datetime", MembersClock)
    use_test_config(monkeypatch)  # umbrales y textos de make_test_settings(), caché propia
    monkeypatch.setattr(
        members_service, "get_backend_texts", backend_texts_service.get_backend_texts
    )
    install_test_jwks(monkeypatch)
    monkeypatch.setattr(supabase_admin, "delete_auth_user", store.delete_auth_user)
    monkeypatch.setattr(supabase_admin, "delete_avatar_files", store.delete_avatar_files)
    real_send = email_service.send_invitation_email

    def spy(settings: Settings, *, correo_invitado: str, email: Any, enlace: str) -> None:
        store.sent.append((correo_invitado, email, enlace))
        real_send(settings, correo_invitado=correo_invitado, email=email, enlace=enlace)

    monkeypatch.setattr(email_service, "send_invitation_email", spy)
    assert not email_service.smtp_configured(make_test_settings())  # DC-04: modo local
    caplog.set_level(logging.INFO)
    yield store
    # Los servicios capturan cualquier excepción: lo inesperado se comprueba aquí.
    assert store.unexpected == []
    store.assert_live_alert_rules()  # A-01/A-02 y «Nuevo miembro» nace de su membresía
    store.assert_member_invariants()


@pytest.fixture
def client(db: MembersStore) -> TestClient:
    return client_for(db)


# --- pasos ----------------------------------------------------------------------------------


class Api:
    """Llama una operación del contrato como una persona (token con su correo).

    Estado declarado → su esquema exacto; 500 no declarado → esquema `Error`; cualquier otro
    estado no declarado hace fallar la prueba.
    """

    def __init__(self, client: TestClient, db: MembersStore) -> None:
        self.client = client
        self.db = db

    def __call__(
        self,
        operation_id: str,
        user_id: UUID,
        body: Any = NO_BODY,
        **path_ids: UUID,
    ) -> httpx.Response:
        method, path, op = OPERATIONS[operation_id]
        url = API_PREFIX + path.format(**{key: str(value) for key, value in path_ids.items()})
        kwargs: dict[str, Any] = {
            "headers": auth_header(make_token(user_id, self.db.emails[user_id]))
        }
        if body is not NO_BODY:
            kwargs["json"] = body
        response = self.client.request(method.upper(), url, **kwargs)
        if str(response.status_code) in op["responses"]:
            assert_matches_contract(operation_id, response)
        elif response.status_code == 500:
            assert_matches_error_schema(response)
        else:
            pytest.fail(f"{operation_id} respondió {response.status_code}, que el contrato no declara")
        return response


def ok(response: httpx.Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return None if status == 204 else response.json()


def error(response: httpx.Response, status: int, codigo: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"codigo", "mensaje", "detalles"}
    assert body["codigo"] == codigo, body
    return body


def household(db: MembersStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str,
              tag: str = TAG) -> tuple[UUID, UUID]:
    """Onboarding real del hogar de referencia de `name`; (administrador, hogar)."""
    at(0)
    hogar_id = create_household(db, client, monkeypatch, name, tag)
    admin = stable_id("usuario", tag, name)
    db.add_account(admin, ADMIN_EMAIL if tag == TAG else f"admin-{tag}@example.com")
    return admin, hogar_id


def person(db: MembersStore, label: str, correo: str | None = None) -> UUID:
    """Cuenta de Auth sin ficha (la crea por la API `with_profile`)."""
    usuario_id = stable_id("persona", TAG, label)
    db.add_account(usuario_id, correo or f"{label}@example.com")
    return usuario_id


def with_profile(api: Api, usuario_id: UUID, nombre: str) -> None:
    """`crearFichaUsuario` (RN-IX-01): primer acceso de la persona invitada."""
    ok(api("crearFichaUsuario", usuario_id, {"nombre_completo": nombre}), 201)


def invite(
    api: Api, caplog: pytest.LogCaptureFixture, admin: UUID, hogar_id: UUID, correo: str
) -> tuple[UUID, str]:
    """`crearInvitacion`; el token sale del enlace del log (sin SMTP, DC-04). (id, token)."""
    before = len(caplog.records)
    body = ok(api("crearInvitacion", admin, {"correo_invitado": correo}, hogar_id=hogar_id), 201)
    (message,) = [
        record.getMessage()
        for record in caplog.records[before:]
        if record.name == email_service.__name__
    ]
    assert message.count(LINK_BASE) == 1, message
    return UUID(body["id"]), message.split(LINK_BASE, 1)[1]


def join(
    api: Api, db: MembersStore, caplog: pytest.LogCaptureFixture, admin: UUID, hogar_id: UUID,
    label: str,
) -> tuple[UUID, UUID]:
    """Una persona nueva con ficha que acepta su invitación; (usuario, membresía)."""
    usuario_id = person(db, label)
    with_profile(api, usuario_id, label.capitalize())
    invitacion_id, _token = invite(api, caplog, admin, hogar_id, db.emails[usuario_id])
    accepted = ok(api("aceptarInvitacion", usuario_id, invitacion_id=invitacion_id))
    return usuario_id, UUID(accepted["membresia_id"])


def alert_ids(api: Api, user_id: UUID, hogar_id: UUID) -> list[str]:
    return [a["id"] for a in ok(api("listarAlertas", user_id, hogar_id=hogar_id))["alertas"]]


def moment_of(text: str) -> datetime:
    return datetime.fromisoformat(text)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- flujo principal, por personalidad -------------------------------------------------------


@each_personality
def test_from_the_invitation_to_the_admin_leaving(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    name: str,
) -> None:
    """Invitar → crear ficha → recibidas → resolver → aceptar → miembros → permisos → transferir → salir.

    Esperado, en orden:
    - `crearInvitacion` 201 con el correo en minúsculas, 'pendiente' y `expira_en` = ahora + 7 días
      (RN-X-05). Sin SMTP el ENLACE sale en el log y el log no lleva el correo (DC-04, S-01). En la
      base solo el hash: sha256(token del enlace) == token_hash y el token no está en la fila
      (S-02). El correo renderizado lleva el enlace, quien invita, el hogar y la fecha larga.
    - La persona crea su ficha (RN-IX-01), ve 1 invitación recibida con hogar y quien invita
      (RN-X-01), la resuelve con el token y la acepta: membresía 'miembro' activa con
      `fecha_ingreso` = ahora, invitación 'aceptada' con `respondida_en` (RN-X-06).
    - Alerta «Nuevo miembro» en la misma transacción: clave `nuevo_miembro:<membresia_id>`, textos
      de la plantilla con su nombre y el del hogar, sin zona; visible en GET /alertas del
      administrador (1 sin leer) y NO para el nuevo (RN-XIV-06/07, RN-VI-02, DC-25).
    - `listarMiembros`: el administrador ve las pendientes y `puede_gestionar`; el miembro recibe
      `null` y false (RN-X-08). `actualizarPermisos`: `{}` → 422 sin cambios; un permiso → 200;
      el miembro → 403 `NO_ES_ADMINISTRADOR` (P-05) (RN-II-03).
    - `transferirAdministracion` → el anterior administrador pasa a miembro y pierde la gestión;
      el nuevo administrador no puede salir con otros (409 `ADMIN_DEBE_TRANSFERIR`); el anterior
      sale (204, 'inactivo' con `fecha_salida`) y luego recibe 404 (P-01); el administrador solo
      no puede salir (409 `ADMIN_UNICO_MIEMBRO`) (RN-II-04, RN-X-07).
    - Zonas, sensores y lecturas del hogar no cambian.
    """
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, name)
    invitee = person(db, "invitada", INVITEE_EMAIL)
    data_before = db.household_data(hogar_id)
    assert data_before["lecturas"] == 720 * len(REFERENCE_HOUSEHOLDS[name][1])

    # 1. El administrador invita (RN-X-05, RN-IX-03, DC-04, S-01, S-02).
    invited_at = at(5)
    invitacion_id, token = invite(api, caplog, admin, hogar_id, "Marta.Rios@Example.com")
    row = db.invitation(invitacion_id)
    assert row["correo_invitado"] == INVITEE_EMAIL
    assert (row["estado"], row["invitado_por"], row["respondida_en"]) == ("pendiente", admin, None)
    assert row["created_at"] == invited_at and row["expira_en"] == invited_at + VALIDITY
    assert row["token_hash"] == sha256(token) and len(row["token_hash"]) == 64
    assert all(token not in str(value) for value in row.values())
    assert row["token_hash"] not in caplog.text
    (sent_to, email, enlace) = db.sent[-1]
    assert (sent_to, enlace) == (INVITEE_EMAIL, LINK_BASE + token)
    expiry_text = format_long_date((invited_at + VALIDITY).astimezone(TIMEZONE).date())
    assert expiry_text == "7 de diciembre de 2026"
    for fragment in (enlace, ADMIN_NAME, HOUSEHOLD_NAME, expiry_text):
        assert fragment in email.texto, fragment
    assert enlace in email.html

    pending_view = ok(api("listarMiembros", admin, hogar_id=hogar_id))
    assert pending_view["miembros_activos"] == 1
    assert pending_view["invitaciones_pendientes"] == [
        {
            "id": str(invitacion_id),
            "correo_invitado": INVITEE_EMAIL,
            "estado": "pendiente",
            "expira_en": pending_view["invitaciones_pendientes"][0]["expira_en"],
        }
    ]
    assert moment_of(pending_view["invitaciones_pendientes"][0]["expira_en"]) == row["expira_en"]

    # 2. La persona invitada crea su ficha, ve la invitación, la resuelve y la acepta (RN-X-06).
    at(10)
    with_profile(api, invitee, INVITEE_NAME)
    received = ok(api("listarInvitacionesRecibidas", invitee))["invitaciones"]
    expected_received = {
        "id": str(invitacion_id),
        "hogar_nombre": HOUSEHOLD_NAME,
        "invitado_por_nombre": ADMIN_NAME,
    }
    assert [{k: r[k] for k in expected_received} for r in received] == [expected_received]
    assert moment_of(received[0]["expira_en"]) == row["expira_en"]
    resolved = ok(api("resolverTokenInvitacion", invitee, {"token": token}))
    assert resolved == received[0]

    accepted_at = at(15)
    accepted = ok(api("aceptarInvitacion", invitee, invitacion_id=invitacion_id))
    membresia_id = UUID(accepted["membresia_id"])
    assert accepted == {
        "membresia_id": str(membresia_id),
        "hogar_id": str(hogar_id),
        "rol": "miembro",
    }
    new_member = db.membership(membresia_id)
    assert (new_member["usuario_id"], new_member["rol"], new_member["estado"]) == (
        invitee,
        "miembro",
        "activo",
    )
    assert new_member["fecha_ingreso"] == accepted_at
    assert db.invitation(invitacion_id)["estado"] == "aceptada"
    assert db.invitation(invitacion_id)["respondida_en"] == accepted_at
    me = ok(api("obtenerUsuarioActual", invitee))
    assert me["membresia"] == accepted

    # 3. «Nuevo miembro» en la misma transacción, para los demás (RN-XIV-06/07, DC-25).
    (alert,) = db.household_alerts(hogar_id)
    assert alert["clave_evento"] == f"{NEW_MEMBER_RULE}:{membresia_id}"
    assert (alert["regla_origen"], alert["categoria"], alert["severidad"], alert["zona_id"]) == (
        NEW_MEMBER_RULE,
        "informacion",
        "informativa",
        None,
    )
    assert alert["titulo"] == NEW_MEMBER_TEXT["titulo"].replace("{nombre}", INVITEE_NAME)
    assert alert["mensaje"] == NEW_MEMBER_TEXT["mensaje"].replace("{nombre}", INVITEE_NAME).replace(
        "{hogar}", HOUSEHOLD_NAME
    )
    assert alert["created_at"] == accepted_at
    deliveries = [key for key in db.committed["alertas_usuario"] if key[0] == alert["id"]]
    assert deliveries == [(alert["id"], admin)]
    at(20)
    (listed,) = ok(api("listarAlertas", admin, hogar_id=hogar_id))["alertas"]
    assert (listed["id"], listed["titulo"], listed["mensaje"]) == (
        str(alert["id"]),
        alert["titulo"],
        alert["mensaje"],
    )
    assert ok(api("contarAlertasNoLeidas", admin, hogar_id=hogar_id))["cantidad"] == 1
    assert alert_ids(api, invitee, hogar_id) == []

    # 4. Miembros: el administrador gestiona; el miembro no (RN-X-08).
    admin_view = ok(api("listarMiembros", admin, hogar_id=hogar_id))
    member_view = ok(api("listarMiembros", invitee, hogar_id=hogar_id))
    roster = [(m["usuario_id"], m["rol"], m["nombre_completo"]) for m in admin_view["miembros"]]
    assert roster == [
        (str(admin), "administrador", ADMIN_NAME),
        (str(invitee), "miembro", INVITEE_NAME),
    ]
    assert admin_view["miembros_activos"] == 2
    assert (admin_view["invitaciones_pendientes"], admin_view["puede_gestionar"]) == ([], True)
    assert (member_view["invitaciones_pendientes"], member_view["puede_gestionar"]) == (None, False)
    assert member_view["miembros"] == admin_view["miembros"]
    assert admin_view["permisos"] == member_view["permisos"] == DEFAULT_PERMISSIONS

    # 5. Permisos (RN-II-03, RN-X-08, P-05).
    before = db.snapshot()
    error(api("actualizarPermisos", admin, {}, hogar_id=hogar_id), 422, "VALIDACION")
    error(
        api("actualizarPermisos", invitee, {"modificar_metas": True}, hogar_id=hogar_id),
        403,
        "NO_ES_ADMINISTRADOR",
    )
    assert db.snapshot() == before
    permisos = ok(api("actualizarPermisos", admin, {"modificar_metas": True}, hogar_id=hogar_id))
    assert permisos == {**DEFAULT_PERMISSIONS, "modificar_metas": True}
    assert db.committed["hogares"][hogar_id]["permiso_modificar_metas"] is True
    assert ok(api("listarMiembros", invitee, hogar_id=hogar_id))["permisos"] == permisos

    # 6. Transferir, salir y el administrador solo (RN-II-04, RN-X-07).
    at(25)
    (admin_membership,) = [m["id"] for m in db.members_of(hogar_id) if m["usuario_id"] == admin]
    transferred = ok(
        api("transferirAdministracion", admin, hogar_id=hogar_id, membresia_id=membresia_id)
    )
    assert (transferred["puede_gestionar"], transferred["invitaciones_pendientes"]) == (False, None)
    assert [(m["usuario_id"], m["rol"]) for m in transferred["miembros"]] == [
        (str(invitee), "administrador"),
        (str(admin), "miembro"),
    ]
    assert db.membership(admin_membership)["rol"] == "miembro"
    assert db.membership(membresia_id)["rol"] == "administrador"
    error(
        api("crearInvitacion", admin, {"correo_invitado": "otra@example.com"}, hogar_id=hogar_id),
        403,
        "NO_ES_ADMINISTRADOR",
    )
    error(api("salirDelHogar", invitee, hogar_id=hogar_id), 409, "ADMIN_DEBE_TRANSFERIR")

    left_at = at(30)
    ok(api("salirDelHogar", admin, hogar_id=hogar_id), 204)
    old = db.membership(admin_membership)
    assert (old["estado"], old["fecha_salida"], old["usuario_id"]) == ("inactivo", left_at, admin)
    error(api("listarMiembros", admin, hogar_id=hogar_id), 404, "NO_ENCONTRADO")  # P-01
    error(api("salirDelHogar", invitee, hogar_id=hogar_id), 409, "ADMIN_UNICO_MIEMBRO")
    alone = ok(api("listarMiembros", invitee, hogar_id=hogar_id))
    assert (alone["miembros_activos"], alone["puede_gestionar"]) == (1, True)

    assert db.household_data(hogar_id) == data_before
    for text in (INVITEE_EMAIL, ADMIN_EMAIL):
        assert text not in caplog.text.lower()


# --- expulsar, revocar y rechazar -------------------------------------------------------------


def test_remove_revoke_and_reject(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Expulsar (RN-X-07), revocar y rechazar (RN-X-06) por la API.

    Esperado: expulsar → 204, la membresía queda 'inactivo' con `fecha_salida` y la persona pierde
    el acceso (404); expulsar otra vez → 404; el administrador no puede expulsarse con otros (409
    `ADMIN_DEBE_TRANSFERIR`). Revocar → 204, 'revocada' sin `respondida_en`; otra vez → 409
    `INVITACION_NO_PENDIENTE`; el enlace ya no sirve (409). Rechazar → 204, 'rechazada' con
    `respondida_en`; aceptar después → 409 `INVITACION_NO_PENDIENTE`, sin membresía.
    """
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    (admin_membership,) = [m["id"] for m in db.members_of(hogar_id)]
    at(5)
    member, membresia_id = join(api, db, caplog, admin, hogar_id, "beatriz")

    removed_at = at(10)
    ok(api("expulsarMiembro", admin, hogar_id=hogar_id, membresia_id=membresia_id), 204)
    removed = db.membership(membresia_id)
    assert (removed["estado"], removed["fecha_salida"]) == ("inactivo", removed_at)
    error(api("listarMiembros", member, hogar_id=hogar_id), 404, "NO_ENCONTRADO")
    error(
        api("expulsarMiembro", admin, hogar_id=hogar_id, membresia_id=membresia_id),
        404,
        "NO_ENCONTRADO",
    )
    _other, _ = join(api, db, caplog, admin, hogar_id, "carlos")
    error(
        api("expulsarMiembro", admin, hogar_id=hogar_id, membresia_id=admin_membership),
        409,
        "ADMIN_DEBE_TRANSFERIR",
    )

    at(15)
    revoked_person = person(db, "diana")
    revoked_id, revoked_token = invite(api, caplog, admin, hogar_id, db.emails[revoked_person])
    ok(api("revocarInvitacion", admin, hogar_id=hogar_id, invitacion_id=revoked_id), 204)
    assert (db.invitation(revoked_id)["estado"], db.invitation(revoked_id)["respondida_en"]) == (
        "revocada",
        None,
    )
    error(
        api("revocarInvitacion", admin, hogar_id=hogar_id, invitacion_id=revoked_id),
        409,
        "INVITACION_NO_PENDIENTE",
    )
    error(
        api("resolverTokenInvitacion", revoked_person, {"token": revoked_token}),
        409,
        "INVITACION_NO_PENDIENTE",
    )
    assert ok(api("listarInvitacionesRecibidas", revoked_person))["invitaciones"] == []

    rejected_at = at(20)
    rejecting = person(db, "elena")
    with_profile(api, rejecting, "Elena")
    rejected_id, _ = invite(api, caplog, admin, hogar_id, db.emails[rejecting])
    ok(api("rechazarInvitacion", rejecting, invitacion_id=rejected_id), 204)
    assert (db.invitation(rejected_id)["estado"], db.invitation(rejected_id)["respondida_en"]) == (
        "rechazada",
        rejected_at,
    )
    error(
        api("aceptarInvitacion", rejecting, invitacion_id=rejected_id),
        409,
        "INVITACION_NO_PENDIENTE",
    )
    assert not [m for m in db.members_of(hogar_id) if m["usuario_id"] == rejecting]
    error(
        api("revocarInvitacion", admin, hogar_id=hogar_id, invitacion_id=uuid4()),
        404,
        "NO_ENCONTRADO",
    )


# --- vencimiento (DC-42) ------------------------------------------------------------------------


def test_expired_invitations_are_marked_and_do_not_block_a_new_one(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """DC-42: a los 7 días exactos la invitación vence y se marca 'expirada' al consultarse.

    Esperado: al listar recibidas → [] y la fila queda 'expirada' (sin `respondida_en`); aceptar
    otra vencida → 409 `INVITACION_EXPIRADA` y también queda 'expirada' (el marcado se confirma
    aunque la respuesta sea error); una vencida que nadie consultó no bloquea invitar de nuevo al
    mismo correo (`crearInvitacion` la marca antes): 201. Las vencidas no cuentan para el límite.
    """
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    first, second, third = (person(db, label) for label in ("fabio", "gloria", "hugo"))
    for usuario_id in (first, second):
        with_profile(api, usuario_id, "Persona")
    invited_at = at(5)
    first_id, _ = invite(api, caplog, admin, hogar_id, db.emails[first])
    second_id, second_token = invite(api, caplog, admin, hogar_id, db.emails[second])
    third_id, _ = invite(api, caplog, admin, hogar_id, db.emails[third])

    at(6, days=7)
    assert Clock.moment == invited_at + VALIDITY + timedelta(minutes=1)  # expira_en < ahora: vencida
    assert ok(api("listarInvitacionesRecibidas", first))["invitaciones"] == []
    assert (db.invitation(first_id)["estado"], db.invitation(first_id)["respondida_en"]) == (
        "expirada",
        None,
    )
    error(api("resolverTokenInvitacion", second, {"token": second_token}), 409, "INVITACION_EXPIRADA")
    assert db.invitation(second_id)["estado"] == "expirada"
    error(api("aceptarInvitacion", second, invitacion_id=second_id), 409, "INVITACION_NO_PENDIENTE")
    assert not [m for m in db.members_of(hogar_id) if m["usuario_id"] == second]
    assert db.invitation(third_id)["estado"] == "pendiente"  # vencida, aún sin consultar

    view = ok(api("listarMiembros", admin, hogar_id=hogar_id))
    assert view["invitaciones_pendientes"] == []  # las vencidas no se muestran
    again_id, _ = invite(api, caplog, admin, hogar_id, db.emails[third])
    assert db.invitation(third_id)["estado"] == "expirada"
    assert db.invitation(again_id)["estado"] == "pendiente"


def test_accepting_an_expired_invitation_is_409_and_marks_it(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Aceptar un minuto después de vencer → 409 `INVITACION_EXPIRADA`, 'expirada' confirmada, sin membresía
    ni alerta (DC-42, RN-X-05)."""
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    late = person(db, "ivan")
    with_profile(api, late, "Iván")
    at(5)
    invitacion_id, _ = invite(api, caplog, admin, hogar_id, db.emails[late])
    at(6, days=7)
    error(api("aceptarInvitacion", late, invitacion_id=invitacion_id), 409, "INVITACION_EXPIRADA")
    assert db.invitation(invitacion_id)["estado"] == "expirada"
    assert [m["usuario_id"] for m in db.members_of(hogar_id)] == [admin]
    assert db.household_alerts(hogar_id) == []


# --- correo, límite y conflictos --------------------------------------------------------------


def test_another_email_gets_403_correo_no_coincide(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Otra persona con el enlace (o el id) de una invitación ajena → 403 `CORREO_NO_COINCIDE` en
    resolver, aceptar y rechazar; la invitación sigue 'pendiente' y no se crea nada (RN-X-05)."""
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    invitee = person(db, "juana")
    intruder = person(db, "kevin")
    with_profile(api, intruder, "Kevin")
    at(5)
    invitacion_id, token = invite(api, caplog, admin, hogar_id, db.emails[invitee])
    before = db.snapshot()

    error(api("resolverTokenInvitacion", intruder, {"token": token}), 403, "CORREO_NO_COINCIDE")
    error(api("aceptarInvitacion", intruder, invitacion_id=invitacion_id), 403, "CORREO_NO_COINCIDE")
    error(api("rechazarInvitacion", intruder, invitacion_id=invitacion_id), 403, "CORREO_NO_COINCIDE")
    assert ok(api("listarInvitacionesRecibidas", intruder))["invitaciones"] == []
    error(api("resolverTokenInvitacion", intruder, {"token": token + "x"}), 404, "NO_ENCONTRADO")

    assert db.snapshot() == before
    assert db.invitation(invitacion_id)["estado"] == "pendiente"


def test_limit_of_five_counts_active_and_pending(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """RN-II-02: activos + pendientes vigentes ≥ 5 → 409 `LIMITE_MIEMBROS` al invitar.

    Esperado: administrador + 4 pendientes = 5 → la 5.ª invitación da 409 sin crear fila; una
    aceptada no cambia la cuenta (sigue 409); al revocar una pendiente se puede invitar (201).
    """
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    at(5)
    people = [person(db, f"persona{index}") for index in range(1, 6)]
    with_profile(api, people[0], "Persona Uno")
    ids = [invite(api, caplog, admin, hogar_id, db.emails[p])[0] for p in people[:4]]
    rows_before = len(db.rows("invitaciones_hogar"))

    body = {"correo_invitado": db.emails[people[4]]}
    error(api("crearInvitacion", admin, body, hogar_id=hogar_id), 409, "LIMITE_MIEMBROS")
    ok(api("aceptarInvitacion", people[0], invitacion_id=ids[0]))
    error(api("crearInvitacion", admin, body, hogar_id=hogar_id), 409, "LIMITE_MIEMBROS")
    assert len(db.rows("invitaciones_hogar")) == rows_before

    ok(api("revocarInvitacion", admin, hogar_id=hogar_id, invitacion_id=ids[3]), 204)
    invite(api, caplog, admin, hogar_id, db.emails[people[4]])
    view = ok(api("listarMiembros", admin, hogar_id=hogar_id))
    assert view["miembros_activos"] + len(view["invitaciones_pendientes"]) == MAX_MEMBERS


MAX_DAILY_INVITATIONS = 20  # D2 de la fase 10 (members_invitations.MAX_DAILY_INVITATIONS)


@each_personality
def test_daily_invitation_limit_uses_the_bogota_day(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    name: str,
) -> None:
    """D2 (decisión de Nicolás, RN-X-05): 20 invitaciones creadas hoy (Bogotá) → la 21.ª da 409.

    Esperado: el administrador crea 20 invitaciones el lunes 30/11 (19 revocadas y 1 pendiente:
    cuentan todas, en cualquier estado; así `LIMITE_MIEMBROS` no interviene). La 21.ª, a las
    19:30 (ya 01/12 en UTC) y a las 23:59 de Bogotá, responde 409 `LIMITE_INVITACIONES_DIARIO`
    con el mensaje de D2; no queda fila nueva, no se envía correo y el log no lleva enlace. A las
    00:00 del martes (Bogotá) vuelve a dejar invitar (201, correo con enlace).
    """
    assert members_service.MAX_DAILY_INVITATIONS == MAX_DAILY_INVITATIONS
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, name)
    created = []
    for number in range(1, MAX_DAILY_INVITATIONS + 1):
        at(number)
        invitacion_id, _token = invite(api, caplog, admin, hogar_id, f"limite{number}@example.com")
        created.append(invitacion_id)
        if number < MAX_DAILY_INVITATIONS:
            ok(api("revocarInvitacion", admin, hogar_id=hogar_id, invitacion_id=invitacion_id), 204)
    states = Counter(db.invitation(i)["estado"] for i in created)
    assert states == {"revocada": MAX_DAILY_INVITATIONS - 1, "pendiente": 1}

    body = {"correo_invitado": "veintiuno@example.com"}
    evening, last_minute = T0 + timedelta(minutes=440), T0 + timedelta(minutes=709)
    assert evening.astimezone(UTC).date() == T0.date() + timedelta(days=1)  # otro día en UTC
    for moment in (evening, last_minute):  # 19:30 y 23:59 del lunes en Bogotá
        Clock.moment = moment
        assert moment.astimezone(TIMEZONE).date() == T0.date()
        before = db.snapshot()
        sent, records = len(db.sent), len(caplog.records)
        refused = error(api("crearInvitacion", admin, body, hogar_id=hogar_id), 409,
                        "LIMITE_INVITACIONES_DIARIO")
        assert refused["mensaje"] == members_service.DAILY_LIMIT_MESSAGE
        assert db.snapshot() == before  # ni fila nueva ni ningún otro cambio
        assert len(db.sent) == sent
        new_records = caplog.records[records:]
        assert not [r for r in new_records if r.name == email_service.__name__]
        assert all(LINK_BASE not in r.getMessage() for r in new_records)

    next_day = at(710)  # martes 01/12 00:00 en Bogotá
    assert next_day.astimezone(TIMEZONE).timetuple()[:5] == (2026, 12, 1, 0, 0)
    invitacion_id, token = invite(api, caplog, admin, hogar_id, body["correo_invitado"])
    row = db.invitation(invitacion_id)
    assert (row["estado"], row["created_at"]) == ("pendiente", next_day)
    assert db.sent[-1][2] == LINK_BASE + token
    assert len(db.rows("invitaciones_hogar")) == MAX_DAILY_INVITATIONS + 1


def test_conflicts_when_inviting_and_accepting(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """409 `YA_ES_MIEMBRO`, `INVITACION_PENDIENTE_EXISTENTE` y `MEMBRESIA_ACTIVA_EXISTENTE`.

    Esperado: invitar el correo de un miembro activo (con otras mayúsculas) → `YA_ES_MIEMBRO`;
    invitar dos veces el mismo correo → `INVITACION_PENDIENTE_EXISTENTE` (DC-41); quien ya
    administra otro hogar puede ser invitado (contrato) pero al aceptar → 409
    `MEMBRESIA_ACTIVA_EXISTENTE` (RN-II-01), la invitación sigue 'pendiente' y no hay alerta. Un
    administrador de otro hogar no ve ni toca este (404, P-01, R-01).
    """
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    other_name = PERSONALITY_ORDER[0]
    other_admin, other_hogar = household(db, client, monkeypatch, other_name, tag="e2e9-otro")
    at(5)
    _member, membresia_id = join(api, db, caplog, admin, hogar_id, "lucia")
    alerts_before = len(db.household_alerts(hogar_id))

    for correo in ("LUCIA@example.com", ADMIN_EMAIL.upper()):
        error(
            api("crearInvitacion", admin, {"correo_invitado": correo}, hogar_id=hogar_id),
            409,
            "YA_ES_MIEMBRO",
        )
    pending = person(db, "mario")
    invite(api, caplog, admin, hogar_id, db.emails[pending])
    error(
        api("crearInvitacion", admin, {"correo_invitado": "MARIO@Example.com"}, hogar_id=hogar_id),
        409,
        "INVITACION_PENDIENTE_EXISTENTE",
    )

    at(10)
    cross_id, _ = invite(api, caplog, admin, hogar_id, db.emails[other_admin])
    error(
        api("aceptarInvitacion", other_admin, invitacion_id=cross_id),
        409,
        "MEMBRESIA_ACTIVA_EXISTENTE",
    )
    assert db.invitation(cross_id)["estado"] == "pendiente"
    assert len(db.household_alerts(hogar_id)) == alerts_before
    assert [m["hogar_id"] for m in db.members_of(other_hogar)] == [other_hogar]

    error(api("listarMiembros", other_admin, hogar_id=hogar_id), 404, "NO_ENCONTRADO")
    error(
        api("revocarInvitacion", other_admin, hogar_id=other_hogar, invitacion_id=cross_id),
        404,
        "NO_ENCONTRADO",
    )
    error(
        api("expulsarMiembro", other_admin, hogar_id=other_hogar, membresia_id=membresia_id),
        404,
        "NO_ENCONTRADO",
    )
    assert db.invitation(cross_id)["estado"] == "pendiente"
    assert db.membership(membresia_id)["estado"] == "activo"


# --- permisos de punta a punta (P-01, P-05) ---------------------------------------------------


def management_calls(
    hogar_id: UUID, membresia_id: UUID, invitacion_id: UUID
) -> list[tuple[str, Any, dict[str, UUID]]]:
    return [
        ("listarMiembros", NO_BODY, {"hogar_id": hogar_id}),
        ("salirDelHogar", NO_BODY, {"hogar_id": hogar_id}),
        ("actualizarPermisos", {"ver_historial": False}, {"hogar_id": hogar_id}),
        ("expulsarMiembro", NO_BODY, {"hogar_id": hogar_id, "membresia_id": membresia_id}),
        (
            "transferirAdministracion",
            NO_BODY,
            {"hogar_id": hogar_id, "membresia_id": membresia_id},
        ),
        ("crearInvitacion", {"correo_invitado": "nadie@example.com"}, {"hogar_id": hogar_id}),
        ("revocarInvitacion", NO_BODY, {"hogar_id": hogar_id, "invitacion_id": invitacion_id}),
    ]


def test_member_gets_403_on_management_and_outsider_gets_404(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """P-05: un miembro (con los 4 permisos) → 403 `NO_ES_ADMINISTRADOR` en las 5 de gestión.
    P-01: alguien con ficha y sin membresía → 404 `NO_ENCONTRADO` en las 7 con hogar.

    Esperado: ninguna de esas llamadas cambia nada (RN-X-08, RN-I-03).
    """
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    (admin_membership,) = [m["id"] for m in db.members_of(hogar_id)]
    at(5)
    member, _ = join(api, db, caplog, admin, hogar_id, "natalia")
    ok(api("actualizarPermisos", admin, {"modificar_metas": True}, hogar_id=hogar_id))
    invitacion_id, _ = invite(api, caplog, admin, hogar_id, "pendiente@example.com")
    outsider = person(db, "oscar")
    with_profile(api, outsider, "Óscar")
    before = db.snapshot()

    calls = management_calls(hogar_id, admin_membership, invitacion_id)
    for operation_id, body, ids in calls:
        if operation_id in MANAGEMENT_OPERATIONS:
            error(api(operation_id, member, body, **ids), 403, "NO_ES_ADMINISTRADOR")
        error(api(operation_id, outsider, body, **ids), 404, "NO_ENCONTRADO")
    assert {op for op, _, _ in calls} == set(HOUSEHOLD_OPERATIONS)
    assert db.snapshot() == before


# --- la carrera al eliminar la cuenta (RN-IX-09, DC-36, I-04) ---------------------------------


def test_accepting_in_the_gap_before_auth_deletion_is_404(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """La persona invitada pide `DELETE /usuarios/me`; entre el commit y el borrado en Supabase
    Auth (el token sigue vigente) llama a `POST /invitaciones/{id}/aceptar`.

    Esperado: la eliminación responde 204; la aceptación del hueco, 404 `NO_ENCONTRADO` (su ficha
    ya se borró en la transacción, RN-IX-09 y DC-36). Al final no hay ninguna membresía
    activa sin usuario (I-04), la persona no tiene membresías, la invitación sigue 'pendiente', no
    hay alerta «Nuevo miembro» y el hogar del administrador queda intacto.
    """
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    invitee = person(db, "paula")
    with_profile(api, invitee, "Paula")
    at(5)
    invitacion_id, _ = invite(api, caplog, admin, hogar_id, db.emails[invitee])
    household_before = {
        "hogar": db.committed["hogares"][hogar_id],
        "miembros": db.members_of(hogar_id),
        "datos": db.household_data(hogar_id),
    }
    in_the_gap: list[httpx.Response] = []

    def accept_in_the_gap() -> None:
        assert invitee not in db.committed["usuarios"]  # ya confirmado
        assert invitee in db.committed["auth_users"]  # Auth aún no la borró
        in_the_gap.append(api("aceptarInvitacion", invitee, invitacion_id=invitacion_id))

    db.gap_hooks.append(accept_in_the_gap)
    at(10)
    ok(api("eliminarCuenta", invitee), 204)

    (gap_response,) = in_the_gap
    error(gap_response, 404, "NO_ENCONTRADO")
    assert invitee not in db.committed["auth_users"]
    assert not [m for m in db.rows("hogar_miembros") if m["usuario_id"] == invitee]
    assert not [
        m for m in db.rows("hogar_miembros") if m["estado"] == "activo" and m["usuario_id"] is None
    ]
    assert db.invitation(invitacion_id)["estado"] == "pendiente"
    assert db.invitation(invitacion_id)["invitado_por"] == admin
    assert db.household_alerts(hogar_id) == []
    assert {
        "hogar": db.committed["hogares"][hogar_id],
        "miembros": db.members_of(hogar_id),
        "datos": db.household_data(hogar_id),
    } == household_before


def test_membership_accepted_just_before_locking_the_profile_is_closed_by_the_retry(
    client: TestClient,
    db: MembersStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Caso inverso: la eliminación empieza sin membresía y, justo antes de bloquear la ficha, la
    persona acepta una invitación (se confirma).

    Esperado: `delete_account` ve la membresía nueva al obtener el bloqueo de la ficha, hace
    rollback y repite la vuelta en el orden hogar → membresía → usuario; cierra la membresía
    (miembro con otros: el hogar sigue), borra la ficha y responde 204. Al final la membresía
    queda 'inactivo' con `fecha_salida` y `usuario_id` nulo (I-04), la invitación 'aceptada', el
    administrador sigue activo y Auth ya no tiene la cuenta.
    """
    api = Api(client, db)
    admin, hogar_id = household(db, client, monkeypatch, ONE_PERSONALITY)
    invitee = person(db, "ramiro")
    with_profile(api, invitee, "Ramiro")
    at(5)
    invitacion_id, _ = invite(api, caplog, admin, hogar_id, db.emails[invitee])
    accepted: list[httpx.Response] = []

    def accept_first() -> None:
        accepted.append(api("aceptarInvitacion", invitee, invitacion_id=invitacion_id))

    db.once_before("LOCK_USER_PROFILE_SQL", accept_first)
    deleted_at = at(10)
    db.events.clear()
    ok(api("eliminarCuenta", invitee), 204)

    (acceptance,) = accepted
    membresia_id = UUID(ok(acceptance)["membresia_id"])
    after_accept = db.events[db.events.index("commit") + 1 :]
    assert after_accept == [
        "LOCK_USER_PROFILE_SQL",
        "ACTIVE_MEMBERSHIP_OF_USER_SQL",  # apareció una membresía: rollback y otra vuelta
        "rollback",
        "ACTIVE_MEMBERSHIP_OF_USER_SQL",
        "LOCK_HOUSEHOLD_SQL",
        "ACTIVE_MEMBERSHIP_OF_USER_FOR_UPDATE_SQL",
        "LOCK_USER_PROFILE_SQL",
        "COUNT_OTHER_ACTIVE_MEMBERS_SQL",
        "CLOSE_MEMBERSHIP_SQL",
        "DELETE_USER_PROFILE_SQL",
        "commit",
        "delete_auth_user",
        "delete_avatar_files",
    ]
    closed = db.membership(membresia_id)
    assert (closed["estado"], closed["fecha_salida"], closed["usuario_id"]) == (
        "inactivo",
        deleted_at,
        None,
    )
    assert db.invitation(invitacion_id)["estado"] == "aceptada"
    assert [(m["usuario_id"], m["estado"]) for m in db.members_of(hogar_id) if m["estado"] == "activo"] == [
        (admin, "activo")
    ]
    assert hogar_id in db.committed["hogares"]
    assert invitee not in db.committed["auth_users"]
    assert invitee not in db.committed["usuarios"]
    assert not any(key[1] == invitee for key in db.committed["alertas_usuario"])

