"""Usuario de punta a punta (fase 3): router → seguridad → servicio → datos, sobre la app real.

`create_app(make_test_settings())` con sus routers, el JWKS de prueba y tokens firmados en
memoria. Solo se reemplaza lo más bajo:

- `get_session` entrega una `RecordingSession` por petición: trabaja sobre una copia de las
  tablas y solo la publica en `commit()` (si la petición falla antes, la copia se descarta,
  como un rollback). Cualquier otro uso de la sesión (SQL) falla.
- Las funciones de `app.data.users`, `app.data.memberships`, `app.data.households` y
  `app.services.supabase_admin` leen y escriben ese almacén en memoria, que respeta las reglas
  de las tablas de `supabase/migrations/` (0002 y 0003): ficha 1:1 con `auth.users`,
  preferencias 1:1 con valores por defecto true/true/'promedio', `base_comparacion` en
  ('meta', 'promedio'), una membresía activa por usuario (`uq_miembros_usuario_activo`), un
  administrador activo por hogar, membresía activa siempre con usuario, cascada de `hogares`
  a `hogar_miembros` y de `auth.users` a `usuarios`/`preferencias_usuario` con
  `hogar_miembros.usuario_id` en nulo (DC-36). Supabase Auth y Storage escriben fuera de la
  transacción de la petición (son otro servicio).

Sin base, sin red y sin secretos. Cada respuesta se valida con `jsonschema` contra el
contrato `docs/api/zentheris-api.yaml` (ayudantes de C-01). Huecos del contrato que se
comprueban solo contra el esquema `Error`: el 404 `FICHA_NO_CREADA` en `actualizarPerfil`,
`guardarAvatar`, `eliminarAvatar`, `obtenerPreferencias` y `actualizarPreferencias`, y el 500
`ERROR_INTERNO` de `eliminarCuenta` (el contrato solo declara 500 en `POST /onboarding`).

Reglas: RN-IX-01, RN-IX-07, RN-IX-09, RN-I-02, RN-VII-01, RN-VI-04, RN-XVI-02, RN-XVI-03.
Decisiones: DC-36 (baja de la cuenta), DC-43 (ruta del avatar), DC-16 (errores).
"""

import copy
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import users as users_data
from app.data.database import get_session
from app.data.memberships import MembershipSummaryRow
from app.data.users import PreferencesRow, UserProfileRow
from app.errors import INTERNAL_ERROR_MESSAGE
from app.main import API_PREFIX, create_app
from app.services import supabase_admin
from tests.contract.test_c01_responses_match_schema import (
    OPERATIONS,
    assert_matches_contract,
    assert_matches_error_schema,
)
from tests.helpers.auth import (
    TEST_SUPABASE_URL,
    auth_header,
    install_test_jwks,
    make_test_settings,
    make_token,
)

# --- personas y hogares de prueba -----------------------------------------------------------

NEW_USER_ID = UUID("e2e00000-0000-4000-8000-000000000001")
ADMIN_ID = UUID("e2e00000-0000-4000-8000-000000000002")
MEMBER_ID = UUID("e2e00000-0000-4000-8000-000000000003")
OTHER_USER_ID = UUID("e2e00000-0000-4000-8000-000000000004")
HOGAR_ID = UUID("e2e00000-0000-4000-8000-000000000101")
ADMIN_MEMBRESIA_ID = UUID("e2e00000-0000-4000-8000-000000000201")
MEMBER_MEMBRESIA_ID = UUID("e2e00000-0000-4000-8000-000000000202")
JOINED_AT = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)

DEFAULT_PREFERENCES = {
    "notif_consumo": True,
    "notif_consejos": True,
    "base_comparacion": "promedio",
}
INTERNAL_ERROR_BODY = {
    "codigo": "ERROR_INTERNO",
    "mensaje": INTERNAL_ERROR_MESSAGE,
    "detalles": None,
}
# Texto de la excepción interna simulada: nunca debe salir en la respuesta (S-01).
AUTH_FAILURE_DETAIL = "detalle-interno-de-supabase-auth"

# El contrato no declara 404 en estas operaciones (hueco conocido, se reporta en el PR).
NO_PROFILE_404_OUTSIDE_CONTRACT = frozenset(
    {
        "actualizarPerfil",
        "guardarAvatar",
        "eliminarAvatar",
        "obtenerPreferencias",
        "actualizarPreferencias",
    }
)


def email_of(user_id: UUID) -> str:
    return f"persona-{str(user_id)[-4:]}@example.com"


