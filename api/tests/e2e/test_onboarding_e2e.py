"""Onboarding de punta a punta (fase 4): router → seguridad → servicio → dominio → datos.

Sobre la app real (`create_app(make_test_settings())`, JWKS de prueba y tokens firmados en
memoria). Corren de verdad el router, la seguridad, el servicio, las reglas de zonas, el simulador
y **las funciones de `app.data`**; solo se reemplaza lo más bajo:

- `get_session` entrega una `StoreSession` por petición. Cada sentencia constante de `app.data`
  se reconoce por identidad y se resuelve sobre un almacén en memoria; una sentencia desconocida
  (por ejemplo, de alertas o consejos) hace fallar la prueba aunque el servicio la capture.
- El almacén imita READ COMMITTED: cada sesión ve lo confirmado más lo suyo y publica solo en
  `commit()`. Un error de una sentencia aborta la transacción (25P02 en las siguientes; `commit`
  ya no publica nada). Un INSERT que choca con `uq_miembros_usuario_activo` de otra transacción
  abierta espera a que termine, como en PostgreSQL.
- Restricciones de `supabase/migrations/` (0002 y 0003) que tocan estas operaciones: claves
  foráneas, `uq_miembros_usuario_activo`, `uq_miembros_admin_activo`, nombre de zona por hogar,
  una fuente por hogar, un sensor por zona, una lectura por sensor y hora, catálogos, kWh ≥ 0 con
  4 decimales y borrados en cascada.
- Supabase Auth y Storage (`app.services.supabase_admin`), que son otro servicio.

El SQL no se ejecuta: que PostgreSQL haga lo mismo queda pendiente (B-03, I-01, I-03 y R-*).

Reglas: RN-X-02, RN-X-03, RN-X-04, RN-IV-01, RN-IV-04, RN-IV-07, RN-II-01, RN-II-03, RN-IX-01,
RN-IX-09. Decisiones: DC-16, DC-33, DC-35, DC-36, DC-37, DC-38.
"""

import logging
import threading
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta, tzinfo
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, IntegrityError, InternalError, OperationalError

from app.config import Settings, get_settings
from app.data import alerts as alerts_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import readings as readings_data
from app.data import simulation_profiles as profiles_data
from app.data import tips as tips_data
from app.data import users as users_data
from app.data.database import get_session
from app.domain import alert_rules
from app.domain.formats import ZONE_NAMES
from app.domain.simulator import TIMEZONE, DegenerateRealizationError, engine
from app.domain.zone_rules import BASIC_ZONES, FALLBACK_PERSONALITY, HOUSING_TYPES, ZONE_TYPES
from app.main import API_PREFIX, create_app
from app.services import alerts_tips, live_alerts, supabase_admin
from app.services import onboarding as onboarding_service
from tests.data.fake_session import FakeResult
from tests.e2e.test_users_e2e import assert_error, call, email_of
from tests.helpers.auth import auth_header, install_test_jwks, make_test_settings, make_token
from tests.helpers.personalities import PERSONALITY_ORDER, load_personalities
from tests.simulator.support import final_profiles, frozen_references, read_csv, stable_id

USER_ID = UUID("e2e40000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("e2e40000-0000-4000-8000-000000000002")
HOUSEHOLD_NAME = "Casa de Laura"
PROFILE_BODY = {"nombre_completo": "Laura Gómez"}
DEFAULT_PERMISSIONS = {  # RN-II-03
    "ver_consumo_actual": True,
    "ver_historial": True,
    "recibir_alertas": True,
    "modificar_metas": False,
}
BACKFILL_ERROR_BODY = {
    "codigo": "BACKFILL_FALLIDO",
    "mensaje": onboarding_service.BACKFILL_FAILED_MESSAGE,
    "detalles": None,
}
# Texto de un error interno simulado: no debe salir en la respuesta ni en el log (S-01).
INTERNAL_DETAIL = f"detalle-interno-de-postgres {USER_ID} {HOUSEHOLD_NAME}"

# Reloj fijo: el backfill es noviembre de 2026 completo (hora de Bogotá), la misma ventana de la
# validación publicada por el Avance 03.
NOW = datetime(2026, 12, 1, 0, 10, tzinfo=TIMEZONE)
FIRST_HOUR = datetime(2026, 11, 1, tzinfo=TIMEZONE)
DAYS = [date(2026, 11, day) for day in range(1, 31)]
ROUNDING_KWH = Decimal("0.00005")  # por lectura: se guardan 4 decimales

# Hogar de referencia completo (vivienda y zonas) de cada personalidad.
REFERENCE_HOUSEHOLDS: dict[str, tuple[str, tuple[str, ...]]] = {
    name: (reference["vivienda"], tuple(reference["zonas"]))
    for name, reference in frozen_references().items()
}
HOUSEHOLD_TABLES = (
    "hogares",
    "hogar_miembros",
    "zonas",
    "fuentes_principales",
    "sensores_zona",
    "lecturas",
)
# Tablas de la fase 8 (alertas y consejos) y las metas: el onboarding no las toca (A-02); las
# usan los almacenes de la recuperación y de las alertas (`tests/e2e/alerts_store.py`).
ALERT_TABLES = ("metas_consumo", "alertas", "alertas_usuario", "consejos", "consejos_usuario")
# Tabla de la fase 9 (invitaciones): la usa el almacén de `test_members_e2e.py`.
MEMBER_TABLES = ("invitaciones_hogar",)
# Tabla de la fase 10 (tarifas): la usa el almacén de `test_consumption_e2e.py` (las metas ya
# están en ALERT_TABLES).
TARIFF_TABLES = ("tarifas_hogar",)
TABLES = (
    "auth_users",
    "usuarios",
    "preferencias_usuario",
    "perfiles_simulacion",
    *HOUSEHOLD_TABLES,
    *ALERT_TABLES,
    *MEMBER_TABLES,
    *TARIFF_TABLES,
)
# Filas de un solo hogar con las 4 zonas básicas (el cuerpo por defecto de `body_of`).
ONE_BASIC_HOUSEHOLD = {
    "hogares": 1,
    "hogar_miembros": 1,
    "zonas": 4,
    "fuentes_principales": 1,
    "sensores_zona": 4,
    "lecturas": 2880,
}
# Sentencias del onboarding, en el orden de RN-X-03.
ONBOARDING_STATEMENTS = (
    "ACTIVE_MEMBERSHIP_OF_USER_SQL",
    "PROFILES_BY_NAME_SQL",
    "INSERT_HOUSEHOLD_SQL",
    "INSERT_ADMIN_MEMBERSHIP_SQL",
    "INSERT_ZONES_SQL",
    "INSERT_MAIN_SOURCE_SQL",
    "INSERT_ZONE_SENSORS_SQL",
    "INSERT_READINGS_BATCH_SQL",
)
READINGS_STATEMENT = ONBOARDING_STATEMENTS[-1]
WAIT_SECONDS = 30

Row = dict[str, Any]
Tables = dict[str, dict[Any, Row]]
Params = Mapping[str, Any]

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)