# --- almacén en memoria ---------------------------------------------------------------------


class ConstraintViolation(AssertionError):
    """Una escritura rompió una regla de las tablas (en PostgreSQL sería IntegrityError)."""


@dataclass
class Tables:
    """Filas de las tablas que toca la fase 3 (y `auth.users`, de Supabase Auth)."""

    auth_users: set[UUID] = field(default_factory=set)
    usuarios: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    preferencias_usuario: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    hogares: set[UUID] = field(default_factory=set)
    hogar_miembros: dict[UUID, dict[str, Any]] = field(default_factory=dict)

    def check(self) -> None:
        """Restricciones de 0002/0003 que afectan a estas operaciones."""
        for usuario_id, row in self.usuarios.items():
            if usuario_id not in self.auth_users:
                raise ConstraintViolation(f"usuarios.id sin auth.users: {usuario_id}")
            if not row["nombre_completo"]:
                raise ConstraintViolation("usuarios.nombre_completo es NOT NULL")
        if set(self.preferencias_usuario) - set(self.usuarios):
            raise ConstraintViolation("preferencias_usuario sin usuarios")
        for prefs in self.preferencias_usuario.values():
            if not isinstance(prefs["notif_consumo"], bool) or not isinstance(
                prefs["notif_consejos"], bool
            ):
                raise ConstraintViolation("interruptores NOT NULL boolean")
            if prefs["base_comparacion"] not in ("meta", "promedio"):
                raise ConstraintViolation("base_comparacion fuera del check")
        active_users: set[UUID] = set()
        active_admins: set[UUID] = set()
        for row in self.hogar_miembros.values():
            if row["hogar_id"] not in self.hogares:
                raise ConstraintViolation("hogar_miembros.hogar_id sin hogares")
            if row["usuario_id"] is not None and row["usuario_id"] not in self.usuarios:
                raise ConstraintViolation("hogar_miembros.usuario_id sin usuarios")
            if row["estado"] != "activo":
                continue
            if row["usuario_id"] is None:
                raise ConstraintViolation("miembros_activo_con_usuario")
            if row["usuario_id"] in active_users:
                raise ConstraintViolation("uq_miembros_usuario_activo")
            active_users.add(row["usuario_id"])
            if row["rol"] == "administrador":
                if row["hogar_id"] in active_admins:
                    raise ConstraintViolation("uq_miembros_admin_activo")
                active_admins.add(row["hogar_id"])

    def delete_household_cascade(self, hogar_id: UUID) -> None:
        self.hogares.discard(hogar_id)
        for membresia_id in [
            m for m, row in self.hogar_miembros.items() if row["hogar_id"] == hogar_id
        ]:
            del self.hogar_miembros[membresia_id]

    def delete_auth_user_cascade(self, usuario_id: UUID) -> None:
        """DC-36: auth.users → usuarios → preferencias (cascada); miembros quedan sin usuario."""
        self.auth_users.discard(usuario_id)
        self.usuarios.pop(usuario_id, None)
        self.preferencias_usuario.pop(usuario_id, None)
        for row in self.hogar_miembros.values():
            if row["usuario_id"] == usuario_id:
                row["usuario_id"] = None


class RecordingSession:
    """Sesión de una petición: escribe en una copia y la publica solo con `commit()`."""

    def __init__(self, db: InMemoryDatabase) -> None:
        self.db = db
        self.working = copy.deepcopy(db.committed)
        self.commits = 0

    def commit(self) -> None:
        self.working.check()
        self.db.committed = copy.deepcopy(self.working)
        self.commits += 1
        self.db.events.append(("commit",))

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"RecordingSession no admite `{name}`: reemplaza la función de datos.")


class InMemoryDatabase:
    """Reemplaza las funciones de `app.data.*` de la fase 3 sobre `Tables` en memoria."""

    def __init__(self) -> None:
        self.committed = Tables()
        self.sessions: list[RecordingSession] = []
        self.events: list[tuple[Any, ...]] = []
        self.auth_failure: Exception | None = None
        self.storage_failure: Exception | None = None

    # --- sesión de la petición ---------------------------------------------------------

    def open_session(self) -> RecordingSession:
        session = RecordingSession(self)
        self.sessions.append(session)
        return session

    def _tables(self, session: object) -> Tables:
        # Cada función de datos recibe la sesión que `get_session` entregó a esta petición.
        assert self.sessions and session is self.sessions[-1], "sesión distinta a la de la petición"
        assert isinstance(session, RecordingSession)
        return session.working

    @property
    def total_commits(self) -> int:
        return sum(session.commits for session in self.sessions)

    def snapshot(self) -> Tables:
        return copy.deepcopy(self.committed)

    # --- semilla (estado ya confirmado) ------------------------------------------------

    def seed_auth_user(self, usuario_id: UUID) -> None:
        self.committed.auth_users.add(usuario_id)

    def seed_profile(
        self, usuario_id: UUID, nombre: str = "Laura Gómez", telefono: str | None = None
    ) -> None:
        self.seed_auth_user(usuario_id)
        self.committed.usuarios[usuario_id] = {
            "nombre_completo": nombre,
            "telefono": telefono,
            "avatar_url": None,
        }
        self.committed.preferencias_usuario[usuario_id] = dict(DEFAULT_PREFERENCES)
        self.committed.check()

    def seed_membership(
        self, membresia_id: UUID, usuario_id: UUID, hogar_id: UUID, rol: str
    ) -> None:
        self.committed.hogares.add(hogar_id)
        self.committed.hogar_miembros[membresia_id] = {
            "hogar_id": hogar_id,
            "usuario_id": usuario_id,
            "rol": rol,
            "estado": "activo",
            "fecha_ingreso": JOINED_AT,
            "fecha_salida": None,
        }
        self.committed.check()

    # --- app.data.users ------------------------------------------------------------------

    def get_user_profile(self, session: object, usuario_id: UUID) -> UserProfileRow | None:
        tables = self._tables(session)
        row = tables.usuarios.get(usuario_id)
        prefs = tables.preferencias_usuario.get(usuario_id)
        if row is None or prefs is None:  # join interno
            return None
        return UserProfileRow(
            id=usuario_id,
            nombre_completo=row["nombre_completo"],
            telefono=row["telefono"],
            avatar_url=row["avatar_url"],
            preferencias=PreferencesRow(**prefs),
        )

    def insert_user_with_default_preferences(
        self, session: object, usuario_id: UUID, nombre_completo: str, telefono: str | None
    ) -> bool:
        tables = self._tables(session)
        if usuario_id not in tables.auth_users:
            # FK usuarios.id → auth.users (23503): token vigente de una cuenta ya borrada.
            raise users_data.AuthUserMissingError("La cuenta de Auth ya no existe.")
        if usuario_id in tables.usuarios:  # ON CONFLICT (id) DO NOTHING
            return False
        tables.usuarios[usuario_id] = {
            "nombre_completo": nombre_completo,
            "telefono": telefono,
            "avatar_url": None,
        }
        # Valores por defecto de la tabla preferencias_usuario.
        tables.preferencias_usuario[usuario_id] = dict(DEFAULT_PREFERENCES)
        tables.check()
        return True

    def update_user_profile(
        self, session: object, usuario_id: UUID, changes: Mapping[str, str | None]
    ) -> bool:
        tables = self._tables(session)
        _check_partial_changes(changes, users_data.USER_PROFILE_FIELDS)
        row = tables.usuarios.get(usuario_id)
        if row is None:
            return False
        row.update(changes)
        tables.check()
        return True

    def set_avatar_url(self, session: object, usuario_id: UUID, avatar_url: str | None) -> bool:
        tables = self._tables(session)
        row = tables.usuarios.get(usuario_id)
        if row is None:
            return False
        row["avatar_url"] = avatar_url
        return True

    def get_preferences(self, session: object, usuario_id: UUID) -> PreferencesRow | None:
        prefs = self._tables(session).preferencias_usuario.get(usuario_id)
        return None if prefs is None else PreferencesRow(**prefs)

    def update_preferences(
        self, session: object, usuario_id: UUID, changes: Mapping[str, bool | str]
    ) -> PreferencesRow | None:
        tables = self._tables(session)
        _check_partial_changes(changes, users_data.PREFERENCE_FIELDS)
        prefs = tables.preferencias_usuario.get(usuario_id)
        if prefs is None:
            return None
        prefs.update(changes)
        tables.check()
        return PreferencesRow(**prefs)

    # --- app.data.memberships ------------------------------------------------------------

    def get_active_membership_of_user(
        self, session: object, usuario_id: UUID, *, for_update: bool = False
    ) -> MembershipSummaryRow | None:
        tables = self._tables(session)
        self.events.append(("get_active_membership_of_user", usuario_id, for_update))
        active = [
            MembershipSummaryRow(membresia_id=m, hogar_id=row["hogar_id"], rol=row["rol"])
            for m, row in tables.hogar_miembros.items()
            if row["usuario_id"] == usuario_id and row["estado"] == "activo"
        ]
        assert len(active) <= 1  # uq_miembros_usuario_activo
        return active[0] if active else None

    def count_other_active_members(self, session: object, hogar_id: UUID, usuario_id: UUID) -> int:
        tables = self._tables(session)
        self.events.append(("count_other_active_members", hogar_id))
        return sum(
            1
            for row in tables.hogar_miembros.values()
            if row["hogar_id"] == hogar_id
            and row["estado"] == "activo"
            and row["usuario_id"] != usuario_id
        )

    def close_membership(self, session: object, membresia_id: UUID, closed_at: datetime) -> None:
        tables = self._tables(session)
        self.events.append(("close_membership", membresia_id))
        row = tables.hogar_miembros.get(membresia_id)
        if row is not None:
            row["estado"] = "inactivo"
            row["fecha_salida"] = closed_at
        tables.check()

    # --- app.data.households -------------------------------------------------------------

    def lock_household(self, session: object, hogar_id: UUID) -> None:
        self._tables(session)
        self.events.append(("lock_household", hogar_id))

    def delete_household(self, session: object, hogar_id: UUID) -> None:
        tables = self._tables(session)
        self.events.append(("delete_household", hogar_id))
        tables.delete_household_cascade(hogar_id)
        tables.check()

    # --- app.services.supabase_admin (otro servicio: fuera de la transacción) -----------

    def delete_auth_user(self, settings: Settings, usuario_id: UUID) -> None:
        self.events.append(("delete_auth_user", settings.supabase_url, usuario_id))
        if self.auth_failure is not None:
            raise self.auth_failure
        self.committed.delete_auth_user_cascade(usuario_id)
        self.committed.check()

    def delete_avatar_files(self, settings: Settings, usuario_id: UUID) -> None:
        self.events.append(("delete_avatar_files", settings.supabase_url, usuario_id))
        if self.storage_failure is not None:
            raise self.storage_failure