class FixedDatetime(datetime):
    """`datetime.now()` del servicio congelado en NOW."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return NOW.astimezone(tz)


# --- almacén en memoria ---------------------------------------------------------------------


class PgError(Exception):
    """Error del controlador, con lo que lee la capa de datos: `pgcode` y `diag`."""

    def __init__(self, message: str, pgcode: str, constraint: str | None = None) -> None:
        super().__init__(message)
        self.pgcode = pgcode
        self.diag = SimpleNamespace(constraint_name=constraint)


class StoreSession:
    """Sesión de una petición. `changes` es su transacción: fila nueva o None (borrada)."""

    def __init__(self, db: Store) -> None:
        self.db = db
        self.changes: dict[str, dict[Any, Row | None]] = {table: {} for table in TABLES}
        self.unique_keys: set[tuple[Any, ...]] = set()
        self.aborted = False

    def exec(self, statement: Any, *, params: Params) -> FakeResult:
        return self.db.run(self, statement, params)

    def commit(self) -> None:
        self.db.commit(self)

    def rollback(self) -> None:
        self.db.events.append("rollback")
        self.db.end(self)

    def __getattr__(self, name: str) -> Any:
        raise self.db.unexpected_use(f"Session.{name}")


class Store:
    """Tablas confirmadas y el intérprete de las sentencias de `app.data` (ver el módulo)."""

    def __init__(self) -> None:
        self.committed: Tables = {table: {} for table in TABLES}
        self.sessions: list[StoreSession] = []
        self.events: list[str] = []  # sentencias por nombre, commit, rollback, Auth y Storage
        self.unexpected: list[str] = []
        self.lock = threading.Condition()
        self.waiting = threading.Event()  # alguien espera por un índice único
        self.fail_once: set[str] = set()  # sentencias (o `commit`) que fallan una sola vez
        self.before: dict[str, Callable[[], object]] = {}
        self.after: dict[str, Callable[[], object]] = {}
        for name, params in final_profiles().items():
            self._seed_simulation_profile(name, params)
        self.handlers = {
            id(getattr(module, name)): (name, handler)
            for module, name, handler in (
                (users_data, "USER_PROFILE_SQL", self._user_profile),
                # Fase 9: eliminarCuenta bloquea la ficha (`for update of u`) y la borra.
                (users_data, "LOCK_USER_PROFILE_SQL", self._user_profile),
                (users_data, "DELETE_USER_PROFILE_SQL", self._delete_user_profile),
                (users_data, "INSERT_USER_SQL", self._insert_user),
                (users_data, "INSERT_DEFAULT_PREFERENCES_SQL", self._insert_preferences),
                (memberships_data, "ACTIVE_MEMBERSHIP_OF_USER_SQL", self._active_membership),
                (
                    memberships_data,
                    "ACTIVE_MEMBERSHIP_OF_USER_FOR_UPDATE_SQL",
                    self._active_membership,
                ),
                (memberships_data, "COUNT_OTHER_ACTIVE_MEMBERS_SQL", self._count_others),
                (memberships_data, "CLOSE_MEMBERSHIP_SQL", self._close_membership),
                (memberships_data, "INSERT_ADMIN_MEMBERSHIP_SQL", self._insert_admin),
                (households_data, "LOCK_HOUSEHOLD_SQL", self._lock_household),
                (households_data, "DELETE_HOUSEHOLD_SQL", self._delete_household),
                (households_data, "INSERT_HOUSEHOLD_SQL", self._insert_household),
                (households_data, "INSERT_ZONES_SQL", self._insert_zones),
                (households_data, "INSERT_MAIN_SOURCE_SQL", self._insert_source),
                (households_data, "INSERT_ZONE_SENSORS_SQL", self._insert_sensors),
                (profiles_data, "PROFILES_BY_NAME_SQL", self._profiles_by_name),
                (readings_data, "INSERT_READINGS_BATCH_SQL", self._insert_readings),
            )
        }

    # --- semilla (ya confirmada) -------------------------------------------------------

    def _seed_simulation_profile(self, name: str, params: Params) -> None:
        """Como la devuelve el controlador: NUMERIC en Decimal y JSONB en dict."""
        row = {"id": uuid4(), **params}
        for column in profiles_data.NUMERIC_FIELDS:
            row[column] = Decimal(str(params[column])).quantize(Decimal("0.0001"))
            assert float(row[column]) == params[column], (name, column)  # cabe en la columna
        self.committed["perfiles_simulacion"][row["id"]] = row

    def profile_id(self, name: str) -> UUID:
        (profile_id,) = [r["id"] for r in self.rows("perfiles_simulacion") if r["nombre"] == name]
        return profile_id

    def deactivate_profile(self, name: str) -> None:
        profile_id = self.profile_id(name)
        table = self.committed["perfiles_simulacion"]
        table[profile_id] = {**table[profile_id], "activo": False}

    def seed_auth_user(self, usuario_id: UUID) -> None:
        self.committed["auth_users"][usuario_id] = {}

    def seed_user(self, usuario_id: UUID) -> None:
        """Usuario de Auth con ficha y preferencias por defecto."""
        self.seed_auth_user(usuario_id)
        self.committed["usuarios"][usuario_id] = self._new_user(usuario_id, "Laura Gómez", None)
        self.committed["preferencias_usuario"][usuario_id] = self._default_preferences()

    def seed_membership(self, usuario_id: UUID, rol: str, estado: str) -> UUID:
        """Hogar ya existente (sin zonas) con esta membresía; devuelve el id del hogar."""
        hogar_id, membresia_id = uuid4(), uuid4()
        self.committed["hogares"][hogar_id] = {
            "id": hogar_id,
            "nombre": "Hogar anterior",
            "tipo_vivienda": "casa",
            "perfil_simulacion_id": self.profile_id(FALLBACK_PERSONALITY),
            "permiso_recibir_alertas": True,
            "created_at": FIRST_HOUR,
        }
        self.committed["hogar_miembros"][membresia_id] = {
            "id": membresia_id,
            "hogar_id": hogar_id,
            "usuario_id": usuario_id,
            "rol": rol,
            "estado": estado,
            "fecha_ingreso": FIRST_HOUR,
            "fecha_salida": None if estado == "activo" else NOW,
        }
        return hogar_id

    # --- lo que miran las pruebas ------------------------------------------------------

    def snapshot(self) -> Tables:
        # Copia superficial: las filas nunca se modifican, se reemplazan.
        return {table: dict(rows) for table, rows in self.committed.items()}

    def rows(self, table: str) -> list[Row]:
        return list(self.committed[table].values())

    def household_rows(self) -> dict[str, int]:
        return {table: len(self.committed[table]) for table in HOUSEHOLD_TABLES}

    def zones_by_sensor(self) -> dict[UUID, str]:
        zones = {row["id"]: row["tipo"] for row in self.rows("zonas")}
        return {row["id"]: zones[row["zona_id"]] for row in self.rows("sensores_zona")}

    def unexpected_use(self, what: str) -> AssertionError:
        self.unexpected.append(what)
        return AssertionError(f"uso no previsto: {what}")

    # --- transacción -------------------------------------------------------------------

    def open_session(self) -> StoreSession:
        session = StoreSession(self)
        self.sessions.append(session)
        return session

    def run(self, session: StoreSession, statement: Any, params: Params) -> FakeResult:
        if id(statement) not in self.handlers:
            raise self.unexpected_use(f"sentencia desconocida: {statement}")
        name, handler = self.handlers[id(statement)]
        if set(statement._bindparams) != set(params):
            raise self.unexpected_use(f"parámetros de {name}: {sorted(params)}")
        self.before.get(name, lambda: None)()
        with self.lock:
            self.record(session, name)
            try:
                if session.aborted:
                    raise PgError("current transaction is aborted", "25P02")
                if name != READINGS_STATEMENT:  # la de lecturas falla a mitad del lote
                    self._fail_if_asked(name)
                result = handler(session, params)
            except PgError as exc:
                session.aborted = True
                raise self._sqlalchemy_error(statement, params, exc) from exc
        self.after.get(name, lambda: None)()
        return result

    def record(self, _session: StoreSession, name: str) -> None:
        """Anota la sentencia en `events` (el almacén de la recuperación la redirige)."""
        self.events.append(name)

    def _fail_if_asked(self, name: str) -> None:
        if name in self.fail_once:
            self.fail_once.discard(name)
            raise PgError(INTERNAL_DETAIL, "57P01")

    @staticmethod
    def _sqlalchemy_error(statement: Any, params: Params, exc: PgError) -> DBAPIError:
        if exc.pgcode.startswith("23"):
            return IntegrityError(str(statement), dict(params), exc)
        cls = InternalError if exc.pgcode == "25P02" else OperationalError
        return cls(str(statement), dict(params), exc)

    def commit(self, session: StoreSession) -> None:
        with self.lock:
            if "commit" in self.fail_once:
                self.fail_once.discard("commit")
                self.events.append("commit-fallido")
                session.aborted = True
                raise OperationalError("COMMIT", {}, PgError(INTERNAL_DETAIL, "08006"))
            if not session.aborted:  # una transacción abortada no publica nada
                for table, changes in session.changes.items():
                    for key, row in changes.items():
                        if row is None:
                            self.committed[table].pop(key, None)
                        else:
                            self.committed[table][key] = row
                self.events.append("commit")
            self.end(session)

    def end(self, session: StoreSession) -> None:
        """Fin de la transacción: descarta lo pendiente y suelta los índices únicos."""
        with self.lock:
            session.changes = {table: {} for table in TABLES}
            session.unique_keys.clear()
            session.aborted = False
            self.lock.notify_all()

    def view(self, session: StoreSession, table: str) -> dict[Any, Row]:
        """READ COMMITTED: lo confirmado ahora mismo más lo de la propia transacción."""
        rows = {**self.committed[table], **session.changes[table]}
        return {key: row for key, row in rows.items() if row is not None}

    @staticmethod
    def put(session: StoreSession, table: str, key: Any, row: Row | None) -> None:
        session.changes[table][key] = row

    def _claim_unique(self, session: StoreSession, key: tuple[Any, ...]) -> None:
        """Espera a las transacciones abiertas que ya insertaron esa clave."""

        def is_free() -> bool:
            return not any(key in s.unique_keys for s in self.sessions if s is not session)

        if not is_free():
            self.waiting.set()
            if not self.lock.wait_for(is_free, timeout=WAIT_SECONDS):
                raise self.unexpected_use(f"espera sin fin por {key[0]}")
        session.unique_keys.add(key)

    @staticmethod
    def _require(condition: object, pgcode: str, constraint: str) -> None:
        if not condition:
            # Como Postgres: el mensaje lleva datos que no deben salir de la API.
            raise PgError(f"{constraint} DETAIL: {INTERNAL_DETAIL}", pgcode, constraint)

    # --- usuarios ----------------------------------------------------------------------

    @staticmethod
    def _new_user(usuario_id: UUID, nombre: str, telefono: str | None) -> Row:
        return {
            "id": usuario_id,
            "nombre_completo": nombre,
            "telefono": telefono,
            "avatar_url": None,
        }

    @staticmethod
    def _default_preferences() -> Row:
        return {"notif_consumo": True, "notif_consejos": True, "base_comparacion": "promedio"}

    def _user_profile(self, session: StoreSession, params: Params) -> FakeResult:
        user = self.view(session, "usuarios").get(params["usuario_id"])
        preferences = self.view(session, "preferencias_usuario").get(params["usuario_id"])
        if user is None or preferences is None:
            return FakeResult()
        return FakeResult([{**user, **preferences}])

    def _insert_user(self, session: StoreSession, params: Params) -> FakeResult:
        usuario_id = params["usuario_id"]
        self._require(usuario_id in self.view(session, "auth_users"), "23503", "usuarios_id_fkey")
        if usuario_id in self.view(session, "usuarios"):
            return FakeResult()
        row = self._new_user(usuario_id, params["nombre_completo"], params["telefono"])
        self.put(session, "usuarios", usuario_id, row)
        return FakeResult([{"id": usuario_id}])

    def _delete_user_profile(self, session: StoreSession, params: Params) -> FakeResult:
        """DELETE FROM usuarios … RETURNING id, con las acciones de las claves foráneas de 0002.

        Cascada: preferencias_usuario, alertas_usuario y consejos_usuario. SET NULL:
        hogar_miembros.usuario_id (la verificación miembros_activo_con_usuario rechaza dejar una
        membresía ACTIVA sin usuario: 23514) e invitaciones_hogar.invitado_por (DC-36).
        """
        usuario_id = params["usuario_id"]
        if usuario_id not in self.view(session, "usuarios"):
            return FakeResult()
        members = self.view(session, "hogar_miembros")
        for key, row in members.items():
            if row["usuario_id"] != usuario_id:
                continue
            self._require(row["estado"] != "activo", "23514", "miembros_activo_con_usuario")
            self.put(session, "hogar_miembros", key, {**row, "usuario_id": None})
        for key, row in self.view(session, "invitaciones_hogar").items():
            if row["invitado_por"] == usuario_id:
                self.put(session, "invitaciones_hogar", key, {**row, "invitado_por": None})
        for table in ("alertas_usuario", "consejos_usuario"):
            for key, row in self.view(session, table).items():
                if row["usuario_id"] == usuario_id:
                    self.put(session, table, key, None)
        self.put(session, "preferencias_usuario", usuario_id, None)
        self.put(session, "usuarios", usuario_id, None)
        return FakeResult([{"id": usuario_id}], rowcount=1)

    def _insert_preferences(self, session: StoreSession, params: Params) -> FakeResult:
        usuario_id = params["usuario_id"]
        self.put(session, "preferencias_usuario", usuario_id, self._default_preferences())
        return FakeResult(rowcount=1)

    # --- membresías --------------------------------------------------------------------

    def _active_membership(self, session: StoreSession, params: Params) -> FakeResult:
        return FakeResult(
            [
                {"membresia_id": row["id"], "hogar_id": row["hogar_id"], "rol": row["rol"]}
                for row in self.view(session, "hogar_miembros").values()
                if row["usuario_id"] == params["usuario_id"] and row["estado"] == "activo"
            ]
        )

    def _count_others(self, session: StoreSession, params: Params) -> FakeResult:
        total = sum(
            row["hogar_id"] == params["hogar_id"]
            and row["estado"] == "activo"
            and row["usuario_id"] != params["usuario_id"]
            for row in self.view(session, "hogar_miembros").values()
        )
        return FakeResult([{"total": total}])

    def _close_membership(self, session: StoreSession, params: Params) -> FakeResult:
        row = self.view(session, "hogar_miembros")[params["membresia_id"]]
        closed = {**row, "estado": "inactivo", "fecha_salida": params["closed_at"]}
        self.put(session, "hogar_miembros", row["id"], closed)
        return FakeResult(rowcount=1)

    def _insert_admin(self, session: StoreSession, params: Params) -> FakeResult:
        hogar_id, usuario_id = params["hogar_id"], params["usuario_id"]
        self._claim_unique(session, ("uq_miembros_usuario_activo", usuario_id))
        members = self.view(session, "hogar_miembros").values()
        active = [row for row in members if row["estado"] == "activo"]
        users = {row["usuario_id"] for row in active}
        administered = {row["hogar_id"] for row in active if row["rol"] == "administrador"}
        self._require(usuario_id not in users, "23505", "uq_miembros_usuario_activo")
        self._require(hogar_id not in administered, "23505", "uq_miembros_admin_activo")
        self._require(
            usuario_id in self.view(session, "usuarios"), "23503", "hogar_miembros_usuario_id_fkey"
        )
        self._require(
            hogar_id in self.view(session, "hogares"), "23503", "hogar_miembros_hogar_id_fkey"
        )
        membresia_id = uuid4()
        row = {
            "id": membresia_id,
            "hogar_id": hogar_id,
            "usuario_id": usuario_id,
            "rol": "administrador",
            "estado": "activo",
            "fecha_ingreso": params["joined_at"],
            "fecha_salida": None,
        }
        self.put(session, "hogar_miembros", membresia_id, row)
        return FakeResult(rowcount=1)

    # --- hogares, zonas, fuente y sensores ---------------------------------------------

    def _lock_household(self, session: StoreSession, params: Params) -> FakeResult:
        found = params["hogar_id"] in self.view(session, "hogares")
        return FakeResult([{"id": params["hogar_id"]}] if found else [])

    def _delete_household(self, session: StoreSession, params: Params) -> FakeResult:
        """Cascada de 0002: miembros, invitaciones, zonas, fuente, sensores y lecturas."""
        parents = {params["hogar_id"]}
        self.put(session, "hogares", params["hogar_id"], None)
        for table, column in (
            ("hogar_miembros", "hogar_id"),
            ("invitaciones_hogar", "hogar_id"),
            ("fuentes_principales", "hogar_id"),
            ("zonas", "hogar_id"),
            ("sensores_zona", "zona_id"),
            ("lecturas", "sensor_id"),
        ):
            rows = self.view(session, table)
            children = {key for key, row in rows.items() if row[column] in parents}
            for key in children:
                self.put(session, table, key, None)
            if table in ("zonas", "sensores_zona"):
                parents = children
        # Tarifas, metas, alertas y consejos del hogar, con sus entregas y seguimientos (0002).
        removed: dict[str, set[Any]] = {}
        for table, column in (("tarifas_hogar", "hogar_id"), ("metas_consumo", "hogar_id"),
                              ("alertas", "hogar_id"), ("consejos", "hogar_id")):
            rows = self.view(session, table)
            removed[table] = {k for k, row in rows.items() if row[column] == params["hogar_id"]}
            for key in removed[table]:
                self.put(session, table, key, None)
        for table, column, parent in (("alertas_usuario", "alerta_id", "alertas"),
                                      ("consejos_usuario", "consejo_id", "consejos")):
            for key, row in self.view(session, table).items():
                if row[column] in removed[parent]:
                    self.put(session, table, key, None)
        return FakeResult(rowcount=1)

    def _insert_household(self, session: StoreSession, params: Params) -> FakeResult:
        hogar_id, tipo, perfil_id = (
            params["hogar_id"],
            params["tipo_vivienda"],
            params["perfil_simulacion_id"],
        )
        self._require(hogar_id not in self.view(session, "hogares"), "23505", "hogares_pkey")
        self._require(params["nombre"] is not None, "23502", "hogares_nombre")
        self._require(tipo in HOUSING_TYPES, "23514", "hogares_tipo_vivienda_check")
        self._require(
            perfil_id in self.view(session, "perfiles_simulacion"),
            "23503",
            "hogares_perfil_simulacion_id_fkey",
        )
        returning = {
            "id": hogar_id,
            "nombre": params["nombre"],
            "tipo_vivienda": tipo,
            # Valores por defecto de la tabla (RN-II-03).
            "permiso_ver_consumo_actual": True,
            "permiso_ver_historial": True,
            "permiso_recibir_alertas": True,
            "permiso_modificar_metas": False,
        }
        row = {
            **returning,
            "perfil_simulacion_id": perfil_id,
            # `default now()`: el instante de la transacción, que es el reloj (fijo) del servicio.
            "created_at": onboarding_service.datetime.now(UTC),
        }
        self.put(session, "hogares", hogar_id, row)
        return FakeResult([returning], rowcount=1)

    def _insert_zones(self, session: StoreSession, params: Params) -> FakeResult:
        hogar_id = params["hogar_id"]
        self._require(hogar_id in self.view(session, "hogares"), "23503", "zonas_hogar_id_fkey")
        rows = list(zip(params["zona_ids"], params["nombres"], params["tipos"], strict=True))
        for zona_id, nombre, tipo in rows:
            zones = self.view(session, "zonas").values()
            names = {(zone["hogar_id"], zone["nombre"]) for zone in zones}
            self._require((hogar_id, nombre) not in names, "23505", "zonas_nombre_unico_por_hogar")
            self._require(tipo in ZONE_TYPES, "23514", "zonas_tipo_check")
            row = {
                "id": UUID(zona_id),
                "hogar_id": hogar_id,
                "nombre": nombre,
                "tipo": tipo,
                "estado": "activa",
            }
            self.put(session, "zonas", row["id"], row)
        return FakeResult(rowcount=len(rows))

    def _insert_source(self, session: StoreSession, params: Params) -> FakeResult:
        hogar_id = params["hogar_id"]
        self._require(
            hogar_id in self.view(session, "hogares"), "23503", "fuentes_principales_hogar_id_fkey"
        )
        owners = {row["hogar_id"] for row in self.view(session, "fuentes_principales").values()}
        self._require(hogar_id not in owners, "23505", "fuentes_principales_hogar_id_key")
        row = {
            "id": params["fuente_id"],
            "hogar_id": hogar_id,
            "nombre": params["nombre"],
            "estado": "activa",
        }
        self.put(session, "fuentes_principales", row["id"], row)
        return FakeResult(rowcount=1)

    def _insert_sensors(self, session: StoreSession, params: Params) -> FakeResult:
        """INSERT … SELECT: solo zonas y fuente del mismo hogar producen fila (DC-38)."""
        hogar_id, fuente_id = params["hogar_id"], params["fuente_id"]
        source = self.view(session, "fuentes_principales").get(fuente_id)
        inserted = 0
        for sensor_id, zona_id in zip(params["sensor_ids"], params["zona_ids"], strict=True):
            zone = self.view(session, "zonas").get(UUID(zona_id))
            if zone is None or source is None:
                continue
            if zone["hogar_id"] != hogar_id or source["hogar_id"] != hogar_id:
                continue
            taken = {row["zona_id"] for row in self.view(session, "sensores_zona").values()}
            self._require(zone["id"] not in taken, "23505", "sensores_zona_zona_id_key")
            row = {
                "id": UUID(sensor_id),
                "zona_id": zone["id"],
                "fuente_principal_id": fuente_id,
                "estado": "activo",
            }
            self.put(session, "sensores_zona", row["id"], row)
            inserted += 1
        return FakeResult(rowcount=inserted)

    # --- perfiles y lecturas -----------------------------------------------------------

    def _profiles_by_name(self, session: StoreSession, params: Params) -> FakeResult:
        rows = self.view(session, "perfiles_simulacion").values()
        return FakeResult([row for row in rows if row["nombre"] in params["nombres"]])

    def _insert_readings(self, session: StoreSession, params: Params) -> FakeResult:
        """ON CONFLICT (sensor_id, fecha_hora) DO NOTHING; guarda el instante en UTC."""
        sensors = self.view(session, "sensores_zona")
        existing = set(self.view(session, "lecturas"))
        rows = list(
            zip(
                params["sensor_ids"],
                params["fechas_hora"],
                params["consumos_kwh"],
                params["calidades"],
                strict=True,
            )
        )
        inserted = 0
        for number, (sensor_text, fecha_hora, consumo_kwh, calidad) in enumerate(rows):
            if number == len(rows) // 2:  # con la primera mitad del lote ya escrita
                self._fail_if_asked(READINGS_STATEMENT)
            sensor_id = UUID(sensor_text)
            self._require(sensor_id in sensors, "23503", "lecturas_sensor_id_fkey")
            self._require(consumo_kwh >= 0, "23514", "lecturas_consumo_kwh_check")
            self._require(
                calidad in ("simulada", "estimada", "real"), "23514", "lecturas_calidad_check"
            )
            key = (sensor_id, fecha_hora.astimezone(UTC))
            if key in existing:
                continue
            existing.add(key)
            row = {
                "sensor_id": sensor_id,
                "fecha_hora": key[1],
                "consumo_kwh": consumo_kwh.quantize(Decimal("0.0001")),
                "calidad": calidad,
            }
            self.put(session, "lecturas", key, row)
            inserted += 1
        return FakeResult(rowcount=inserted)

    # --- app.services.supabase_admin (fuera de la transacción) ---------------------------

    def delete_auth_user(self, _settings: Settings, usuario_id: UUID) -> None:
        """DC-36: cascada a la ficha y las preferencias; las membresías quedan sin usuario."""
        self.events.append("delete_auth_user")
        for table in ("auth_users", "usuarios", "preferencias_usuario"):
            self.committed[table].pop(usuario_id, None)
        for table in ("alertas_usuario", "consejos_usuario"):  # cascada desde usuarios
            rows = self.committed[table]
            for key in [k for k, row in rows.items() if row["usuario_id"] == usuario_id]:
                del rows[key]
        members = self.committed["hogar_miembros"]
        for key, row in list(members.items()):
            if row["usuario_id"] == usuario_id:
                assert row["estado"] != "activo", "miembros_activo_con_usuario"
                members[key] = {**row, "usuario_id": None}

    def delete_avatar_files(self, _settings: Settings, _usuario_id: UUID) -> None:
        self.events.append("delete_avatar_files")


# --- app y cliente --------------------------------------------------------------------------


def forbid_alerts_and_tips(monkeypatch: pytest.MonkeyPatch, store: Store) -> list[str]:
    """DC-35: toda función de alertas o consejos falla (y queda anotada) si alguien la llama."""

    def forbidden(name: str) -> Callable[..., Any]:
        def fail(*_args: Any, **_kwargs: Any) -> None:
            raise store.unexpected_use(f"{name} (DC-35)")

        return fail

    guarded = []
    for module in (alerts_data, tips_data, alert_rules, alerts_tips, live_alerts):
        for name, value in list(vars(module).items()):
            if callable(value) and getattr(value, "__module__", "") == module.__name__:
                monkeypatch.setattr(module, name, forbidden(f"{module.__name__}.{name}"))
                guarded.append(name)
    return guarded


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Store]:
    store = Store()
    monkeypatch.setattr(supabase_admin, "delete_auth_user", store.delete_auth_user)
    monkeypatch.setattr(supabase_admin, "delete_avatar_files", store.delete_avatar_files)
    monkeypatch.setattr(onboarding_service, "datetime", FixedDatetime)
    # La vigilancia no puede quedar vacía.
    guarded = forbid_alerts_and_tips(monkeypatch, store)
    assert {"evaluate_alert_rules", "build_tips", "evaluate_live_hours"} <= set(guarded)
    install_test_jwks(monkeypatch)
    yield store
    # El servicio captura cualquier excepción: lo inesperado se comprueba aquí.
    assert store.unexpected == []


@pytest.fixture
def app(db: Store) -> Iterator[FastAPI]:
    app = create_app(make_test_settings())
    app.dependency_overrides[get_settings] = make_test_settings

    def session_override() -> Iterator[StoreSession]:
        session = db.open_session()
        try:
            yield session
        finally:
            db.end(session)  # cerrar sin commit descarta lo pendiente

    app.dependency_overrides[get_session] = session_override
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def body_of(housing: str = "apartamento", zones: Any = BASIC_ZONES, **extra: Any) -> dict[str, Any]:
    body = {"nombre_hogar": HOUSEHOLD_NAME, "tipo_vivienda": housing, "zonas": list(zones)}
    return {**body, **extra}


def onboard(client: TestClient, user_id: UUID, body: Any = None) -> httpx.Response:
    """`crearHogarOnboarding`; `call` valida la respuesta contra el contrato."""
    return call(client, "crearHogarOnboarding", user_id, body or body_of())


def use_household_id(monkeypatch: pytest.MonkeyPatch, hogar_id: UUID) -> None:
    """El primer id que genera el servicio es el del hogar; los demás siguen siendo al azar."""
    ids = iter([hogar_id])
    monkeypatch.setattr(onboarding_service, "uuid4", lambda: next(ids, None) or uuid4())


def assert_backfill_failed(response: httpx.Response) -> None:
    """500 con el cuerpo exacto: nada de la excepción interna (RN-X-03, S-01)."""
    assert response.status_code == 500, response.text
    assert response.json() == BACKFILL_ERROR_BODY


def assert_no_profile(response: httpx.Response) -> None:
    """404 `FICHA_NO_CREADA` declarado en el contrato 0.2.8, sin rastro de la causa."""
    assert response.status_code == 404, response.text
    body = response.json()
    assert body["codigo"] == "FICHA_NO_CREADA"
    assert str(USER_ID) not in response.text and "23503" not in response.text


# --- las 5 personalidades -------------------------------------------------------------------


@each_personality
def test_reference_household_is_created_with_its_backfill(
    client: TestClient, db: Store, name: str
) -> None:
    """201 y 720 × zonas lecturas, solo de las zonas elegidas (RN-X-03, RN-IV-01, RN-IV-07).

    Además: un solo lote (DC-33), una transacción, zonas, fuente y sensores del mismo hogar
    (DC-38) y el perfil de la personalidad esperada (RN-X-04).
    """
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    assert set(zones) <= set(load_personalities()[name].zone_kwh_per_day)
    db.seed_user(USER_ID)

    response = onboard(client, USER_ID, body_of(housing, zones))

    assert response.status_code == 201, response.text
    assert db.events == [*ONBOARDING_STATEMENTS, "commit"]
    assert len(db.sessions) == 1

    (household,) = db.rows("hogares")
    (member,) = db.rows("hogar_miembros")
    (source,) = db.rows("fuentes_principales")
    assert household["perfil_simulacion_id"] == db.profile_id(name)
    assert (household["nombre"], household["tipo_vivienda"]) == (HOUSEHOLD_NAME, housing)
    assert member["hogar_id"] == source["hogar_id"] == household["id"]
    assert member["usuario_id"] == USER_ID
    assert (member["rol"], member["estado"]) == ("administrador", "activo")
    assert (member["fecha_ingreso"], member["fecha_salida"]) == (NOW, None)
    assert source["nombre"] == f"Fuente principal {HOUSEHOLD_NAME}"
    assert {row["hogar_id"] for row in db.rows("zonas")} == {household["id"]}
    expected_names = {zone: ZONE_NAMES[zone] for zone in zones}
    assert {row["tipo"]: row["nombre"] for row in db.rows("zonas")} == expected_names
    assert {row["fuente_principal_id"] for row in db.rows("sensores_zona")} == {source["id"]}

    readings = db.rows("lecturas")
    assert len(readings) == 720 * len(zones)
    assert {row["calidad"] for row in readings} == {"simulada"}
    zone_of = db.zones_by_sensor()
    hours: dict[str, set[datetime]] = defaultdict(set)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in readings:
        hours[zone_of[row["sensor_id"]]].add(row["fecha_hora"])
        totals[zone_of[row["sensor_id"]]] += row["consumo_kwh"]
    expected_hours = {FIRST_HOUR + timedelta(hours=offset) for offset in range(720)}
    assert hours == dict.fromkeys(zones, expected_hours)
    assert all(total > 0 for total in totals.values())


@each_personality
def test_response_is_the_contract_household_without_the_personality(
    client: TestClient, db: Store, name: str
) -> None:
    """`Hogar` exacto, con los permisos por defecto y sin la personalidad (RN-X-04, RN-II-03)."""
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    db.seed_user(USER_ID)

    response = onboard(client, USER_ID, body_of(housing, zones))

    assert response.status_code == 201, response.text
    (household,) = db.rows("hogares")
    assert response.json() == {
        "id": str(household["id"]),
        "nombre": HOUSEHOLD_NAME,
        "tipo_vivienda": housing,
        "rol_usuario": "administrador",
        "permisos": DEFAULT_PERMISSIONS,
    }
    secrets = [word for personality in PERSONALITY_ORDER for word in personality.split()]
    secrets += [str(row["id"]) for row in db.rows("perfiles_simulacion")]
    exposed = response.text + str(response.headers)
    assert not [secret for secret in secrets if secret in exposed]


def test_monthly_consumption_is_the_published_one_and_respects_the_order(
    client: TestClient, db: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """compacto < eficiente < intermedio < familiar < amplio, en un mismo almacén.

    Con los ids de hogar `val-000` del Avance 03 y noviembre de 2026, lo guardado suma el total
    publicado de cada personalidad (salvo el redondeo a 4 decimales de cada lectura) y queda a
    ±10 % de su objetivo congelado (CE03).
    """
    published = {
        row["personalidad"]: Decimal(row["total_kwh"])
        for row in read_csv("validacion_totales_por_semilla.csv")
        if row["semilla"] == "val-000"
    }
    totals = []
    for number, name in enumerate(PERSONALITY_ORDER, start=1):
        user_id = UUID(int=USER_ID.int + number)
        db.seed_user(user_id)
        hogar_id = stable_id("hogar", f"val|{name}|val-000")
        use_household_id(monkeypatch, hogar_id)
        housing, zones = REFERENCE_HOUSEHOLDS[name]

        response = onboard(client, user_id, body_of(housing, zones))

        assert response.status_code == 201, response.text
        assert response.json()["id"] == str(hogar_id)
        zone_ids = {row["id"] for row in db.rows("zonas") if row["hogar_id"] == hogar_id}
        sensors = {row["id"] for row in db.rows("sensores_zona") if row["zona_id"] in zone_ids}
        values = [r["consumo_kwh"] for r in db.rows("lecturas") if r["sensor_id"] in sensors]
        assert len(values) == 720 * len(zones)
        total = sum(values, Decimal(0))
        assert abs(total - published[name]) <= ROUNDING_KWH * len(values), name
        target = Decimal(frozen_references()[name]["objetivo_validacion_kwh"])
        assert abs(total / target - 1) <= Decimal("0.10"), name
        totals.append(total)
    assert totals == sorted(totals)
    assert len(set(totals)) == len(PERSONALITY_ORDER)


@each_personality
def test_daily_consumption_stays_in_the_band_of_its_averages(
    client: TestClient, db: Store, name: str
) -> None:
    """Cada día y zona: promedio × fin de semana × [humor mínimo, humor máximo].

    Los picos solo suman: el techo se comprueba en las zonas que no los tienen.
    """
    personality = load_personalities()[name]
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    zones_with_peaks = set(final_profiles()[name]["picos_config"])
    db.seed_user(USER_ID)
    assert onboard(client, USER_ID, body_of(housing, zones)).status_code == 201

    zone_of = db.zones_by_sensor()
    daily: dict[tuple[str, date], Decimal] = defaultdict(Decimal)
    for row in db.rows("lecturas"):
        day = row["fecha_hora"].astimezone(TIMEZONE).date()
        daily[zone_of[row["sensor_id"]], day] += row["consumo_kwh"]

    assert set(daily) == {(zone, day) for zone in zones for day in DAYS}
    tolerance = 24 * float(ROUNDING_KWH)
    for (zone, day), kwh in daily.items():
        factor = personality.weekend_factor if day.weekday() >= 5 else 1.0
        expected = personality.zone_kwh_per_day[zone] * factor
        assert float(kwh) >= expected * personality.humor_min - tolerance, (zone, day)
        if zone not in zones_with_peaks:
            assert float(kwh) <= expected * personality.humor_max + tolerance, (zone, day)


def test_duplex_with_nine_zones_saves_6480_readings(client: TestClient, db: Store) -> None:
    """B-01 de punta a punta: 9 zonas, 6.480 lecturas sin duplicados y un solo lote (DC-33)."""
    db.seed_user(USER_ID)
    assert onboard(client, USER_ID, body_of("duplex", ZONE_TYPES)).status_code == 201
    assert len(db.rows("lecturas")) == 6480  # la clave es (sensor, hora)
    assert len(db.rows("sensores_zona")) == 9
    assert db.events.count(READINGS_STATEMENT) == 1


@pytest.mark.parametrize("name", [n for n in PERSONALITY_ORDER if n != FALLBACK_PERSONALITY])
def test_inactive_personality_falls_back_to_the_efficient_one(
    client: TestClient, db: Store, name: str
) -> None:
    """RN-X-04: con la personalidad inactiva se usa *Consumo eficiente*."""
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    db.seed_user(USER_ID)
    db.deactivate_profile(name)

    assert onboard(client, USER_ID, body_of(housing, zones)).status_code == 201

    (household,) = db.rows("hogares")
    assert household["perfil_simulacion_id"] == db.profile_id(FALLBACK_PERSONALITY)
    assert len(db.rows("lecturas")) == 720 * len(zones)


@each_personality
def test_backfill_does_not_touch_alerts_nor_tips(client: TestClient, db: Store, name: str) -> None:
    """DC-35: ni una función ni una sentencia de alertas o consejos durante el backfill.

    Las funciones quedan vigiladas en la fixture `db`; una sentencia que no es del onboarding ni
    de la ficha es «desconocida». Ambas cosas se anotan en `db.unexpected`.
    """
    db.seed_user(USER_ID)
    assert onboard(client, USER_ID, body_of(*REFERENCE_HOUSEHOLDS[name])).status_code == 201
    assert db.unexpected == []
    assert set(db.events) == {*ONBOARDING_STATEMENTS, "commit"}


def test_the_guard_detects_alerts_and_unknown_statements(db: Store) -> None:
    """La vigilancia de DC-35 sí detecta una llamada o una sentencia ajena (y la anota)."""
    with pytest.raises(AssertionError):
        alert_rules.evaluate_alert_rules({})
    with pytest.raises(AssertionError):
        db.open_session().exec("insert into alertas", params={})
    assert len(db.unexpected) == 2
    db.unexpected.clear()


# --- autenticación y entrada ----------------------------------------------------------------


@pytest.mark.parametrize("body", [body_of(), {"zonas": "mal"}], ids=["valido", "invalido"])
@pytest.mark.parametrize("kind", ["sin-token", "basura", "vencido", "sin-firma"])
def test_without_a_valid_token_it_is_401(
    client: TestClient, db: Store, kind: str, body: Any
) -> None:
    """401 `NO_AUTENTICADO` antes de mirar el cuerpo o la base (DC-16, S-03)."""
    db.seed_user(USER_ID)
    before = db.snapshot()
    headers = {
        "sin-token": {},
        "basura": auth_header("no-es-un-token"),
        "vencido": auth_header(make_token(USER_ID, email_of(USER_ID), expired=True)),
        "sin-firma": auth_header(make_token(USER_ID, email_of(USER_ID), algorithm="none")),
    }[kind]

    response = client.post(f"{API_PREFIX}/onboarding", json=body, headers=headers)

    assert_error(response, 401, "NO_AUTENTICADO")
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert db.events == []
    assert db.snapshot() == before


INVALID_ZONES = (
    ("ZONAS_NO_PERMITIDAS", "apartaestudio", ("cocina", "sala", "bano", "terraza")),
    ("ZONAS_BASICAS_FALTANTES", "apartamento", ("cocina", "sala", "dormitorio")),
    ("CANTIDAD_ZONAS_INVALIDA", "apartaestudio", (*BASIC_ZONES, "oficina", "lavanderia")),
    ("CANTIDAD_ZONAS_INVALIDA", "apartaestudio", ("cocina", "sala", "oficina", "lavanderia")),
    ("ZONAS_DUPLICADAS", "casa", (*BASIC_ZONES, "bano")),
)


@pytest.mark.parametrize("with_household", [False, True], ids=["sin-hogar", "con-hogar"])
@pytest.mark.parametrize(
    ("code", "housing", "zones"),
    INVALID_ZONES,
    ids=[f"{case[0]}-{len(case[2])}" for case in INVALID_ZONES],
)
def test_invalid_zones_are_422_without_touching_the_database(
    client: TestClient,
    db: Store,
    code: str,
    housing: str,
    zones: tuple[str, ...],
    with_household: bool,
) -> None:
    """Los 4 códigos de RN-X-02; se responden antes de consultar la membresía."""
    db.seed_user(USER_ID)
    if with_household:
        db.seed_membership(USER_ID, "miembro", "activo")
    before = db.snapshot()

    assert_error(onboard(client, USER_ID, body_of(housing, zones)), 422, code)

    assert db.events == []
    assert db.snapshot() == before


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(body_of(zones=("cocina", "sala")), id="dos-zonas"),
        pytest.param(body_of(zones=(*BASIC_ZONES, "sotano")), id="zona-fuera-de-catalogo"),
        pytest.param(body_of("cuarto"), id="vivienda-fuera-de-catalogo"),
        pytest.param(body_of(personalidad="Consumo amplio"), id="personalidad-del-cliente"),
        pytest.param(body_of(nombre_hogar=""), id="nombre-vacio"),
    ],
)
def test_body_outside_the_schema_is_422_validacion(
    client: TestClient, db: Store, body: dict[str, Any]
) -> None:
    """Entrada que el contrato rechaza; el cliente no puede enviar la personalidad (RN-X-04)."""
    db.seed_user(USER_ID)
    assert_error(onboard(client, USER_ID, body), 422, "VALIDACION")
    assert db.events == []
    assert set(db.household_rows().values()) == {0}


# --- una membresía activa por usuario (RN-II-01) ----------------------------------------------


@pytest.mark.parametrize("rol", ["miembro", "administrador"])
def test_user_with_an_active_household_gets_409_and_nothing_is_created(
    client: TestClient, db: Store, rol: str
) -> None:
    db.seed_user(USER_ID)
    db.seed_membership(USER_ID, rol, "activo")
    before = db.snapshot()

    assert_error(onboard(client, USER_ID), 409, "MEMBRESIA_ACTIVA_EXISTENTE")

    assert db.events == ["ACTIVE_MEMBERSHIP_OF_USER_SQL"]
    assert db.snapshot() == before


def test_second_onboarding_of_the_same_user_is_409(client: TestClient, db: Store) -> None:
    """Repetir la llamada después de un 201 no crea otro hogar ni más lecturas."""
    db.seed_user(USER_ID)
    assert onboard(client, USER_ID).status_code == 201
    before = db.snapshot()

    assert_error(onboard(client, USER_ID), 409, "MEMBRESIA_ACTIVA_EXISTENTE")

    assert db.snapshot() == before


def test_closed_membership_does_not_block(client: TestClient, db: Store) -> None:
    """Una membresía inactiva de otro hogar no cuenta (RN-II-01): 201."""
    db.seed_user(USER_ID)
    old_household = db.seed_membership(USER_ID, "miembro", "inactivo")

    response = onboard(client, USER_ID)

    assert response.status_code == 201, response.text
    assert response.json()["id"] != str(old_household)
    assert len(db.rows("hogares")) == 2


def race(app: FastAPI, db: Store) -> list[httpx.Response]:
    """Dos peticiones del mismo usuario que pasan a la vez la comprobación previa.

    La que inserta primero la membresía espera, antes de las lecturas, a que la otra esté
    bloqueada en el índice único: el resultado no depende del orden de los hilos.
    """
    both_checked = threading.Barrier(2, timeout=WAIT_SECONDS)
    db.after["ACTIVE_MEMBERSHIP_OF_USER_SQL"] = both_checked.wait
    db.before[READINGS_STATEMENT] = lambda: db.waiting.wait(WAIT_SECONDS)
    clients = [TestClient(app, raise_server_exceptions=False) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda client: onboard(client, USER_ID), clients))
    assert db.waiting.is_set()
    assert len(db.sessions) == 2
    return sorted(responses, key=lambda response: response.status_code)


def test_race_of_two_requests_creates_a_single_household(app: FastAPI, db: Store) -> None:
    """Una gana con 201; la otra choca con `uq_miembros_usuario_activo` y responde 409."""
    db.seed_user(USER_ID)

    won, lost = race(app, db)

    assert won.status_code == 201, won.text
    assert_error(lost, 409, "MEMBRESIA_ACTIVA_EXISTENTE")
    assert str(USER_ID) not in lost.text
    assert [str(row["id"]) for row in db.rows("hogares")] == [won.json()["id"]]
    assert db.household_rows() == ONE_BASIC_HOUSEHOLD
    assert (db.events.count("commit"), db.events.count("rollback")) == (1, 1)


def test_race_when_the_first_one_fails_lets_the_second_one_in(app: FastAPI, db: Store) -> None:
    """Si la primera falla y revierte, la que esperaba crea el hogar: 500 y 201."""
    db.seed_user(USER_ID)
    db.fail_once.add(READINGS_STATEMENT)

    won, failed = race(app, db)

    assert won.status_code == 201, won.text
    assert_backfill_failed(failed)
    assert [str(row["id"]) for row in db.rows("hogares")] == [won.json()["id"]]
    assert db.household_rows() == ONE_BASIC_HOUSEHOLD


def test_two_users_have_separate_households(client: TestClient, db: Store) -> None:
    """Mismo nombre y zonas: cada usuario con su hogar, sus sensores y sus lecturas."""
    for user_id in (USER_ID, OTHER_USER_ID):
        db.seed_user(user_id)
        assert onboard(client, user_id).status_code == 201
    assert db.household_rows() == {table: 2 * n for table, n in ONE_BASIC_HOUSEHOLD.items()}
    zone_household = {row["id"]: row["hogar_id"] for row in db.rows("zonas")}
    source_household = {row["id"]: row["hogar_id"] for row in db.rows("fuentes_principales")}
    for sensor in db.rows("sensores_zona"):  # DC-38
        assert zone_household[sensor["zona_id"]] == source_household[sensor["fuente_principal_id"]]


# --- fallos: todo o nada (RN-X-03) ------------------------------------------------------------


@pytest.mark.parametrize("step", [*ONBOARDING_STATEMENTS, "commit"])
def test_failure_in_any_step_leaves_the_store_intact_and_the_retry_works(
    client: TestClient, db: Store, caplog: pytest.LogCaptureFixture, step: str
) -> None:
    """500 `BACKFILL_FALLIDO` en cualquier paso, también a mitad del lote y en el commit.

    El almacén queda igual, la respuesta y el log no llevan el detalle interno (S-01) y repetir
    la misma llamada crea el hogar completo una sola vez (RN-X-03, sección 7.1).
    """
    db.seed_user(USER_ID)
    before = db.snapshot()
    db.fail_once.add(step)

    with caplog.at_level(logging.INFO):
        failed = onboard(client, USER_ID)

    assert_backfill_failed(failed)
    assert db.fail_once == set()  # el fallo sí ocurrió
    assert db.snapshot() == before
    assert db.events[-1] == "rollback"
    assert "commit" not in db.events
    assert "Onboarding fallido" in caplog.text
    assert "Onboarding creado" not in caplog.text
    for secret in ("detalle-interno", str(USER_ID), HOUSEHOLD_NAME):
        assert secret not in failed.text
        assert secret not in caplog.text

    retried = onboard(client, USER_ID)

    assert retried.status_code == 201, retried.text
    assert db.household_rows() == ONE_BASIC_HOUSEHOLD


@each_personality
def test_failure_halfway_through_the_batch_leaves_zero_rows(
    client: TestClient, db: Store, name: str
) -> None:
    """B-02 de punta a punta con cada personalidad: media escritura y 0 filas del hogar."""
    db.seed_user(USER_ID)
    db.fail_once.add(READINGS_STATEMENT)

    assert_backfill_failed(onboard(client, USER_ID, body_of(*REFERENCE_HOUSEHOLDS[name])))

    assert set(db.household_rows().values()) == {0}


def test_simulator_failure_halfway_reverts_the_rows_already_written(
    client: TestClient, db: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falla el simulador en la tercera zona: aquí PostgreSQL no aborta nada, revierte la API."""
    db.seed_user(USER_ID)
    before = db.snapshot()
    real, generated = engine.simulate_zone, []

    def fail_on_third(*args: Any, **kwargs: Any) -> Any:
        generated.append(args[2])
        if len(generated) == 3:
            raise DegenerateRealizationError(INTERNAL_DETAIL)
        return real(*args, **kwargs)

    monkeypatch.setattr(engine, "simulate_zone", fail_on_third)

    assert_backfill_failed(onboard(client, USER_ID))

    assert len(generated) == 3
    assert db.events == [*ONBOARDING_STATEMENTS[:-1], "rollback"]
    assert db.snapshot() == before


def test_without_any_active_personality_it_is_500_and_nothing_is_created(
    client: TestClient, db: Store
) -> None:
    """Ni la asignada ni el respaldo están activos (RN-X-04): no se escribe nada."""
    db.seed_user(USER_ID)
    db.deactivate_profile(FALLBACK_PERSONALITY)
    before = db.snapshot()

    assert_backfill_failed(onboard(client, USER_ID))

    assert db.events == [*ONBOARDING_STATEMENTS[:2], "rollback"]
    assert db.snapshot() == before


def test_user_without_profile_gets_404_and_can_retry_after_creating_it(
    client: TestClient, db: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Sin ficha (23503 en `hogar_miembros.usuario_id`): 404 `FICHA_NO_CREADA` y 0 filas.

    Después de crear la ficha (RN-IX-01), la misma llamada funciona.
    """
    db.seed_auth_user(USER_ID)
    before = db.snapshot()

    with caplog.at_level(logging.INFO):
        assert_no_profile(onboard(client, USER_ID))

    assert db.snapshot() == before
    assert db.events[-2:] == ["INSERT_ADMIN_MEMBERSHIP_SQL", "rollback"]
    assert "sqlstate=23503" in caplog.text
    assert str(USER_ID) not in caplog.text

    assert call(client, "crearFichaUsuario", USER_ID, PROFILE_BODY).status_code == 201
    assert onboard(client, USER_ID).status_code == 201
    assert db.household_rows() == ONE_BASIC_HOUSEHOLD


# --- cadena fase 3 + fase 4 -------------------------------------------------------------------


@each_personality
def test_from_the_profile_to_the_household_and_back_to_nothing(
    client: TestClient, db: Store, name: str
) -> None:
    """Ficha → onboarding → `GET /usuarios/me` con la membresía → eliminar la cuenta.

    Esperado: la ficha muestra la membresía nueva de administrador; al eliminar la cuenta del único
    miembro se borra el hogar con sus zonas, sensores y lecturas, y el hogar de otra persona y el
    catálogo de perfiles quedan igual (RN-IX-01, RN-IX-09, DC-36).
    """
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    db.seed_user(OTHER_USER_ID)
    assert onboard(client, OTHER_USER_ID).status_code == 201
    neighbour = db.snapshot()
    db.seed_auth_user(USER_ID)

    assert_error(call(client, "obtenerUsuarioActual", USER_ID), 404, "FICHA_NO_CREADA")
    created = call(client, "crearFichaUsuario", USER_ID, PROFILE_BODY)
    assert created.status_code == 201, created.text
    assert created.json()["membresia"] is None

    onboarded = onboard(client, USER_ID, body_of(housing, zones))
    assert onboarded.status_code == 201, onboarded.text

    current = call(client, "obtenerUsuarioActual", USER_ID)
    assert current.status_code == 200, current.text
    (member,) = [row for row in db.rows("hogar_miembros") if row["usuario_id"] == USER_ID]
    membership = {
        "membresia_id": str(member["id"]),
        "hogar_id": onboarded.json()["id"],
        "rol": "administrador",
    }
    assert current.json() == {**created.json(), "membresia": membership}
    other = call(client, "obtenerUsuarioActual", OTHER_USER_ID).json()
    assert other["membresia"]["hogar_id"] != onboarded.json()["id"]

    db.events.clear()
    deleted = call(client, "eliminarCuenta", USER_ID)

    assert deleted.status_code == 204, deleted.text
    assert db.events == [  # orden de bloqueo hogar → membresía → usuario (fase 9)
        "ACTIVE_MEMBERSHIP_OF_USER_SQL",
        "LOCK_HOUSEHOLD_SQL",
        "ACTIVE_MEMBERSHIP_OF_USER_FOR_UPDATE_SQL",
        "LOCK_USER_PROFILE_SQL",
        "COUNT_OTHER_ACTIVE_MEMBERS_SQL",
        "CLOSE_MEMBERSHIP_SQL",
        "DELETE_HOUSEHOLD_SQL",
        "DELETE_USER_PROFILE_SQL",
        "commit",
        "delete_auth_user",
        "delete_avatar_files",
    ]
    assert db.snapshot() == neighbour  # nada huérfano; lo demás intacto
    assert_error(call(client, "obtenerUsuarioActual", USER_ID), 404, "FICHA_NO_CREADA")


def test_token_of_a_deleted_account_cannot_create_a_household(
    client: TestClient, db: Store
) -> None:
    """El token sigue vigente, pero ya no hay ficha: 404 `FICHA_NO_CREADA` y almacén intacto."""
    db.seed_user(USER_ID)
    assert onboard(client, USER_ID).status_code == 201
    assert call(client, "eliminarCuenta", USER_ID).status_code == 204
    before = db.snapshot()

    assert_no_profile(onboard(client, USER_ID))

    assert db.snapshot() == before
    assert set(db.household_rows().values()) == {0}