def _check_partial_changes(changes: Mapping[str, Any], allowed: frozenset[str]) -> None:
    """Igual que la capa de datos real: lista blanca y al menos un cambio."""
    if not changes:
        raise ValueError("No hay cambios que aplicar.")
    if set(changes) - allowed:
        raise ValueError(f"Columnas no permitidas: {sorted(set(changes) - allowed)}")


REPLACED_FUNCTIONS = (
    (
        users_data,
        (
            "get_user_profile",
            "insert_user_with_default_preferences",
            "update_user_profile",
            "set_avatar_url",
            "get_preferences",
            "update_preferences",
        ),
    ),
    (
        memberships_data,
        ("get_active_membership_of_user", "count_other_active_members", "close_membership"),
    ),
    (households_data, ("lock_household", "delete_household")),
    (supabase_admin, ("delete_auth_user", "delete_avatar_files")),
)


# --- app y cliente --------------------------------------------------------------------------


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> InMemoryDatabase:
    database = InMemoryDatabase()
    for module, names in REPLACED_FUNCTIONS:
        for name in names:
            assert hasattr(module, name), f"{module.__name__}.{name}"
            monkeypatch.setattr(module, name, getattr(database, name))
    install_test_jwks(monkeypatch)
    return database


@pytest.fixture
def client(db: InMemoryDatabase) -> Iterator[TestClient]:
    app = create_app(make_test_settings())
    app.dependency_overrides[get_settings] = make_test_settings

    def session_override() -> Iterator[RecordingSession]:
        yield db.open_session()

    app.dependency_overrides[get_session] = session_override
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


NO_BODY = object()


def call(
    client: TestClient,
    operation_id: str,
    user_id: UUID | None,
    body: Any = NO_BODY,
) -> httpx.Response:
    """Llama la operación como `user_id` (None = sin token) y valida el cuerpo con el contrato.

    Estado declarado en la operación → su esquema exacto. Huecos conocidos (404
    `FICHA_NO_CREADA` fuera del contrato y 500 sin declarar) → el esquema `Error`.
    Cualquier otro estado no declarado hace fallar la prueba.
    """
    method, path, op = OPERATIONS[operation_id]
    headers = auth_header(make_token(user_id, email_of(user_id))) if user_id else {}
    kwargs: dict[str, Any] = {"headers": headers}
    if body is not NO_BODY:
        kwargs["json"] = body
    response = client.request(method.upper(), API_PREFIX + path, **kwargs)
    if str(response.status_code) in op["responses"]:
        assert_matches_contract(operation_id, response)
    elif response.status_code == 404 and operation_id in NO_PROFILE_404_OUTSIDE_CONTRACT:
        assert_matches_error_schema(response)
        assert response.json()["codigo"] == "FICHA_NO_CREADA"
    elif response.status_code == 500:
        assert_matches_error_schema(response)
    else:
        pytest.fail(f"{operation_id} respondió {response.status_code}, que el contrato no declara")
    return response


def assert_error(response: httpx.Response, status: int, codigo: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"codigo", "mensaje", "detalles"}
    assert body["codigo"] == codigo
    return body


# --- primer acceso (RN-IX-01) ---------------------------------------------------------------


def test_first_access_creates_profile_with_default_preferences(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """GET sin ficha → 404; POST → 201 con preferencias por defecto; POST otra vez → 409.

    Esperado: 404 `FICHA_NO_CREADA`; 201 con `telefono`/`avatar_url`/`membresia` en null,
    `correo` del token y preferencias true/true/'promedio' (un commit); 409
    `FICHA_EXISTENTE` sin tocar nada; GET → 200 igual a lo creado. Regla: RN-IX-01, RN-IX-07.
    """
    db.seed_auth_user(NEW_USER_ID)

    assert_error(call(client, "obtenerUsuarioActual", NEW_USER_ID), 404, "FICHA_NO_CREADA")
    assert db.total_commits == 0

    created = call(client, "crearFichaUsuario", NEW_USER_ID, {"nombre_completo": "Ana Ruiz"})
    assert created.status_code == 201, created.text
    assert created.json() == {
        "id": str(NEW_USER_ID),
        "correo": email_of(NEW_USER_ID),
        "nombre_completo": "Ana Ruiz",
        "telefono": None,
        "avatar_url": None,
        "preferencias": DEFAULT_PREFERENCES,
        "membresia": None,
    }
    assert db.total_commits == 1
    assert db.committed.preferencias_usuario[NEW_USER_ID] == DEFAULT_PREFERENCES

    before = db.snapshot()
    again = call(client, "crearFichaUsuario", NEW_USER_ID, {"nombre_completo": "Otro nombre"})
    assert_error(again, 409, "FICHA_EXISTENTE")
    assert db.committed == before
    assert db.total_commits == 1

    current = call(client, "obtenerUsuarioActual", NEW_USER_ID)
    assert current.status_code == 200
    assert current.json() == created.json()


def test_current_user_shows_active_membership(client: TestClient, db: InMemoryDatabase) -> None:
    """GET con membresía activa → `membresia` con id, hogar y rol (RN-IX-01, RN-I-03)."""
    db.seed_profile(ADMIN_ID)
    db.seed_membership(ADMIN_MEMBRESIA_ID, ADMIN_ID, HOGAR_ID, "administrador")
    body = call(client, "obtenerUsuarioActual", ADMIN_ID).json()
    assert body["membresia"] == {
        "membresia_id": str(ADMIN_MEMBRESIA_ID),
        "hogar_id": str(HOGAR_ID),
        "rol": "administrador",
    }


def test_create_profile_for_account_deleted_in_auth_is_401(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """Token todavía vigente de una cuenta ya borrada en Auth → POST /usuarios/me da 401.

    La FK `usuarios.id → auth.users` falla (`AuthUserMissingError` en la capa de datos).
    Esperado: 401 `NO_AUTENTICADO` con `WWW-Authenticate: Bearer`, sin commit ni filas
    creadas. Regla: RN-IX-01, DC-36, DC-16.
    """
    before = db.snapshot()  # NEW_USER_ID no está en auth.users

    response = call(client, "crearFichaUsuario", NEW_USER_ID, {"nombre_completo": "Ana Ruiz"})

    assert_error(response, 401, "NO_AUTENTICADO")
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert db.total_commits == 0
    assert db.committed == before


# --- perfil (RN-IX-07) ----------------------------------------------------------------------


def test_patch_profile_changes_only_sent_fields(client: TestClient, db: InMemoryDatabase) -> None:
    """PATCH parcial: solo teléfono; `telefono: null` lo borra; `{}` y «correo» → 422.

    Esperado: el nombre no cambia; null queda guardado como null (no como texto vacío);
    `{}` y un campo extra dan 422 `VALIDACION` sin commit ni cambios. Regla: RN-IX-07.
    """
    db.seed_profile(MEMBER_ID, nombre="Laura Gómez", telefono="3001234567")

    phone = call(client, "actualizarPerfil", MEMBER_ID, {"telefono": "3109876543"})
    assert phone.status_code == 200, phone.text
    assert phone.json()["telefono"] == "3109876543"
    assert phone.json()["nombre_completo"] == "Laura Gómez"
    assert db.committed.usuarios[MEMBER_ID]["telefono"] == "3109876543"

    cleared = call(client, "actualizarPerfil", MEMBER_ID, {"telefono": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["telefono"] is None
    assert db.committed.usuarios[MEMBER_ID]["telefono"] is None
    assert call(client, "obtenerUsuarioActual", MEMBER_ID).json()["telefono"] is None
    assert db.total_commits == 2

    before = db.snapshot()
    assert_error(call(client, "actualizarPerfil", MEMBER_ID, {}), 422, "VALIDACION")
    extra = call(client, "actualizarPerfil", MEMBER_ID, {"correo": "otra@example.com"})
    assert_error(extra, 422, "VALIDACION")
    assert db.committed == before
    assert db.total_commits == 2


# --- avatar (RN-I-02, DC-43) ----------------------------------------------------------------


def test_avatar_save_reject_foreign_path_and_delete(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """PUT `{id}/avatar.png` → 200; ruta de otro usuario → 422; DELETE → 204; GET → null.

    Esperado: la ruta queda guardada tal cual; la carpeta ajena da 422 `VALIDACION` en
    `["body", "avatar_url"]` sin cambiar la guardada; DELETE responde 204 sin cuerpo y el
    avatar vuelve a null (la app muestra las iniciales). Regla: RN-I-02, DC-43.
    """
    db.seed_profile(MEMBER_ID)
    own_path = f"{MEMBER_ID}/avatar.png"

    saved = call(client, "guardarAvatar", MEMBER_ID, {"avatar_url": own_path})
    assert saved.status_code == 200, saved.text
    assert saved.json()["avatar_url"] == own_path
    assert db.committed.usuarios[MEMBER_ID]["avatar_url"] == own_path

    before = db.snapshot()
    foreign = call(
        client, "guardarAvatar", MEMBER_ID, {"avatar_url": f"{OTHER_USER_ID}/avatar.png"}
    )
    body = assert_error(foreign, 422, "VALIDACION")
    assert [c["ubicacion"] for c in body["detalles"]["campos"]] == [["body", "avatar_url"]]
    assert db.committed == before

    deleted = call(client, "eliminarAvatar", MEMBER_ID)
    assert deleted.status_code == 204
    assert db.committed.usuarios[MEMBER_ID]["avatar_url"] is None
    assert call(client, "obtenerUsuarioActual", MEMBER_ID).json()["avatar_url"] is None
    assert db.total_commits == 2


# --- preferencias (RN-VII-01, RN-VI-04, RN-XVI-02, RN-XVI-03) ------------------------------


def test_preferences_patch_changes_only_comparison_base(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """GET → valores por defecto; PATCH `base_comparacion: 'meta'` → solo cambia ese campo.

    Esperado: un interruptor apagado antes sigue apagado y el otro sigue encendido; GET
    devuelve lo guardado. Regla: RN-VII-01, RN-XVI-03 (individual), RN-VI-04, RN-XVI-02.
    """
    db.seed_profile(MEMBER_ID)

    assert call(client, "obtenerPreferencias", MEMBER_ID).json() == DEFAULT_PREFERENCES

    off = call(client, "actualizarPreferencias", MEMBER_ID, {"notif_consumo": False})
    assert off.json() == {**DEFAULT_PREFERENCES, "notif_consumo": False}

    meta = call(client, "actualizarPreferencias", MEMBER_ID, {"base_comparacion": "meta"})
    assert meta.status_code == 200, meta.text
    expected = {"notif_consumo": False, "notif_consejos": True, "base_comparacion": "meta"}
    assert meta.json() == expected
    assert call(client, "obtenerPreferencias", MEMBER_ID).json() == expected
    assert db.committed.preferencias_usuario[MEMBER_ID] == expected
    assert db.total_commits == 2


# --- sin ficha (hueco del contrato) ---------------------------------------------------------

NO_PROFILE_CALLS = (
    ("actualizarPerfil", {"telefono": None}),
    ("guardarAvatar", {"avatar_url": f"{NEW_USER_ID}/avatar.jpg"}),
    ("eliminarAvatar", NO_BODY),
    ("obtenerPreferencias", NO_BODY),
    ("actualizarPreferencias", {"base_comparacion": "meta"}),
)


@pytest.mark.parametrize(
    ("operation_id", "body"), NO_PROFILE_CALLS, ids=[op for op, _ in NO_PROFILE_CALLS]
)
def test_operations_without_profile_answer_404_ficha_no_creada(
    client: TestClient, db: InMemoryDatabase, operation_id: str, body: Any
) -> None:
    """Sin ficha: 404 `FICHA_NO_CREADA` (cuerpo `Error`), sin commit ni filas creadas.

    El contrato no declara este 404 en estas operaciones: hueco conocido, se reporta.
    """
    db.seed_auth_user(NEW_USER_ID)
    assert operation_id in NO_PROFILE_404_OUTSIDE_CONTRACT
    assert "404" not in OPERATIONS[operation_id][2]["responses"]
    assert_error(call(client, operation_id, NEW_USER_ID, body), 404, "FICHA_NO_CREADA")
    assert db.total_commits == 0
    assert db.committed.usuarios == {}


# --- eliminar la cuenta (RN-IX-09, DC-36) ---------------------------------------------------


def _seed_household_with_two_members(db: InMemoryDatabase) -> None:
    db.seed_profile(ADMIN_ID, nombre="Administradora")
    db.seed_profile(MEMBER_ID, nombre="Miembro")
    db.seed_membership(ADMIN_MEMBRESIA_ID, ADMIN_ID, HOGAR_ID, "administrador")
    db.seed_membership(MEMBER_MEMBRESIA_ID, MEMBER_ID, HOGAR_ID, "miembro")


def test_delete_account_admin_with_other_member_gets_409_and_nothing_changes(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """Administrador con otro miembro activo → 409 `ADMIN_DEBE_TRANSFERIR`.

    Esperado: ningún commit, ninguna fila cambia y Supabase (Auth y Storage) no se llama.
    Regla: RN-IX-09, DC-36.
    """
    _seed_household_with_two_members(db)
    before = db.snapshot()

    assert_error(call(client, "eliminarCuenta", ADMIN_ID), 409, "ADMIN_DEBE_TRANSFERIR")

    assert db.committed == before
    assert db.total_commits == 0
    names = [event[0] for event in db.events]
    assert "commit" not in names
    assert "delete_auth_user" not in names and "delete_avatar_files" not in names


def test_delete_account_sole_admin_closes_membership_deletes_household_then_auth(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """Administrador único → 204: membresía cerrada, hogar borrado, Auth después del commit.

    Esperado (orden único de bloqueo del proyecto: hogar → membresía): lectura de la
    membresía sin bloqueo → bloqueo del hogar → relectura con FOR UPDATE → conteo → cierre de
    la membresía → borrado del hogar → commit → Auth → Storage (una sola vez, con la URL de la
    configuración y el id del token). Después no queda hogar, ni ficha, ni preferencias, ni usuario de
    Auth, y GET /usuarios/me da 404. Regla: RN-IX-09, DC-36, RN-I-02.
    """
    db.seed_profile(ADMIN_ID)
    db.seed_membership(ADMIN_MEMBRESIA_ID, ADMIN_ID, HOGAR_ID, "administrador")

    response = call(client, "eliminarCuenta", ADMIN_ID)

    assert response.status_code == 204, response.text
    assert db.events == [
        ("get_active_membership_of_user", ADMIN_ID, False),
        ("lock_household", HOGAR_ID),
        ("get_active_membership_of_user", ADMIN_ID, True),
        ("count_other_active_members", HOGAR_ID),
        ("close_membership", ADMIN_MEMBRESIA_ID),
        ("delete_household", HOGAR_ID),
        ("commit",),
        ("delete_auth_user", TEST_SUPABASE_URL, ADMIN_ID),
        ("delete_avatar_files", TEST_SUPABASE_URL, ADMIN_ID),
    ]
    assert db.total_commits == 1
    assert HOGAR_ID not in db.committed.hogares
    assert db.committed.hogar_miembros == {}  # cascada desde hogares
    assert ADMIN_ID not in db.committed.auth_users
    assert ADMIN_ID not in db.committed.usuarios
    assert ADMIN_ID not in db.committed.preferencias_usuario
    assert_error(call(client, "obtenerUsuarioActual", ADMIN_ID), 404, "FICHA_NO_CREADA")


def test_delete_account_member_not_alone_keeps_household(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """Miembro con otro miembro activo → 204 y el hogar sigue.

    Esperado: su membresía queda 'inactivo' con `fecha_salida` de esta petición y
    `usuario_id` en nulo por la cascada de Auth (DC-36); la del administrador sigue activa;
    no se borra el hogar. Regla: RN-IX-09, DC-36.
    """
    _seed_household_with_two_members(db)
    started = datetime.now(UTC)

    response = call(client, "eliminarCuenta", MEMBER_ID)

    finished = datetime.now(UTC)
    assert response.status_code == 204, response.text
    assert "delete_household" not in [event[0] for event in db.events]
    assert HOGAR_ID in db.committed.hogares
    closed = db.committed.hogar_miembros[MEMBER_MEMBRESIA_ID]
    assert closed["estado"] == "inactivo"
    assert started <= closed["fecha_salida"] <= finished
    assert closed["usuario_id"] is None
    admin = db.committed.hogar_miembros[ADMIN_MEMBRESIA_ID]
    assert (admin["estado"], admin["usuario_id"]) == ("activo", ADMIN_ID)
    assert MEMBER_ID not in db.committed.usuarios
    assert db.events.index(("commit",)) < db.events.index(
        ("delete_auth_user", TEST_SUPABASE_URL, MEMBER_ID)
    )


def test_delete_account_auth_failure_is_500_without_internal_detail_and_retry_is_safe(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """Falla de Supabase Auth → 500 `ERROR_INTERNO` sin exponer la excepción; reintento → 204.

    Esperado: el commit ya ocurrió (membresía cerrada y hogar borrado quedan guardados), Auth
    se llamó después del commit, Storage no se llamó y la ficha sigue (Auth no la borró). Al
    reintentar sin falla: 204, sin membresía activa que bloquee, y la cuenta desaparece.
    Regla: RN-IX-09, DC-36, DC-16 (S-01).
    """
    db.seed_profile(ADMIN_ID)
    db.seed_membership(ADMIN_MEMBRESIA_ID, ADMIN_ID, HOGAR_ID, "administrador")
    db.auth_failure = supabase_admin.SupabaseAdminError(f"{AUTH_FAILURE_DETAIL} {ADMIN_ID}")

    failed = call(client, "eliminarCuenta", ADMIN_ID)

    assert failed.status_code == 500
    assert failed.json() == INTERNAL_ERROR_BODY
    assert AUTH_FAILURE_DETAIL not in failed.text
    assert "SupabaseAdminError" not in failed.text
    names = [event[0] for event in db.events]
    assert names[-2:] == ["commit", "delete_auth_user"]
    assert "delete_avatar_files" not in names
    assert HOGAR_ID not in db.committed.hogares
    assert ADMIN_ID in db.committed.usuarios

    db.auth_failure = None
    db.events.clear()
    retried = call(client, "eliminarCuenta", ADMIN_ID)

    assert retried.status_code == 204, retried.text
    assert db.events == [
        ("get_active_membership_of_user", ADMIN_ID, False),
        ("commit",),
        ("delete_auth_user", TEST_SUPABASE_URL, ADMIN_ID),
        ("delete_avatar_files", TEST_SUPABASE_URL, ADMIN_ID),
    ]
    assert ADMIN_ID not in db.committed.usuarios
    assert ADMIN_ID not in db.committed.auth_users


def test_delete_account_storage_failure_is_best_effort(
    client: TestClient, db: InMemoryDatabase
) -> None:
    """Falla al borrar las fotos en Storage después de borrar Auth → igual 204 (mejor esfuerzo).

    Regla: RN-IX-09, RN-I-02, DC-36 (la cuenta ya no existe; solo queda en el log).
    """
    db.seed_profile(MEMBER_ID)
    db.storage_failure = supabase_admin.SupabaseAdminError("storage caído")

    response = call(client, "eliminarCuenta", MEMBER_ID)

    assert response.status_code == 204, response.text
    assert MEMBER_ID not in db.committed.auth_users
    assert [event[0] for event in db.events][-3:] == [
        "commit",
        "delete_auth_user",
        "delete_avatar_files",
    ]


def test_delete_account_without_token_is_401(client: TestClient, db: InMemoryDatabase) -> None:
    """Sin token → 401 `NO_AUTENTICADO` con `WWW-Authenticate: Bearer`; nada se toca (DC-16)."""
    db.seed_profile(MEMBER_ID)
    before = db.snapshot()

    response = call(client, "eliminarCuenta", None)

    assert_error(response, 401, "NO_AUTENTICADO")
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert db.events == []
    assert db.committed == before
