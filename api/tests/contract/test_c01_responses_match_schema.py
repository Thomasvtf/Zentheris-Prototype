"""C-01 · Contrato: Cada respuesta coincide con su esquema del contrato.

Esperado: Sin errores (validación automática). Regla: DC-47.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Llama a la app real (`create_app`, JWKS de prueba, sin base ni red) con las funciones de
`app.data.*` reemplazadas por un almacén en memoria, y valida con `jsonschema` cada
respuesta (éxito y error) contra el esquema que el contrato declara para esa operación y ese
código. Los `$ref` se resuelven desde docs/api/zentheris-api.yaml (cargado una vez).

Vista de respuesta del esquema: un objeto con `properties` y sin `additionalProperties`
explícito no admite campos que el contrato no declara; las propiedades `writeOnly` no pueden
salir en una respuesta; las `readOnly` (como `UsuarioActual.correo`) sí salen y siguen siendo
obligatorias. `oneOf` con `type: 'null'` valida tal cual (null o el objeto, nunca ambos).

Cubre `obtenerSalud`, las 8 operaciones de la fase 3 (Usuario): RN-IX-01, RN-IX-07, RN-IX-09,
RN-I-02, RN-VII-01, RN-VI-04, RN-XVI-02, RN-XVI-03; y `crearHogarOnboarding` (fase 4): RN-X-02,
RN-X-03, RN-X-04, RN-IV-01, RN-IV-07, RN-II-01, RN-II-03; errores DC-16; y las 3 consultas de
consumo de la fase 6 (`obtenerConsumoActual`, `obtenerConsumoZonas`, `obtenerConsumoZona`):
RN-XI-01, RN-XI-03 a RN-XI-08, RN-XVII-01, RN-IV-05, DC-34, con el servicio real sobre datos en
memoria construidos con los promedios de las personalidades; y `obtenerHistorial` (fase 7):
RN-XIII-01 a RN-XIII-06, RN-XVII-02, RN-I-03, RN-IV-05, DC-29 a DC-31, DC-34 (v0.2.9:
`PuntoSerie.zonas` solo con el filtro General, en el orden de `participacion_zonas`); y las 5
operaciones de alertas y consejos (fase 8: `listarAlertas`, `contarAlertasNoLeidas`,
`marcarAlertasLeidas`, `listarConsejos`, `actualizarEstadoConsejo`) con el servicio reemplazado
por un doble: RN-XIV-01 a RN-XIV-05, RN-XV-02 a RN-XV-06, RN-XII-02, RN-I-03, RN-VI-05; y las 11
operaciones de miembros e invitaciones (fase 9) con el servicio reemplazado por un doble:
RN-II-01 a RN-II-04, RN-X-01, RN-X-05 a RN-X-08, RN-XVI-07, DC-41, DC-42.
Las demás: TODO(C-01).
"""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.config import Settings, get_settings
from app.data import goals as goals_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import readings as readings_data
from app.data import tariffs as tariffs_data
from app.data import users as users_data
from app.data.database import get_session
from app.data.memberships import (
    ActiveMembershipExistsError,
    ActiveMembershipRow,
    MembershipSummaryRow,
)
from app.data.users import PreferencesRow, UserProfileRow
from app.domain import states
from app.domain.formats import zone_name
from app.domain.simulator import TIMEZONE
from app.domain.zone_rules import BASIC_ZONES, PERSONALITIES, ZONE_TYPES
from app.errors import NOT_FOUND_MESSAGE, ApiError, CodigoError
from app.main import API_PREFIX, create_app
from app.schemas.alerts_tips import (
    Alerta,
    AlertasLista,
    AlertasMarcadas,
    AlertasMarcar,
    AlertasNoLeidas,
    CategoriaAlerta,
    Consejo,
    ConsejoEstadoActualizar,
    ConsejosLista,
)
from app.schemas.common import Rol
from app.schemas.households import Permisos, PermisosActualizar
from app.schemas.members_invitations import (
    InvitacionCrear,
    InvitacionesRecibidasLista,
    InvitacionPendiente,
    InvitacionRecibida,
    InvitacionToken,
    Miembro,
    MiembrosHogar,
)
from app.schemas.users import MembresiaResumen
from app.services import alerts_tips as alerts_tips_service
from app.services import consumption as consumption_service
from app.services import hour_recovery, supabase_admin
from app.services import members_invitations as members_service
from app.services.backend_texts import get_backend_texts
from tests.helpers.auth import (
    TEST_SUPABASE_URL,
    auth_header,
    install_test_jwks,
    make_membership_row,
    make_test_settings,
    make_token,
)
from tests.helpers.onboarding import (
    REFERENCE_HOUSEHOLDS,
    FakeDatabase,
    install_fake_database,
    missing_profile_error,
)
from tests.helpers.personalities import PERSONALITY_ORDER, load_personalities
from tests.services.consumption_fakes import (
    FakeConsumptionDatabase,
    hourly_series,
    install_fake_consumption_database,
)
from tests.services.consumption_fakes import FakeSession as ConsumptionFakeSession

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "docs/api/zentheris-api.yaml"
CONTRACT: dict[str, Any] = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
HTTP_METHODS = ("get", "post", "put", "patch", "delete")

USER_ID = UUID("6f1c2d3e-4a5b-4c6d-8e7f-90a1b2c3d4e5")
CORREO = "persona@example.com"
HOGAR_ID = UUID("11111111-2222-4333-8444-555555555555")
MEMBRESIA_ID = UUID("99999999-8888-4777-8666-555555555555")
DEFAULT_PREFERENCES = PreferencesRow(
    notif_consumo=True, notif_consejos=True, base_comparacion="promedio"
)

PHASE_OPERATIONS = frozenset(
    {
        "obtenerUsuarioActual",
        "crearFichaUsuario",
        "actualizarPerfil",
        "eliminarCuenta",
        "guardarAvatar",
        "eliminarAvatar",
        "obtenerPreferencias",
        "actualizarPreferencias",
    }
)
CONSUMPTION_OPERATIONS = frozenset(
    {"obtenerConsumoActual", "obtenerConsumoZonas", "obtenerConsumoZona"}
)
HISTORY_OPERATION = "obtenerHistorial"
ALERTS_OPERATIONS = frozenset(
    {
        "listarAlertas",
        "contarAlertasNoLeidas",
        "marcarAlertasLeidas",
        "listarConsejos",
        "actualizarEstadoConsejo",
    }
)
MEMBERS_OPERATIONS = frozenset(
    {
        "listarMiembros",
        "actualizarPermisos",
        "expulsarMiembro",
        "transferirAdministracion",
        "salirDelHogar",
        "crearInvitacion",
        "revocarInvitacion",
        "listarInvitacionesRecibidas",
        "resolverTokenInvitacion",
        "aceptarInvitacion",
        "rechazarInvitacion",
    }
)
# Operaciones con C-01 real: las de la fase 3, el onboarding, la salud (sin autenticación), las
# consultas de consumo de la fase 6, el historial de la fase 7, las alertas y consejos de la 8 y
# los miembros e invitaciones de la 9.
COVERED_OPERATIONS = (
    PHASE_OPERATIONS | CONSUMPTION_OPERATIONS | ALERTS_OPERATIONS | MEMBERS_OPERATIONS
) | {
    "obtenerSalud",
    "crearHogarOnboarding",
    HISTORY_OPERATION,
}
# Respuestas del contrato que no se pueden provocar: `/salud` no tiene parámetros ni cuerpo, así
# que ninguna petición a esa operación da un 4XX propio; y `transferirAdministracion` declara 409,
# pero ninguna regla del servicio lo produce (destino inexistente o inactivo → 404; la propia
# membresía → 422).
# TODO(pendiente: el contrato declara 409 en transferirAdministracion pero ninguna regla lo produce)
UNREACHABLE_RANGES = frozenset({("obtenerSalud", "4XX"), ("transferirAdministracion", "409")})
# Respuestas que necesitan un cliente propio (el 500 no se propaga) y tienen su prueba aparte.
COVERED_BY_OWN_TEST = frozenset({("eliminarCuenta", "500")})


# --- contrato ---------------------------------------------------------------------------


def _operations() -> dict[str, tuple[str, str, dict[str, Any]]]:
    return {
        op["operationId"]: (method, path, op)
        for path, item in CONTRACT["paths"].items()
        for method, op in item.items()
        if method in HTTP_METHODS
    }


OPERATIONS = _operations()


def _lookup(ref: str) -> dict[str, Any]:
    assert ref.startswith("#/"), ref
    node: Any = CONTRACT
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def resolve(node: Any) -> Any:
    """Copia del esquema con todos los `$ref` internos sustituidos (el contrato no es recursivo)."""
    if isinstance(node, list):
        return [resolve(item) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        siblings = {k: resolve(v) for k, v in node.items() if k != "$ref"}
        return {**resolve(_lookup(node["$ref"])), **siblings}
    return {k: resolve(v) for k, v in node.items()}


def response_view(schema: Any) -> Any:
    """Esquema ya resuelto, visto como respuesta (ver la docstring del módulo)."""
    if isinstance(schema, list):
        return [response_view(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out = dict(schema)
    for key in ("items", "additionalProperties", "not"):
        if isinstance(out.get(key), dict):
            out[key] = response_view(out[key])
    for key in ("oneOf", "anyOf", "allOf"):
        if key in out:
            out[key] = [response_view(item) for item in out[key]]
    if "properties" in out:
        properties = {
            name: response_view(sub)
            for name, sub in out["properties"].items()
            if not sub.get("writeOnly")
        }
        out["properties"] = properties
        if "required" in out:
            out["required"] = [name for name in out["required"] if name in properties]
        out.setdefault("additionalProperties", False)
    return out


def contract_response(operation_id: str, status: int) -> dict[str, Any]:
    """Respuesta declarada (con `components.responses` resuelto); falla si no está declarada."""
    _method, _path, op = OPERATIONS[operation_id]
    declared = op["responses"]
    assert str(status) in declared, f"{operation_id} no declara {status}: {sorted(declared)}"
    return resolve(declared[str(status)])


def assert_matches_contract(operation_id: str, response: Any) -> None:
    """El estado está declarado y el cuerpo valida contra su esquema (o va vacío si no hay)."""
    declared = contract_response(operation_id, response.status_code)
    content = declared.get("content")
    if content is None:
        assert response.content == b"", response.content
        return
    assert response.headers["content-type"].startswith("application/json")
    schema = response_view(content["application/json"]["schema"])
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(response.json()), key=lambda e: list(e.path))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors]


def assert_matches_error_schema(response: Any) -> None:
    """Para un estado que el contrato no declara en la operación: al menos el esquema `Error`."""
    schema = response_view(resolve({"$ref": "#/components/schemas/Error"}))
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = list(validator.iter_errors(response.json()))
    assert not errors, [e.message for e in errors]


# --- capa de datos falsa ------------------------------------------------------------------


class RecordingSession:
    """Sesión de la petición: solo cuenta commits y rollbacks; cualquier otro uso falla (sin SQL)."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"RecordingSession no admite `{name}`: reemplaza la función de datos.")


@dataclass
class FakeStore:
    """Estado en memoria del usuario de la prueba y registro de llamadas a Supabase."""

    session: RecordingSession = field(default_factory=RecordingSession)
    profile: UserProfileRow | None = None
    membership: MembershipSummaryRow | None = None
    other_members: int = 0
    auth_user_missing: bool = False  # token vigente de una cuenta ya borrada en Supabase Auth
    auth_delete_fails: bool = False
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def _check(self, session: object, usuario_id: UUID) -> None:
        # El router pasa la sesión de `get_session` y el id del token.
        assert session is self.session
        assert usuario_id == USER_ID

    # app.data.users
    def get_user_profile(self, session: object, usuario_id: UUID) -> UserProfileRow | None:
        self._check(session, usuario_id)
        return self.profile

    def insert_user_with_default_preferences(
        self, session: object, usuario_id: UUID, nombre_completo: str, telefono: str | None
    ) -> bool:
        self._check(session, usuario_id)
        if self.auth_user_missing:
            raise users_data.AuthUserMissingError()
        if self.profile is not None:
            return False
        self.profile = UserProfileRow(
            id=usuario_id,
            nombre_completo=nombre_completo,
            telefono=telefono,
            avatar_url=None,
            preferencias=DEFAULT_PREFERENCES,
        )
        return True

    def update_user_profile(
        self, session: object, usuario_id: UUID, changes: Mapping[str, str | None]
    ) -> bool:
        self._check(session, usuario_id)
        if self.profile is None:
            return False
        self.profile = replace(self.profile, **changes)
        return True

    def set_avatar_url(self, session: object, usuario_id: UUID, avatar_url: str | None) -> bool:
        self._check(session, usuario_id)
        if self.profile is None:
            return False
        self.profile = replace(self.profile, avatar_url=avatar_url)
        return True

    def get_preferences(self, session: object, usuario_id: UUID) -> PreferencesRow | None:
        self._check(session, usuario_id)
        return None if self.profile is None else self.profile.preferencias

    def lock_user_profile(self, session: object, usuario_id: UUID) -> UserProfileRow | None:
        self._check(session, usuario_id)
        return self.profile

    def delete_user_profile(self, session: object, usuario_id: UUID) -> bool:
        self._check(session, usuario_id)
        self.calls.append(("delete_user_profile", usuario_id))
        deleted = self.profile is not None
        self.profile = None
        return deleted

    def update_preferences(
        self, session: object, usuario_id: UUID, changes: Mapping[str, bool | str]
    ) -> PreferencesRow | None:
        self._check(session, usuario_id)
        if self.profile is None:
            return None
        preferences = replace(self.profile.preferencias, **changes)
        self.profile = replace(self.profile, preferencias=preferences)
        return preferences

    # app.data.memberships
    def get_active_membership_of_user(
        self, session: object, usuario_id: UUID, *, for_update: bool = False
    ) -> MembershipSummaryRow | None:
        self._check(session, usuario_id)
        return self.membership

    def count_other_active_members(self, session: object, hogar_id: UUID, usuario_id: UUID) -> int:
        self._check(session, usuario_id)
        return self.other_members

    def close_membership(self, session: object, membresia_id: UUID, closed_at: datetime) -> None:
        assert session is self.session
        self.calls.append(("close_membership", membresia_id))

    # app.data.households
    def lock_household(self, session: object, hogar_id: UUID) -> None:
        assert session is self.session

    def delete_household(self, session: object, hogar_id: UUID) -> None:
        assert session is self.session
        self.calls.append(("delete_household", hogar_id))

    # app.services.supabase_admin
    def delete_auth_user(self, settings: Settings, usuario_id: UUID) -> None:
        self.calls.append(("delete_auth_user", settings.supabase_url, usuario_id))
        if self.auth_delete_fails:
            raise supabase_admin.SupabaseAdminError("fallo simulado")

    def delete_avatar_files(self, settings: Settings, usuario_id: UUID) -> None:
        self.calls.append(("delete_avatar_files", settings.supabase_url, usuario_id))


def install_store(monkeypatch: pytest.MonkeyPatch, store: FakeStore) -> None:
    for module, names in (
        (
            users_data,
            (
                "get_user_profile",
                "insert_user_with_default_preferences",
                "update_user_profile",
                "set_avatar_url",
                "get_preferences",
                "update_preferences",
                "lock_user_profile",
                "delete_user_profile",
            ),
        ),
        (
            memberships_data,
            ("get_active_membership_of_user", "count_other_active_members", "close_membership"),
        ),
        (households_data, ("lock_household", "delete_household")),
        (supabase_admin, ("delete_auth_user", "delete_avatar_files")),
    ):
        for name in names:
            assert hasattr(module, name), f"{module.__name__}.{name}"
            monkeypatch.setattr(module, name, getattr(store, name))


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> FakeStore:
    store = FakeStore()
    install_store(monkeypatch, store)
    install_test_jwks(monkeypatch)
    return store


@pytest.fixture
def client(store: FakeStore) -> Iterator[TestClient]:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_settings] = make_test_settings

    def session_override() -> Iterator[RecordingSession]:
        yield store.session

    app.dependency_overrides[get_session] = session_override
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- estados de partida -------------------------------------------------------------------


def with_profile(store: FakeStore) -> None:
    store.profile = UserProfileRow(
        id=USER_ID,
        nombre_completo="Laura Gómez",
        telefono=None,
        avatar_url=None,
        preferencias=DEFAULT_PREFERENCES,
    )


def with_full_profile(store: FakeStore) -> None:
    with_profile(store)
    assert store.profile is not None
    store.profile = replace(
        store.profile,
        telefono="3001234567",
        avatar_url=f"{USER_ID}/avatar.png",
        preferencias=PreferencesRow(
            notif_consumo=False, notif_consejos=True, base_comparacion="meta"
        ),
    )
    store.membership = MembershipSummaryRow(
        membresia_id=MEMBRESIA_ID, hogar_id=HOGAR_ID, rol="miembro"
    )


def with_sole_admin(store: FakeStore) -> None:
    with_profile(store)
    store.membership = MembershipSummaryRow(
        membresia_id=MEMBRESIA_ID, hogar_id=HOGAR_ID, rol="administrador"
    )
    store.other_members = 0


def with_admin_and_others(store: FakeStore) -> None:
    with_sole_admin(store)
    store.other_members = 2


def with_member_and_others(store: FakeStore) -> None:
    with_full_profile(store)
    store.other_members = 1


# --- casos --------------------------------------------------------------------------------

NO_BODY = object()


@dataclass(frozen=True)
class Case:
    name: str
    operation_id: str
    status: int
    body: Any = NO_BODY
    setup: Callable[[Any], None] | None = None  # recibe el doble de datos del caso
    authenticated: bool = True
    codigo: str | None = None
    commits: int | None = None


CASES: tuple[Case, ...] = (
    # obtenerSalud
    Case("activo", "obtenerSalud", 200, authenticated=False),
    # obtenerUsuarioActual
    Case("ficha-sin-membresia", "obtenerUsuarioActual", 200, setup=with_profile, commits=0),
    Case("ficha-con-membresia", "obtenerUsuarioActual", 200, setup=with_full_profile, commits=0),
    Case("sin-token", "obtenerUsuarioActual", 401, authenticated=False, codigo="NO_AUTENTICADO"),
    Case("sin-ficha", "obtenerUsuarioActual", 404, codigo="FICHA_NO_CREADA"),
    # crearFichaUsuario
    Case(
        "crea",
        "crearFichaUsuario",
        201,
        body={"nombre_completo": "Laura Gómez", "telefono": "3001234567"},
        commits=1,
    ),
    Case(
        "crea-sin-telefono",
        "crearFichaUsuario",
        201,
        body={"nombre_completo": "Laura Gómez"},
        commits=1,
    ),
    Case(
        "sin-token",
        "crearFichaUsuario",
        401,
        body={"nombre_completo": "Laura"},
        authenticated=False,
        codigo="NO_AUTENTICADO",
    ),
    Case(
        "cuenta-borrada",
        "crearFichaUsuario",
        401,
        body={"nombre_completo": "Laura"},
        setup=lambda store: setattr(store, "auth_user_missing", True),
        codigo="NO_AUTENTICADO",
        commits=0,
    ),
    Case(
        "ya-existe",
        "crearFichaUsuario",
        409,
        body={"nombre_completo": "Laura"},
        setup=with_profile,
        codigo="FICHA_EXISTENTE",
        commits=0,
    ),
    Case("sin-nombre", "crearFichaUsuario", 422, body={"telefono": None}, codigo="VALIDACION"),
    Case(
        "nombre-vacio", "crearFichaUsuario", 422, body={"nombre_completo": ""}, codigo="VALIDACION"
    ),
    Case(
        "campo-extra",
        "crearFichaUsuario",
        422,
        body={"nombre_completo": "Laura", "correo": "otra@example.com"},
        codigo="VALIDACION",
    ),
    # actualizarPerfil
    Case(
        "cambia-nombre",
        "actualizarPerfil",
        200,
        body={"nombre_completo": "Laura G."},
        setup=with_full_profile,
        commits=1,
    ),
    Case(
        "borra-telefono",
        "actualizarPerfil",
        200,
        body={"telefono": None},
        setup=with_full_profile,
        commits=1,
    ),
    Case(
        "sin-token",
        "actualizarPerfil",
        401,
        body={"telefono": None},
        authenticated=False,
        codigo="NO_AUTENTICADO",
    ),
    Case(
        "cuerpo-vacio",
        "actualizarPerfil",
        422,
        body={},
        setup=with_profile,
        codigo="VALIDACION",
        commits=0,
    ),
    Case(
        "nombre-null",
        "actualizarPerfil",
        422,
        body={"nombre_completo": None},
        setup=with_profile,
        codigo="VALIDACION",
        commits=0,
    ),
    Case(
        "correo-no-editable",
        "actualizarPerfil",
        422,
        body={"correo": "otra@example.com"},
        setup=with_profile,
        codigo="VALIDACION",
        commits=0,
    ),
    # eliminarCuenta
    Case("sin-membresia", "eliminarCuenta", 204, setup=with_profile, commits=1),
    Case("miembro-con-otros", "eliminarCuenta", 204, setup=with_member_and_others, commits=1),
    Case("admin-unico", "eliminarCuenta", 204, setup=with_sole_admin, commits=1),
    Case("sin-token", "eliminarCuenta", 401, authenticated=False, codigo="NO_AUTENTICADO"),
    Case(
        "admin-con-otros",
        "eliminarCuenta",
        409,
        setup=with_admin_and_others,
        codigo="ADMIN_DEBE_TRANSFERIR",
        commits=0,
    ),
    # guardarAvatar
    Case(
        "guarda",
        "guardarAvatar",
        200,
        body={"avatar_url": f"{USER_ID}/avatar.webp"},
        setup=with_profile,
        commits=1,
    ),
    Case(
        "sin-token",
        "guardarAvatar",
        401,
        body={"avatar_url": f"{USER_ID}/avatar.jpg"},
        authenticated=False,
        codigo="NO_AUTENTICADO",
    ),
    Case(
        "carpeta-ajena",
        "guardarAvatar",
        422,
        body={"avatar_url": "00000000-0000-4000-8000-000000000000/avatar.jpg"},
        setup=with_profile,
        codigo="VALIDACION",
        commits=0,
    ),
    Case("ruta-vacia", "guardarAvatar", 422, body={"avatar_url": ""}, codigo="VALIDACION"),
    # eliminarAvatar
    Case("elimina", "eliminarAvatar", 204, setup=with_full_profile, commits=1),
    Case("sin-token", "eliminarAvatar", 401, authenticated=False, codigo="NO_AUTENTICADO"),
    # obtenerPreferencias
    Case("lee", "obtenerPreferencias", 200, setup=with_full_profile, commits=0),
    Case("sin-token", "obtenerPreferencias", 401, authenticated=False, codigo="NO_AUTENTICADO"),
    # actualizarPreferencias
    Case(
        "cambia-base",
        "actualizarPreferencias",
        200,
        body={"base_comparacion": "meta"},
        setup=with_profile,
        commits=1,
    ),
    Case(
        "cambia-interruptores",
        "actualizarPreferencias",
        200,
        body={"notif_consumo": False, "notif_consejos": False},
        setup=with_profile,
        commits=1,
    ),
    Case(
        "sin-token",
        "actualizarPreferencias",
        401,
        body={"notif_consumo": False},
        authenticated=False,
        codigo="NO_AUTENTICADO",
    ),
    Case(
        "cuerpo-vacio",
        "actualizarPreferencias",
        422,
        body={},
        setup=with_profile,
        codigo="VALIDACION",
        commits=0,
    ),
    Case(
        "base-invalida",
        "actualizarPreferencias",
        422,
        body={"base_comparacion": "mediana"},
        setup=with_profile,
        codigo="VALIDACION",
        commits=0,
    ),
    Case(
        "interruptor-null",
        "actualizarPreferencias",
        422,
        body={"notif_consumo": None},
        setup=with_profile,
        codigo="VALIDACION",
        commits=0,
    ),
    Case(
        "campo-extra",
        "actualizarPreferencias",
        422,
        body={"meta_kwh": 120},
        setup=with_profile,
        codigo="VALIDACION",
        commits=0,
    ),
    # 404 FICHA_NO_CREADA: la persona aún no creó su ficha (contrato 0.2.7)
    Case(
        "sin-ficha",
        "actualizarPerfil",
        404,
        body={"telefono": None},
        codigo="FICHA_NO_CREADA",
        commits=0,
    ),
    Case(
        "sin-ficha",
        "guardarAvatar",
        404,
        body={"avatar_url": f"{USER_ID}/avatar.jpg"},
        codigo="FICHA_NO_CREADA",
        commits=0,
    ),
    Case("sin-ficha", "eliminarAvatar", 404, codigo="FICHA_NO_CREADA", commits=0),
    Case("sin-ficha", "obtenerPreferencias", 404, codigo="FICHA_NO_CREADA", commits=0),
    Case(
        "sin-ficha",
        "actualizarPreferencias",
        404,
        body={"notif_consejos": False},
        codigo="FICHA_NO_CREADA",
        commits=0,
    ),
)


# --- casos de crearHogarOnboarding --------------------------------------------------------

HOUSEHOLD_NAME = "Casa Gómez"
INTERNAL_DETAIL = "detalle interno de la base"


def onboarding_body(housing: str = "apartamento", zones: Any = BASIC_ZONES, **changes: Any) -> Any:
    zones = list(zones) if isinstance(zones, tuple) else zones
    return {"nombre_hogar": HOUSEHOLD_NAME, "tipo_vivienda": housing, "zonas": zones, **changes}


def without(field_name: str) -> dict[str, Any]:
    return {name: value for name, value in onboarding_body().items() if name != field_name}


def with_active_membership(db: FakeDatabase) -> None:
    db.membership = MembershipSummaryRow(
        membresia_id=MEMBRESIA_ID, hogar_id=HOGAR_ID, rol="miembro"
    )


def failing_at(step: str, error: Exception) -> Callable[[FakeDatabase], None]:
    return lambda db: db.failures.update({step: error})


def onboarding_error(name: str, status: int, codigo: str, body: Any = NO_BODY, **kw: Any) -> Case:
    body = onboarding_body() if body is NO_BODY else body
    return Case(name, "crearHogarOnboarding", status, body=body, codigo=codigo, commits=0, **kw)


ONBOARDING_CASES: tuple[Case, ...] = (
    # 201: el hogar de referencia de cada personalidad, el máximo y el mínimo de zonas
    *(
        Case(
            f"crea-{name.split()[1]}",
            "crearHogarOnboarding",
            201,
            body=onboarding_body(*REFERENCE_HOUSEHOLDS[name]),
            commits=1,
        )
        for name in PERSONALITY_ORDER
    ),
    Case(
        "crea-nueve-zonas",
        "crearHogarOnboarding",
        201,
        body=onboarding_body("duplex", ZONE_TYPES),
        commits=1,
    ),
    Case(
        "crea-tres-zonas",
        "crearHogarOnboarding",
        201,
        body=onboarding_body("apartaestudio", ("cocina", "sala", "bano")),
        commits=1,
    ),
    # 401
    onboarding_error("sin-token", 401, "NO_AUTENTICADO", authenticated=False),
    onboarding_error(
        "sin-ficha",
        404,
        "FICHA_NO_CREADA",
        setup=failing_at("insert_admin_membership", missing_profile_error()),
    ),
    onboarding_error(
        "nombre-de-81-caracteres", 422, "VALIDACION", onboarding_body(nombre_hogar="a" * 81)
    ),
    # 409: ya tiene un hogar, también si otra petición suya se adelantó (RN-II-01)
    onboarding_error(
        "ya-tiene-hogar", 409, "MEMBRESIA_ACTIVA_EXISTENTE", setup=with_active_membership
    ),
    onboarding_error(
        "otra-peticion-se-adelanto",
        409,
        "MEMBRESIA_ACTIVA_EXISTENTE",
        setup=failing_at("insert_admin_membership", ActiveMembershipExistsError(INTERNAL_DETAIL)),
    ),
    # 422 de las reglas de zonas (RN-X-02)
    onboarding_error(
        "extra-en-apartaestudio",
        422,
        "ZONAS_NO_PERMITIDAS",
        onboarding_body("apartaestudio", ("cocina", "sala", "dormitorio", "garaje")),
    ),
    onboarding_error(
        "falta-una-basica",
        422,
        "ZONAS_BASICAS_FALTANTES",
        onboarding_body("casa", ("cocina", "sala", "dormitorio", "oficina")),
    ),
    onboarding_error(
        "seis-en-apartaestudio",
        422,
        "CANTIDAD_ZONAS_INVALIDA",
        onboarding_body("apartaestudio", (*BASIC_ZONES, "oficina", "lavanderia")),
    ),
    onboarding_error(
        "dos-basicas-en-apartaestudio",
        422,
        "CANTIDAD_ZONAS_INVALIDA",
        onboarding_body("apartaestudio", ("cocina", "sala", "oficina")),
    ),
    # Pydantic no comprueba `uniqueItems`: de 3 a 9 elementos llegan al servicio.
    onboarding_error(
        "repetida-en-tres",
        422,
        "ZONAS_DUPLICADAS",
        onboarding_body("apartaestudio", ("cocina", "cocina", "sala")),
    ),
    onboarding_error(
        "repetida-con-todas-las-basicas",
        422,
        "ZONAS_DUPLICADAS",
        onboarding_body("apartamento", (*BASIC_ZONES, "bano")),
    ),
    onboarding_error(
        "repetida-en-nueve",
        422,
        "ZONAS_DUPLICADAS",
        onboarding_body("duplex", (*ZONE_TYPES[:8], "cocina")),
    ),
    # 422 del esquema: no llega al servicio
    onboarding_error("sin-zonas", 422, "VALIDACION", onboarding_body(zones=[])),
    onboarding_error("dos-zonas", 422, "VALIDACION", onboarding_body(zones=["cocina", "sala"])),
    onboarding_error(
        "diez-zonas", 422, "VALIDACION", onboarding_body("duplex", (*ZONE_TYPES, "cocina"))
    ),
    onboarding_error(
        "zona-desconocida", 422, "VALIDACION", onboarding_body(zones=(*BASIC_ZONES, "piscina"))
    ),
    onboarding_error("zonas-null", 422, "VALIDACION", onboarding_body(zones=None)),
    onboarding_error("zona-null", 422, "VALIDACION", onboarding_body(zones=(*BASIC_ZONES, None))),
    onboarding_error("vivienda-desconocida", 422, "VALIDACION", onboarding_body("finca")),
    onboarding_error("vivienda-null", 422, "VALIDACION", onboarding_body(tipo_vivienda=None)),
    onboarding_error("nombre-vacio", 422, "VALIDACION", onboarding_body(nombre_hogar="")),
    onboarding_error("nombre-null", 422, "VALIDACION", onboarding_body(nombre_hogar=None)),
    onboarding_error("nombre-numero", 422, "VALIDACION", onboarding_body(nombre_hogar=7)),
    *(
        onboarding_error(f"falta-{name}", 422, "VALIDACION", without(name))
        for name in ("nombre_hogar", "tipo_vivienda", "zonas")
    ),
    # La personalidad la calcula el servidor: el cliente no la envía (RN-X-04)
    *(
        onboarding_error(f"extra-{name}", 422, "VALIDACION", onboarding_body(**{name: value}))
        for name, value in (
            ("personalidad", "Consumo amplio"),
            ("perfil_simulacion_id", str(HOGAR_ID)),
            ("estrato", 3),
        )
    ),
    onboarding_error("cuerpo-vacio", 422, "VALIDACION", {}),
    onboarding_error("cuerpo-lista", 422, "VALIDACION", []),
    # 500: falla cualquier paso y no queda nada (RN-X-03)
    *(
        onboarding_error(
            f"falla-{step}",
            500,
            "BACKFILL_FALLIDO",
            setup=failing_at(step, RuntimeError(INTERNAL_DETAIL)),
        )
        for step in ("insert_household", "insert_readings_batch", "commit")
    ),
)


def send(client: TestClient, case: Case) -> Any:
    method, path, _op = OPERATIONS[case.operation_id]
    headers = auth_header(make_token(USER_ID, CORREO)) if case.authenticated else {}
    kwargs: dict[str, Any] = {"headers": headers}
    if case.body is not NO_BODY:
        kwargs["json"] = case.body
    return client.request(method.upper(), API_PREFIX + path, **kwargs)


def test_cases_cover_every_declared_response_of_the_phase() -> None:
    """Cada (operación, código) que el contrato declara para las operaciones cubiertas tiene al
    menos un caso (salvo los rangos imposibles de provocar, `UNREACHABLE_RANGES`)."""
    declared = {
        (operation_id, int(code))
        for operation_id in COVERED_OPERATIONS
        for code in OPERATIONS[operation_id][2]["responses"]
        if (operation_id, str(code)) not in UNREACHABLE_RANGES | COVERED_BY_OWN_TEST
    }
    cases = (
        CASES + ONBOARDING_CASES + CONSUMPTION_CASES + HISTORY_CASES + ALERTS_CASES + MEMBERS_CASES
    )
    covered = {(case.operation_id, case.status) for case in cases}
    assert covered == declared
    assert len({(c.operation_id, c.name) for c in cases}) == len(cases)


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c.operation_id}-{c.status}-{c.name}")
def test_response_matches_contract_schema(case: Case, client: TestClient, store: FakeStore) -> None:
    if case.setup is not None:
        case.setup(store)
    response = send(client, case)
    assert response.status_code == case.status, response.text
    assert_matches_contract(case.operation_id, response)
    if case.codigo is not None:
        assert response.json()["codigo"] == case.codigo
    if case.status == 401:
        assert response.headers.get("WWW-Authenticate") == "Bearer"
    if case.commits is not None:
        assert store.session.commits == case.commits


# --- comprobaciones de la capa HTTP sobre los datos de la respuesta ------------------------


def test_current_user_body_uses_token_email_and_stored_profile(
    client: TestClient, store: FakeStore
) -> None:
    with_full_profile(store)
    body = send(client, Case("x", "obtenerUsuarioActual", 200)).json()
    assert body == {
        "id": str(USER_ID),
        "correo": CORREO,
        "nombre_completo": "Laura Gómez",
        "telefono": "3001234567",
        "avatar_url": f"{USER_ID}/avatar.png",
        "preferencias": {
            "notif_consumo": False,
            "notif_consejos": True,
            "base_comparacion": "meta",
        },
        "membresia": {
            "membresia_id": str(MEMBRESIA_ID),
            "hogar_id": str(HOGAR_ID),
            "rol": "miembro",
        },
    }


def test_new_profile_has_nulls_and_default_preferences(
    client: TestClient, store: FakeStore
) -> None:
    body = send(
        client, Case("x", "crearFichaUsuario", 201, body={"nombre_completo": "Laura Gómez"})
    ).json()
    assert body["telefono"] is None
    assert body["avatar_url"] is None
    assert body["membresia"] is None
    assert body["preferencias"] == {
        "notif_consumo": True,
        "notif_consejos": True,
        "base_comparacion": "promedio",
    }


def test_patch_null_phone_clears_it(client: TestClient, store: FakeStore) -> None:
    with_full_profile(store)
    body = send(client, Case("x", "actualizarPerfil", 200, body={"telefono": None})).json()
    assert body["telefono"] is None
    assert body["nombre_completo"] == "Laura Gómez"


def test_delete_account_passes_settings_and_token_user_to_supabase(
    client: TestClient, store: FakeStore
) -> None:
    with_sole_admin(store)
    response = send(client, Case("x", "eliminarCuenta", 204))
    assert response.status_code == 204
    assert store.calls == [
        ("close_membership", MEMBRESIA_ID),
        ("delete_household", HOGAR_ID),
        ("delete_user_profile", USER_ID),  # la ficha se borra en la transacción (DC-36)
        ("delete_auth_user", TEST_SUPABASE_URL, USER_ID),
        ("delete_avatar_files", TEST_SUPABASE_URL, USER_ID),
    ]


def test_delete_account_conflict_touches_nothing(client: TestClient, store: FakeStore) -> None:
    with_admin_and_others(store)
    assert send(client, Case("x", "eliminarCuenta", 409)).status_code == 409
    assert store.calls == []


# --- fallo de Supabase al eliminar la cuenta -----------------------------------------------


def test_delete_account_supabase_failure_is_500(store: FakeStore) -> None:
    """Si falla el borrado en Supabase Auth: 500 `ERROR_INTERNO` con el esquema del contrato.

    La baja en la base ya quedó confirmada (commit) y reintentar es seguro.
    """
    with_profile(store)
    store.auth_delete_fails = True
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_settings] = make_test_settings

    def session_override() -> Iterator[RecordingSession]:
        yield store.session

    app.dependency_overrides[get_session] = session_override
    client = TestClient(app, raise_server_exceptions=False)
    response = send(client, Case("x", "eliminarCuenta", 500))
    assert response.status_code == 500
    assert_matches_contract("eliminarCuenta", response)
    assert response.json()["codigo"] == "ERROR_INTERNO"
    assert "fallo simulado" not in response.text
    assert store.session.commits == 1


# --- crearHogarOnboarding -----------------------------------------------------------------


@pytest.fixture
def onboarding_db(store: FakeStore, monkeypatch: pytest.MonkeyPatch) -> FakeDatabase:
    """Datos del onboarding en memoria; el servicio, las zonas y el simulador son los reales."""
    db = install_fake_database(monkeypatch)
    store.session = db  # type: ignore[assignment]  # la sesión que entrega `get_session`
    return db


@pytest.mark.parametrize("case", ONBOARDING_CASES, ids=lambda c: f"{c.status}-{c.name}")
def test_onboarding_response_matches_contract_schema(
    case: Case, client: TestClient, onboarding_db: FakeDatabase
) -> None:
    if case.setup is not None:
        case.setup(onboarding_db)
    response = send(client, case)
    assert response.status_code == case.status, response.text
    assert_matches_contract("crearHogarOnboarding", response)
    assert onboarding_db.commits == case.commits
    if case.status == 201:
        return
    assert response.json()["codigo"] == case.codigo
    assert (response.headers.get("WWW-Authenticate") == "Bearer") == (case.status == 401)
    assert INTERNAL_DETAIL not in response.text
    onboarding_db.assert_nothing_saved()
    if case.status in (401, 422):
        assert onboarding_db.events == []  # sin tocar la base


def test_onboarding_cases_cover_every_code_of_the_operation() -> None:
    """Los códigos que el contrato nombra para `crearHogarOnboarding`, ni uno más."""
    assert {case.codigo for case in ONBOARDING_CASES if case.codigo} == {
        "NO_AUTENTICADO",
        "FICHA_NO_CREADA",
        "MEMBRESIA_ACTIVA_EXISTENTE",
        "ZONAS_NO_PERMITIDAS",
        "ZONAS_BASICAS_FALTANTES",
        "CANTIDAD_ZONAS_INVALIDA",
        "ZONAS_DUPLICADAS",
        "VALIDACION",
        "BACKFILL_FALLIDO",
    }


@pytest.mark.parametrize("name", PERSONALITY_ORDER)
def test_onboarding_body_is_the_saved_household_without_personality(
    name: str, client: TestClient, onboarding_db: FakeDatabase
) -> None:
    """RN-X-04: el 201 no expone la personalidad. Permisos por defecto de RN-II-03."""
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    response = send(
        client, Case("x", "crearHogarOnboarding", 201, body=onboarding_body(housing, zones))
    )
    (household,) = onboarding_db.saved["hogares"]
    assert response.json() == {
        "id": str(household["id"]),
        "nombre": HOUSEHOLD_NAME,
        "tipo_vivienda": housing,
        "rol_usuario": "administrador",
        "permisos": {
            "ver_consumo_actual": True,
            "ver_historial": True,
            "recibir_alertas": True,
            "modificar_metas": False,
        },
    }
    assert onboarding_db.used_profiles == [name]
    hidden = (*PERSONALITIES, str(household["perfil_simulacion_id"]), "perfil", "personalidad")
    assert not [value for value in hidden if value in response.text]
    (member,) = onboarding_db.saved["hogar_miembros"]
    assert member["usuario_id"] == USER_ID  # el del token


@pytest.mark.parametrize(
    ("zones", "location"),
    [
        (["cocina", "sala"], ["body", "zonas"]),
        ([*ZONE_TYPES, "cocina"], ["body", "zonas"]),
        ([*BASIC_ZONES, "piscina"], ["body", "zonas", "4"]),
    ],
    ids=["dos", "diez", "desconocida"],
)
def test_onboarding_validation_error_locates_the_field_without_echoing_it(
    zones: list[str], location: list[str], client: TestClient, onboarding_db: FakeDatabase
) -> None:
    response = send(
        client, Case("x", "crearHogarOnboarding", 422, body=onboarding_body(zones=zones))
    )
    assert [campo["ubicacion"] for campo in response.json()["detalles"]["campos"]] == [location]
    assert HOUSEHOLD_NAME not in response.text
    assert "piscina" not in response.text


# --- consultas de consumo (fase 6) ---------------------------------------------------------
#
# El servicio y el dominio son los reales; los datos (`app.data.*`) son los dobles en memoria de
# `tests/services/consumption_fakes.py`, con lecturas construidas con los promedios de cada
# personalidad (`tests/helpers/personalities.py`). La recuperación de horas es un espía. El reloj
# del servicio se fija (el router no pasa `now`) para que la hora evaluada no dependa de cuándo
# corre la prueba.

FIXED_NOW = datetime(2026, 11, 23, 15, 20, tzinfo=TIMEZONE)  # lunes; hora evaluada 14:00-15:00
HOUR_START, HOUR_END = states.evaluated_hour(FIXED_NOW)
PRICE_KWH = 850.0  # COP por kWh de la tarifa de prueba (el valor no cambia el esquema)
DEFAULT_PERSONALITY = "Consumo intermedio"
OTHER_HOUSEHOLD_ID = UUID("22222222-3333-4444-8555-666666666666")
REAL_FILL_MISSING_HOURS = hour_recovery.fill_missing_hours
CONSUMPTION_DATA_FUNCTIONS = (
    (households_data, "list_household_zones"),
    (readings_data, "get_hourly_readings"),
    (users_data, "get_preferences"),
    (goals_data, "get_active_goal"),
    (tariffs_data, "get_current_tariff"),
    (tariffs_data, "list_tariffs_between"),
    (hour_recovery, "fill_missing_hours"),
)


class FixedClock(datetime):
    """`datetime` del módulo del servicio con `now()` fijo en `FIXED_NOW`."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
        return FIXED_NOW if tz is None else FIXED_NOW.astimezone(tz)


@dataclass
class ConsumptionWorld:
    """Hogar de la prueba: datos en memoria, membresías y sesiones que vio cada capa."""

    db: FakeConsumptionDatabase
    session: ConsumptionFakeSession
    memberships: list[ActiveMembershipRow]
    personality: str = DEFAULT_PERSONALITY
    zone_ids: dict[str, UUID] = field(default_factory=dict)  # tipo -> id
    foreign_zone_id: UUID | None = None
    days: int = 31  # días de lecturas antes de la hora evaluada
    guard_sessions: list[object] = field(default_factory=list)
    data_sessions: list[object] = field(default_factory=list)

    def build_household(self, personality: str) -> None:
        """Zonas del hogar de referencia de la personalidad y `days` días de lecturas promedio."""
        averages = load_personalities()[personality]
        self.personality = personality
        for zona_id in self.zone_ids.values():
            self.db.readings.pop(zona_id, None)
        self.db.zones.pop(HOGAR_ID, None)
        self.zone_ids.clear()
        first = HOUR_START - timedelta(days=self.days)
        for tipo in REFERENCE_HOUSEHOLDS[personality][1]:
            zona_id = self.db.add_zone(HOGAR_ID, tipo, zone_name(tipo))
            self.zone_ids[tipo] = zona_id

            def kwh(moment: datetime, tipo: str = tipo) -> float:
                local = moment.astimezone(TIMEZONE)
                weekend = averages.weekend_factor if local.weekday() >= 5 else 1.0
                return averages.zone_kwh_for_hour(tipo, local.hour) * weekend

            self.db.set_series(zona_id, hourly_series(kwh, first, HOUR_START))

    @property
    def first_zone_id(self) -> UUID:
        return next(iter(self.zone_ids.values()))


def install_consumption_world(
    monkeypatch: pytest.MonkeyPatch, store: FakeStore
) -> ConsumptionWorld:
    db = install_fake_consumption_database(monkeypatch)
    world = ConsumptionWorld(
        db=db,
        session=ConsumptionFakeSession(),
        memberships=[make_membership_row(USER_ID, HOGAR_ID, rol="miembro")],
    )
    store.session = world.session  # type: ignore[assignment]  # la que entrega `get_session`

    def fake_get_active_membership(
        session: object, usuario_id: UUID, hogar_id: UUID
    ) -> ActiveMembershipRow | None:
        world.guard_sessions.append(session)
        return next(
            (m for m in world.memberships if m.usuario_id == usuario_id and m.hogar_id == hogar_id),
            None,
        )

    monkeypatch.setattr(memberships_data, "get_active_membership", fake_get_active_membership)
    for module, name in CONSUMPTION_DATA_FUNCTIONS:
        original = getattr(module, name)

        def spy(session: object, *args: Any, _original: Any = original, **kw: Any) -> Any:
            world.data_sessions.append(session)
            return _original(session, *args, **kw)

        monkeypatch.setattr(module, name, spy)
    monkeypatch.setattr(consumption_service, "datetime", FixedClock)
    world.build_household(DEFAULT_PERSONALITY)
    db.add_tariff(HOGAR_ID, PRICE_KWH, date(2026, 1, 1))
    world.foreign_zone_id = db.add_zone(OTHER_HOUSEHOLD_ID, "cocina", zone_name("cocina"))
    return world


@pytest.fixture
def consumption(monkeypatch: pytest.MonkeyPatch, store: FakeStore) -> ConsumptionWorld:
    return install_consumption_world(monkeypatch, store)


# Preparaciones de los casos (reciben el `ConsumptionWorld`).
def with_personality(name: str) -> Callable[[ConsumptionWorld], None]:
    return lambda world: world.build_household(name)


def without_tariff(world: ConsumptionWorld) -> None:
    world.db.tariffs.clear()  # RN-XI-08: tarifa_vigente = false y COP null


def without_evaluated_hour(world: ConsumptionWorld) -> None:
    """A una zona le falta la lectura de la hora evaluada: kW null y `sin_datos`."""
    world.db.readings[world.first_zone_id].pop(HOUR_START)


def with_goal(world: ConsumptionWorld) -> None:
    """`base_comparacion = meta` y una meta activa igual al consumo mensual de referencia."""
    averages = load_personalities()[world.personality]
    zones = tuple(world.zone_ids)
    monthly = sum(averages.household_kwh_for_hour(hour, zones) for hour in range(24)) * 30
    world.db.set_preferences(USER_ID, "meta")
    world.db.set_goal(HOGAR_ID, monthly)


def with_goal_preference_without_goal(world: ConsumptionWorld) -> None:
    world.db.set_preferences(USER_ID, "meta")  # sin meta activa: se usa el promedio (RN-XI-03)


def with_elevated_hour(world: ConsumptionWorld) -> None:
    series = world.db.readings[world.first_zone_id]
    series[HOUR_START] *= 1.6


def with_paused_first_zone(world: ConsumptionWorld) -> None:
    """La primera zona tiene el sensor pausado: no cuenta y su detalle sale sin datos."""
    zones = world.db.zones[HOGAR_ID]
    index = next(i for i, z in enumerate(zones) if z.id == world.first_zone_id)
    zones[index] = replace(zones[index], sensor_estado="pausado")


def without_recent_history(world: ConsumptionWorld) -> None:
    """Solo 3 días de lecturas: menos de los 7 días mínimos, sin referencia (DC-28)."""
    cutoff = HOUR_START - timedelta(days=3)
    for series in world.db.readings.values():
        for moment in [m for m in series if m < cutoff]:
            del series[moment]


def without_permission(world: ConsumptionWorld) -> None:
    world.memberships[:] = [
        make_membership_row(USER_ID, HOGAR_ID, rol="miembro", ver_consumo_actual=False)
    ]


def as_admin_without_permissions(world: ConsumptionWorld) -> None:
    world.memberships[:] = [
        make_membership_row(
            USER_ID,
            HOGAR_ID,
            rol="administrador",
            ver_consumo_actual=False,
            ver_historial=False,
            recibir_alertas=False,
        )
    ]


def without_membership(world: ConsumptionWorld) -> None:
    world.memberships.clear()


@dataclass(frozen=True)
class ConsumptionCase:
    name: str
    operation_id: str
    status: int
    setup: Callable[[ConsumptionWorld], None] | None = None
    authenticated: bool = True
    codigo: str | None = None
    hogar_id: str | None = None  # por defecto, el hogar de la prueba
    zona_id: str | None = None  # por defecto, la primera zona del hogar (`foreign` = otro hogar)
    # Parámetros de consulta; en `zona_id`, `first` = primera zona y `foreign` = zona de otro hogar.
    query: tuple[tuple[str, str], ...] = ()


def _consumption_cases_for(operation_id: str) -> tuple[ConsumptionCase, ...]:
    def case(name: str, status: int, **kw: Any) -> ConsumptionCase:
        return ConsumptionCase(name, operation_id, status, **kw)

    return (
        *(
            case(f"promedio-{name.split()[1]}", 200, setup=with_personality(name))
            for name in PERSONALITY_ORDER
        ),
        case("sin-tarifa", 200, setup=without_tariff),
        case("hora-sin-lectura", 200, setup=without_evaluated_hour),
        case("con-meta", 200, setup=with_goal),
        case("meta-elegida-sin-meta-activa", 200, setup=with_goal_preference_without_goal),
        case("hora-elevada", 200, setup=with_elevated_hour),
        case("sensor-pausado", 200, setup=with_paused_first_zone),
        case("sin-referencia", 200, setup=without_recent_history),
        case("admin-sin-permisos", 200, setup=as_admin_without_permissions),
        case("sin-token", 401, authenticated=False, codigo="NO_AUTENTICADO"),
        case("sin-permiso", 403, setup=without_permission, codigo="SIN_PERMISO_VER_CONSUMO"),
        case("sin-membresia", 404, setup=without_membership, codigo="NO_ENCONTRADO"),
        case("hogar-ajeno", 404, hogar_id=str(OTHER_HOUSEHOLD_ID), codigo="NO_ENCONTRADO"),
        case("hogar-no-uuid", 422, hogar_id="no-es-un-uuid", codigo="VALIDACION"),
    )


CONSUMPTION_CASES: tuple[ConsumptionCase, ...] = (
    *_consumption_cases_for("obtenerConsumoActual"),
    *_consumption_cases_for("obtenerConsumoZonas"),
    *_consumption_cases_for("obtenerConsumoZona"),
    ConsumptionCase(
        "zona-de-otro-hogar", "obtenerConsumoZona", 404, zona_id="foreign", codigo="NO_ENCONTRADO"
    ),
    ConsumptionCase(
        "zona-inexistente",
        "obtenerConsumoZona",
        404,
        zona_id="00000000-0000-4000-8000-000000000000",
        codigo="NO_ENCONTRADO",
    ),
    ConsumptionCase(
        "zona-no-uuid", "obtenerConsumoZona", 422, zona_id="no-es-un-uuid", codigo="VALIDACION"
    ),
)
# Casos que la guardia corta antes de llegar al servicio.
GUARD_STOPS = frozenset({"sin-token", "sin-permiso", "sin-membresia", "hogar-ajeno"})


def _zone_placeholder(value: str, world: ConsumptionWorld) -> str:
    return {"first": str(world.first_zone_id), "foreign": str(world.foreign_zone_id)}.get(
        value, value
    )


def consumption_url(case: ConsumptionCase, world: ConsumptionWorld) -> str:
    _method, path, _op = OPERATIONS[case.operation_id]
    zona_id = _zone_placeholder(case.zona_id or "first", world)
    url = API_PREFIX + path.format(hogar_id=case.hogar_id or str(HOGAR_ID), zona_id=zona_id)
    if case.query:
        pairs = [
            (name, _zone_placeholder(value, world) if name == "zona_id" else value)
            for name, value in case.query
        ]
        url += "?" + urlencode(pairs)
    return url


def send_consumption(client: TestClient, case: ConsumptionCase, world: ConsumptionWorld) -> Any:
    headers = auth_header(make_token(USER_ID, CORREO)) if case.authenticated else {}
    return client.get(consumption_url(case, world), headers=headers)


def get_consumption(client: TestClient, world: ConsumptionWorld, operation_id: str) -> Any:
    response = send_consumption(client, ConsumptionCase("x", operation_id, 200), world)
    assert response.status_code == 200, response.text
    assert_matches_contract(operation_id, response)
    return response.json()


@pytest.mark.parametrize(
    "case", CONSUMPTION_CASES, ids=lambda c: f"{c.operation_id}-{c.status}-{c.name}"
)
def test_consumption_response_matches_contract_schema(
    case: ConsumptionCase, client: TestClient, consumption: ConsumptionWorld
) -> None:
    if case.setup is not None:
        case.setup(consumption)
    response = send_consumption(client, case, consumption)
    assert response.status_code == case.status, response.text
    assert_matches_contract(case.operation_id, response)
    # La guardia y cada función de datos recibieron la sesión de la petición.
    assert all(s is consumption.session for s in consumption.guard_sessions)
    assert all(s is consumption.session for s in consumption.data_sessions)
    assert consumption.session.commits == 0  # solo lectura (la recuperación espía no guarda)
    if case.status == 200:
        assert consumption.guard_sessions == [consumption.session]
        assert consumption.db.names()[0] == "recovery"  # recuperación primero (RN-IV-05)
        assert consumption.db.calls[0][2] == FIXED_NOW  # el reloj fijo llegó al servicio
        return
    assert response.json()["codigo"] == case.codigo
    assert (response.headers.get("WWW-Authenticate") == "Bearer") == (case.status == 401)
    if case.status == 422 or case.name in GUARD_STOPS:
        assert consumption.db.calls == []  # no llegó al servicio


def test_consumption_cases_cover_every_code_of_the_operations() -> None:
    for operation_id in CONSUMPTION_OPERATIONS:
        codes = {c.codigo for c in CONSUMPTION_CASES if c.operation_id == operation_id}
        assert codes - {None} == {
            "NO_AUTENTICADO",
            "SIN_PERMISO_VER_CONSUMO",
            "NO_ENCONTRADO",
            "VALIDACION",
        }


SERVICE_FUNCTIONS = {
    "obtenerConsumoActual": "get_current_consumption",
    "obtenerConsumoZonas": "get_zones_consumption",
    "obtenerConsumoZona": "get_zone_consumption",
}


@pytest.mark.parametrize("operation_id", sorted(CONSUMPTION_OPERATIONS))
def test_router_passes_guard_session_and_token_user_to_service(
    operation_id: str,
    client: TestClient,
    consumption: ConsumptionWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La MISMA sesión llega a la guardia y al servicio, con el usuario del token, el hogar de la
    ruta (y la zona) y sin `now` (lo decide el servicio)."""
    received: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    name = SERVICE_FUNCTIONS[operation_id]
    real = getattr(consumption_service, name)

    def spy(*args: Any, **kwargs: Any) -> Any:
        received.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(consumption_service, name, spy)
    get_consumption(client, consumption, operation_id)
    ((args, kwargs),) = received
    assert kwargs == {}
    expected: tuple[Any, ...] = (consumption.session, USER_ID, HOGAR_ID)
    if operation_id == "obtenerConsumoZona":
        expected += (consumption.first_zone_id,)
    assert args == expected
    assert args[0] is consumption.session
    assert consumption.guard_sessions == [consumption.session]
    assert consumption.guard_sessions[0] is args[0]


def test_current_consumption_with_tariff_has_costs(
    client: TestClient, consumption: ConsumptionWorld
) -> None:
    body = get_consumption(client, consumption, "obtenerConsumoActual")
    assert body["tarifa_vigente"] is True
    assert datetime.fromisoformat(body["hora"]["inicio"]) == HOUR_START
    assert datetime.fromisoformat(body["hora"]["fin"]) == HOUR_END
    actual, today = body["actual"], body["acumulado_hoy"]
    expected_kw = sum(consumption.db.readings[z][HOUR_START] for z in consumption.zone_ids.values())
    assert actual["potencia_kw"] == pytest.approx(expected_kw)
    assert actual["costo_cop"] == pytest.approx(actual["potencia_kw"] * PRICE_KWH)
    assert actual["referencia_tipo"] == "promedio"
    assert today["costo_cop"] == pytest.approx(today["energia_kwh"] * PRICE_KWH)
    assert today["muestra_limite"] is False


@pytest.mark.parametrize("operation_id", sorted(CONSUMPTION_OPERATIONS))
def test_consumption_without_tariff_has_null_costs(
    operation_id: str, client: TestClient, consumption: ConsumptionWorld
) -> None:
    """RN-XI-08: sin tarifa vigente, `tarifa_vigente = false` y todos los COP null."""
    without_tariff(consumption)
    body = get_consumption(client, consumption, operation_id)
    assert body["tarifa_vigente"] is False
    if operation_id == "obtenerConsumoActual":
        assert body["actual"]["potencia_kw"] is not None
        assert body["actual"]["costo_cop"] is None
        assert body["acumulado_hoy"]["costo_cop"] is None
    elif operation_id == "obtenerConsumoZonas":
        assert body["zonas"]
        assert all(z["potencia_kw"] is not None and z["costo_cop"] is None for z in body["zonas"])
    else:
        assert body["potencia_kw"] is not None
        assert body["costo_cop"] is None


def assert_missing_hour_is_sin_datos(
    operation_id: str, body: dict[str, Any], world: ConsumptionWorld
) -> None:
    """La zona sin la lectura de la hora evaluada: kW null (nunca 0) y `sin_datos`."""
    if operation_id == "obtenerConsumoActual":
        assert body["actual"]["potencia_kw"] is None
        assert body["actual"]["costo_cop"] is None
        assert body["actual"]["estado"] == "sin_datos"
        assert body["actual"]["mensaje_codigo"] == "consumo_actual.sin_datos"
    elif operation_id == "obtenerConsumoZonas":
        assert body["total_kw"] is None
        (missing,) = [z for z in body["zonas"] if z["zona_id"] == str(world.first_zone_id)]
        assert missing["potencia_kw"] is None
        assert missing["costo_cop"] is None
        assert missing["participacion_pct"] is None
    else:
        assert body["potencia_kw"] is None
        assert body["costo_cop"] is None
        assert body["estado_consumo"]["estado"] == "sin_datos"
        assert body["estado_consumo"]["mensaje_codigo"] == "zona_estado.sin_datos"
        assert body["participacion"]["total_hogar_kw"] is None


@pytest.mark.parametrize("operation_id", sorted(CONSUMPTION_OPERATIONS))
def test_consumption_hour_without_reading_is_null_and_sin_datos(
    operation_id: str, client: TestClient, consumption: ConsumptionWorld
) -> None:
    without_evaluated_hour(consumption)
    body = get_consumption(client, consumption, operation_id)
    assert_missing_hour_is_sin_datos(operation_id, body, consumption)


def test_zone_detail_of_a_zone_that_does_not_count_is_200_without_data(
    client: TestClient, consumption: ConsumptionWorld
) -> None:
    with_paused_first_zone(consumption)
    body = get_consumption(client, consumption, "obtenerConsumoZona")
    assert body["zona"]["id"] == str(consumption.first_zone_id)
    assert body["potencia_kw"] is None
    assert body["estado_consumo"]["estado"] == "sin_datos"


def test_zones_consumption_lists_the_counting_zones(
    client: TestClient, consumption: ConsumptionWorld
) -> None:
    body = get_consumption(client, consumption, "obtenerConsumoZonas")
    assert {z["zona_id"] for z in body["zonas"]} == {str(z) for z in consumption.zone_ids.values()}
    assert body["total_kw"] == pytest.approx(sum(z["potencia_kw"] for z in body["zonas"]))


# --- recuperación de horas fallida (decisión de Nicolás, 23/11/2026) -----------------------


def recovery_raises(world: ConsumptionWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(session: object, hogar_id: UUID, now: datetime | None = None) -> int:
        world.data_sessions.append(session)
        raise hour_recovery.HourRecoveryError()

    monkeypatch.setattr(hour_recovery, "fill_missing_hours", failing)


def recovery_lock_fails(world: ConsumptionWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    """La recuperación real falla al tomar el candado del hogar (p. ej. conexión perdida)."""

    def failing_lock(session: object, hogar_id: UUID) -> None:
        world.data_sessions.append(session)
        raise RuntimeError(INTERNAL_DETAIL)

    monkeypatch.setattr(hour_recovery, "fill_missing_hours", REAL_FILL_MISSING_HOURS)
    monkeypatch.setattr(readings_data, "lock_household_recovery", failing_lock)


@pytest.mark.parametrize(
    "failure", [recovery_raises, recovery_lock_fails], ids=["error", "candado"]
)
@pytest.mark.parametrize("operation_id", sorted(CONSUMPTION_OPERATIONS))
def test_failed_hour_recovery_answers_200_with_stored_data(
    operation_id: str,
    failure: Callable[[ConsumptionWorld, pytest.MonkeyPatch], None],
    client: TestClient,
    consumption: ConsumptionWorld,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Si la recuperación falla, 200 (no 500) con los datos guardados; la hora que la
    recuperación no pudo completar sale `sin_datos`. Sin detalles internos en la respuesta."""
    without_evaluated_hour(consumption)  # la hora que la recuperación habría generado
    failure(consumption, monkeypatch)
    with caplog.at_level("WARNING", logger=hour_recovery.__name__):
        body = get_consumption(client, consumption, operation_id)
    assert_missing_hour_is_sin_datos(operation_id, body, consumption)
    assert INTERNAL_DETAIL not in str(body)
    assert consumption.data_sessions, "la recuperación no se llamó"
    assert all(s is consumption.session for s in consumption.data_sessions)
    assert consumption.session.commits == 0
    if failure is recovery_lock_fails:
        assert consumption.session.rollbacks == 1  # la recuperación revirtió lo suyo
    assert hour_recovery.RECOVERY_SKIPPED_MESSAGE in caplog.messages
    assert not [r for r in caplog.records if INTERNAL_DETAIL in r.getMessage()]


# --- historial (fase 7) -------------------------------------------------------------------
# `obtenerHistorial` con el servicio real sobre el mismo mundo en memoria, con 56 días de lecturas
# para cubrir el tramo anterior de Mes (desde el día 1 del mes anterior, DC-29) y las ventanas de
# referencia. FIXED_NOW es lunes 23/11/2026 15:20: Día = 15 horas, Semana = 1 día, Mes = 23 días.

PERIODS = ("dia", "semana", "mes")
HISTORY_DAYS = 56
FIXED_CHARGE = 12_000.0  # COP de cargo fijo mensual de la tarifa de prueba
HISTORY_ERROR_CODES = frozenset(
    {"NO_AUTENTICADO", "SIN_PERMISO_VER_HISTORIAL", "NO_ENCONTRADO", "VALIDACION"}
)
_LOCAL_NOW = FIXED_NOW.astimezone(TIMEZONE)
EXPECTED_POINTS = {
    "dia": _LOCAL_NOW.hour,
    "semana": _LOCAL_NOW.weekday() + 1,
    "mes": _LOCAL_NOW.day,
}


@pytest.fixture
def history_world(consumption: ConsumptionWorld) -> ConsumptionWorld:
    consumption.days = HISTORY_DAYS
    consumption.build_household(DEFAULT_PERSONALITY)
    return consumption


def without_history_permission(world: ConsumptionWorld) -> None:
    world.memberships[:] = [
        make_membership_row(USER_ID, HOGAR_ID, rol="miembro", ver_historial=False)
    ]


def with_fixed_charge(world: ConsumptionWorld) -> None:
    world.db.tariffs.clear()
    world.db.add_tariff(HOGAR_ID, PRICE_KWH, date(2026, 1, 1), cargo_fijo=FIXED_CHARGE)


def history_query(periodo: str, zona: str | None = None) -> tuple[tuple[str, str], ...]:
    return (("periodo", periodo),) if zona is None else (("periodo", periodo), ("zona_id", zona))


def _history_cases() -> tuple[ConsumptionCase, ...]:
    def case(name: str, status: int, **kw: Any) -> ConsumptionCase:
        kw.setdefault("query", history_query("dia"))
        return ConsumptionCase(name, HISTORY_OPERATION, status, **kw)

    cases: list[ConsumptionCase] = []
    for periodo in PERIODS:
        for name in PERSONALITY_ORDER:
            short = name.split()[1]
            setup = with_personality(name)
            cases.append(case(f"{periodo}-general-{short}", 200, setup=setup,
                              query=history_query(periodo)))
            cases.append(case(f"{periodo}-zona-{short}", 200, setup=setup,
                              query=history_query(periodo, "first")))
        for scope, zona in (("general", None), ("zona", "first")):
            query = history_query(periodo, zona)
            cases.append(case(f"{periodo}-{scope}-sin-tarifa", 200, setup=without_tariff,
                              query=query))
            cases.append(case(f"{periodo}-{scope}-cargo-fijo", 200, setup=with_fixed_charge,
                              query=query))
    cases += [
        case("sin-referencia", 200, setup=without_recent_history, query=history_query("mes")),
        case("sensor-pausado-general", 200, setup=with_paused_first_zone),
        case("sensor-pausado-zona", 200, setup=with_paused_first_zone,
             query=history_query("dia", "first")),
        case("admin-sin-permisos", 200, setup=as_admin_without_permissions),
        case("sin-token", 401, authenticated=False, codigo="NO_AUTENTICADO"),
        case("sin-permiso", 403, setup=without_history_permission,
             codigo="SIN_PERMISO_VER_HISTORIAL"),
        case("sin-membresia", 404, setup=without_membership, codigo="NO_ENCONTRADO"),
        case("hogar-ajeno", 404, hogar_id=str(OTHER_HOUSEHOLD_ID), codigo="NO_ENCONTRADO"),
        case("zona-de-otro-hogar", 404, query=history_query("dia", "foreign"),
             codigo="NO_ENCONTRADO"),
        case("zona-inexistente", 404,
             query=history_query("dia", "00000000-0000-4000-8000-000000000000"),
             codigo="NO_ENCONTRADO"),
        case("periodo-invalido", 422, query=history_query("anio"), codigo="VALIDACION"),
        case("periodo-ausente", 422, query=(), codigo="VALIDACION"),
        case("zona-no-uuid", 422, query=history_query("dia", "no-es-un-uuid"),
             codigo="VALIDACION"),
        case("hogar-no-uuid", 422, hogar_id="no-es-un-uuid", codigo="VALIDACION"),
    ]
    return tuple(cases)


HISTORY_CASES: tuple[ConsumptionCase, ...] = _history_cases()
# Casos que la guardia corta antes del servicio o que no pasan la validación de la entrada.
HISTORY_NOT_REACHING_SERVICE = GUARD_STOPS | {
    "periodo-invalido",
    "periodo-ausente",
    "zona-no-uuid",
    "hogar-no-uuid",
}


def alphabetical_zone_ids(world: ConsumptionWorld) -> list[str]:
    """Zonas que cuentan, por nombre visible (RN-XII-03) y, a igual nombre, por id."""
    zones = [
        z for z in world.db.zones[HOGAR_ID] if z.estado == "activa" and z.sensor_estado == "activo"
    ]
    return [str(z.id) for z in sorted(zones, key=lambda z: (zone_name(z.tipo), str(z.id)))]


def assert_history_shape(
    body: dict[str, Any], world: ConsumptionWorld, periodo: str, zona_id: str | None
) -> None:
    """Forma del historial: periodo, granularidad, número de puntos y (v0.2.9) `zonas` por punto
    solo con General, con los mismos zona_id y en el mismo orden que `participacion_zonas`."""
    assert body["periodo"] == periodo
    assert body["granularidad"] == ("hora" if periodo == "dia" else "dia")
    assert body["zona_id"] == zona_id
    assert datetime.fromisoformat(body["fin"]) == HOUR_END
    assert len(body["serie"]) == EXPECTED_POINTS[periodo]
    if zona_id is not None:
        assert body["participacion_zonas"] is None
        assert all(point["zonas"] is None for point in body["serie"])
        return
    order = [share["zona_id"] for share in body["participacion_zonas"]]
    assert order == alphabetical_zone_ids(world)
    for point in body["serie"]:
        assert [z["zona_id"] for z in point["zonas"]] == order
        energies = [z["energia_kwh"] for z in point["zonas"]]
        if None in energies:
            assert point["energia_kwh"] is None  # una zona sin lectura deja el punto sin dato
        else:
            assert point["energia_kwh"] == pytest.approx(sum(energies))


def get_history(
    client: TestClient, world: ConsumptionWorld, periodo: str, zona: str | None = None
) -> dict[str, Any]:
    case = ConsumptionCase("x", HISTORY_OPERATION, 200, query=history_query(periodo, zona))
    response = send_consumption(client, case, world)
    assert response.status_code == 200, response.text
    assert_matches_contract(HISTORY_OPERATION, response)
    return response.json()


def _requested(case: ConsumptionCase, world: ConsumptionWorld) -> tuple[str, str | None]:
    query = dict(case.query)
    zona = query.get("zona_id")
    return query["periodo"], None if zona is None else _zone_placeholder(zona, world)


@pytest.mark.parametrize("case", HISTORY_CASES, ids=lambda c: f"{c.status}-{c.name}")
def test_history_response_matches_contract_schema(
    case: ConsumptionCase, client: TestClient, history_world: ConsumptionWorld
) -> None:
    world = history_world
    if case.setup is not None:
        case.setup(world)
    response = send_consumption(client, case, world)
    assert response.status_code == case.status, response.text
    assert_matches_contract(HISTORY_OPERATION, response)
    assert all(s is world.session for s in world.guard_sessions)
    assert all(s is world.session for s in world.data_sessions)
    assert world.session.commits == 0  # solo lectura
    if case.status == 200:
        periodo, zona_id = _requested(case, world)
        assert_history_shape(response.json(), world, periodo, zona_id)
        assert world.guard_sessions == [world.session]
        assert world.db.names()[0] == "recovery"  # recuperación primero (RN-IV-05, DC-34)
        assert world.db.calls[0][2] == FIXED_NOW
        return
    assert response.json()["codigo"] == case.codigo
    assert (response.headers.get("WWW-Authenticate") == "Bearer") == (case.status == 401)
    if case.name in HISTORY_NOT_REACHING_SERVICE:
        assert world.db.calls == []  # no llegó al servicio
    if case.name in {"zona-de-otro-hogar", "zona-inexistente"}:
        assert "readings" not in world.db.names()  # 404 antes de leer lecturas


def test_history_cases_cover_every_code_of_the_operation() -> None:
    codes = {c.codigo for c in HISTORY_CASES} - {None}
    assert codes == HISTORY_ERROR_CODES


@pytest.mark.parametrize("zona", [None, "first"], ids=["general", "zona"])
@pytest.mark.parametrize("periodo", PERIODS)
def test_history_router_passes_guard_session_and_query_to_service(
    periodo: str,
    zona: str | None,
    client: TestClient,
    history_world: ConsumptionWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La MISMA sesión llega a la guardia y al servicio, con el usuario del token, el hogar de la
    ruta, el periodo y la zona de la consulta, y sin `now` (lo decide el servicio)."""
    received: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    real = consumption_service.get_history

    def spy(*args: Any, **kwargs: Any) -> Any:
        received.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(consumption_service, "get_history", spy)
    get_history(client, history_world, periodo, zona)
    ((args, kwargs),) = received
    assert kwargs == {}
    zona_id = None if zona is None else history_world.first_zone_id
    assert args == (history_world.session, USER_ID, HOGAR_ID, periodo, zona_id)
    assert args[0] is history_world.session
    assert history_world.guard_sessions == [history_world.session]


@pytest.mark.parametrize("zona", [None, "first"], ids=["general", "zona"])
@pytest.mark.parametrize("periodo", PERIODS)
def test_history_without_tariff_has_null_costs(
    periodo: str, zona: str | None, client: TestClient, history_world: ConsumptionWorld
) -> None:
    """RN-XI-08, RN-XIII-05: sin tarifa, `tarifa_vigente = false` y todos los COP null."""
    without_tariff(history_world)
    body = get_history(client, history_world, periodo, zona)
    assert body["tarifa_vigente"] is False
    assert body["total_kwh"] > 0
    assert all(p["energia_kwh"] is not None and p["costo_cop"] is None for p in body["serie"])
    assert body["costo"]["costo_cop"] is None
    assert body["costo"]["proyeccion_cierre_cop"] is None
    assert body["costo"]["incluye_cargo_fijo"] is False


@pytest.mark.parametrize("zona", [None, "first"], ids=["general", "zona"])
@pytest.mark.parametrize("periodo", PERIODS)
def test_history_with_tariff_and_fixed_charge(
    periodo: str, zona: str | None, client: TestClient, history_world: ConsumptionWorld
) -> None:
    """RN-XIII-05, RN-V-01, RN-V-02, DC-30: cada punto al precio de su fecha; el cargo fijo solo
    entra en la proyección de Mes con el filtro General."""
    with_fixed_charge(history_world)
    body = get_history(client, history_world, periodo, zona)
    general = zona is None
    assert body["tarifa_vigente"] is True
    assert body["comparacion"]["anterior_kwh"] is not None  # los datos cubren el tramo anterior
    for point in body["serie"]:
        assert point["costo_cop"] == pytest.approx(point["energia_kwh"] * PRICE_KWH)
    cost = body["costo"]
    assert cost["costo_cop"] == pytest.approx(body["total_kwh"] * PRICE_KWH)
    assert cost["incluye_cargo_fijo"] is (periodo == "mes" and general)
    assert cost["proyeccion_cierre_cop"] is not None
    floor = cost["costo_cop"] + (FIXED_CHARGE if cost["incluye_cargo_fijo"] else 0.0)
    assert cost["proyeccion_cierre_cop"] >= floor


@pytest.mark.parametrize("periodo", PERIODS)
def test_history_general_shares_add_up_to_100(
    periodo: str, client: TestClient, history_world: ConsumptionWorld
) -> None:
    """RN-XIII-04: la participación del filtro General suma 100, su energía suma el total y el
    nombre de cada zona es el visible de su tipo (RN-XII-03)."""
    body = get_history(client, history_world, periodo)
    shares = body["participacion_zonas"]
    assert sum(s["participacion_pct"] for s in shares) == pytest.approx(100.0)
    assert sum(s["energia_kwh"] for s in shares) == pytest.approx(body["total_kwh"])
    tipos = {str(zona_id): tipo for tipo, zona_id in history_world.zone_ids.items()}
    assert all(s["nombre"] == zone_name(tipos[s["zona_id"]]) for s in shares)


@pytest.mark.parametrize(
    "failure", [recovery_raises, recovery_lock_fails], ids=["error", "candado"]
)
@pytest.mark.parametrize("zona", [None, "first"], ids=["general", "zona"])
def test_history_failed_hour_recovery_answers_200_with_stored_data(
    zona: str | None,
    failure: Callable[[ConsumptionWorld, pytest.MonkeyPatch], None],
    client: TestClient,
    history_world: ConsumptionWorld,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """RN-IV-05, DC-34: si la recuperación falla, 200 (no 500) con lo guardado; la hora que no se
    pudo completar sale sin dato (null, nunca 0). Sin detalles internos en la respuesta."""
    world = history_world
    without_evaluated_hour(world)  # la hora que la recuperación habría generado
    failure(world, monkeypatch)
    with caplog.at_level("WARNING", logger=hour_recovery.__name__):
        body = get_history(client, world, "dia", zona)
    last = body["serie"][-1]
    assert datetime.fromisoformat(last["inicio"]) == HOUR_START
    assert last["energia_kwh"] is None
    assert last["costo_cop"] is None
    assert body["costo"]["costo_cop"] is None  # periodo incompleto: sin costo parcial
    if zona is None:
        (missing,) = [z for z in last["zonas"] if z["zona_id"] == str(world.first_zone_id)]
        assert missing["energia_kwh"] is None
    assert INTERNAL_DETAIL not in str(body)
    assert world.data_sessions, "la recuperación no se llamó"
    assert all(s is world.session for s in world.data_sessions)
    assert world.session.commits == 0
    if failure is recovery_lock_fails:
        assert world.session.rollbacks == 1
    assert hour_recovery.RECOVERY_SKIPPED_MESSAGE in caplog.messages
    assert not [r for r in caplog.records if INTERNAL_DETAIL in r.getMessage()]


# --- alertas y consejos (fase 8) ----------------------------------------------------------
# Las 5 operaciones con el servicio reemplazado por un doble (monkeypatch de
# `app.services.alerts_tips`): aquí se prueba la capa HTTP (validación de la entrada, guardas de
# membresía y permiso, sesión de la petición y cuerpo contra el contrato). El servicio real, con
# la recuperación de horas antes de leer (decisión de Nicolás del 23/11/2026: si la recuperación
# falla, la consulta responde con lo guardado; RN-IV-05, DC-34), está probado en
# `tests/services/test_alerts_tips_service.py`, y la evaluación en vivo en
# `tests/services/test_live_alerts_service.py`. Los textos de ejemplo son las plantillas del
# catálogo del backend (`get_backend_texts`), no inventados.

ALERTS_SERVICE_FUNCTIONS = {
    "listarAlertas": "list_alerts",
    "contarAlertasNoLeidas": "count_unread_alerts",
    "marcarAlertasLeidas": "mark_alerts_read",
    "listarConsejos": "list_tips",
    "actualizarEstadoConsejo": "update_tip_status",
}
_GUARDED_CODES = frozenset({"NO_AUTENTICADO", "NO_ENCONTRADO", "VALIDACION"})
ALERTS_ERROR_CODES = {
    "listarAlertas": _GUARDED_CODES | {"SIN_PERMISO_RECIBIR_ALERTAS"},
    "contarAlertasNoLeidas": _GUARDED_CODES | {"SIN_PERMISO_RECIBIR_ALERTAS"},
    "marcarAlertasLeidas": _GUARDED_CODES | {"SIN_PERMISO_RECIBIR_ALERTAS"},
    "listarConsejos": _GUARDED_CODES,
    "actualizarEstadoConsejo": _GUARDED_CODES,
}
ALERTS_ZONE_ID = UUID("33333333-4444-4555-8666-777777777777")
ALERTS_ZONE_TYPE = "cocina"
ALERTS_CREATED_AT = datetime(2026, 11, 23, 14, 5, tzinfo=TIMEZONE)
ALERTS_READ_AT = datetime(2026, 11, 23, 15, 0, tzinfo=TIMEZONE)
FOREIGN_ID = "00000000-0000-4000-8000-000000000000"  # id que no es del usuario ni del hogar


def sample_id(kind: int, index: int) -> UUID:
    return UUID(f"{kind:08d}-0000-4000-8000-{index:012d}")


FIRST_TIP_ID = sample_id(2, 0)
COMPLETED_TIP_ID = sample_id(2, 2)


def sample_alerts() -> list[Alerta]:
    """Una alerta por plantilla del catálogo (las 7 reglas de DC-25), alternando zona y lectura:
    cubre cada categoría y severidad del catálogo, y `zona_id` y `leida_en` con dato y null."""
    templates = sorted(get_backend_texts().alerts.values(), key=lambda t: t.regla_origen)
    alerts = []
    for index, template in enumerate(templates):
        zonal = index % 2 == 0
        alerts.append(
            Alerta(
                id=sample_id(1, index),
                categoria=CategoriaAlerta(template.categoria),
                severidad=template.severidad,  # type: ignore[arg-type]
                titulo=template.titulo,
                mensaje=template.mensaje,
                zona_id=ALERTS_ZONE_ID if zonal else None,
                zona_nombre=zone_name(ALERTS_ZONE_TYPE) if zonal else None,
                creada_en=ALERTS_CREATED_AT - timedelta(hours=index),
                leida_en=None if index % 3 else ALERTS_READ_AT,
            )
        )
    return alerts


def sample_tips() -> list[Consejo]:
    """Un consejo del catálogo por prioridad (alta, media, baja); el último, completado."""
    by_priority = {
        t.prioridad: t for t in sorted(get_backend_texts().tips, key=lambda t: t.regla_origen)
    }
    tips = []
    for index, priority in enumerate(("alta", "media", "baja")):
        template = by_priority[priority]
        completed = index == 2
        tips.append(
            Consejo(
                id=sample_id(2, index),
                categoria="general" if template.zona is None else "zona",
                prioridad=template.prioridad,  # type: ignore[arg-type]
                titulo=template.titulo,
                descripcion=template.descripcion,
                zona_id=None if template.zona is None else ALERTS_ZONE_ID,
                zona_nombre=None if template.zona is None else zone_name(template.zona),
                estado="completada" if completed else "pendiente",
                completada_en=ALERTS_READ_AT if completed else None,
                creado_en=ALERTS_CREATED_AT - timedelta(days=index),
            )
        )
    return tips


@dataclass
class AlertsWorld:
    """Membresías de la prueba, filas que devuelve el doble del servicio y llamadas recibidas.

    Los dobles tienen la firma posicional del servicio real: un argumento de más o de menos es un
    TypeError (500) y la prueba falla.
    """

    session: RecordingSession
    memberships: list[ActiveMembershipRow]
    alerts: list[Alerta] = field(default_factory=sample_alerts)
    tips: list[Consejo] = field(default_factory=sample_tips)
    guard_sessions: list[object] = field(default_factory=list)
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)

    def list_alerts(
        self,
        session: object,
        user_id: UUID,
        hogar_id: UUID,
        categoria: CategoriaAlerta | None,
        limite: int,
        **kw: Any,
    ) -> AlertasLista:
        self.calls.append(("list_alerts", (session, user_id, hogar_id, categoria, limite), kw))
        found = [a for a in self.alerts if categoria is None or a.categoria == categoria]
        return AlertasLista(alertas=found[:limite])

    def count_unread_alerts(
        self, session: object, user_id: UUID, hogar_id: UUID, **kw: Any
    ) -> AlertasNoLeidas:
        self.calls.append(("count_unread_alerts", (session, user_id, hogar_id), kw))
        return AlertasNoLeidas(cantidad=sum(a.leida_en is None for a in self.alerts))

    def mark_alerts_read(
        self, session: object, user_id: UUID, hogar_id: UUID, payload: AlertasMarcar, **kw: Any
    ) -> AlertasMarcadas:
        self.calls.append(("mark_alerts_read", (session, user_id, hogar_id, payload), kw))
        wanted = set(payload.alerta_ids)  # los ajenos o ya leídos se ignoran
        return AlertasMarcadas(
            marcadas=sum(a.id in wanted and a.leida_en is None for a in self.alerts)
        )

    def list_tips(
        self, session: object, user_id: UUID, hogar_id: UUID, **kw: Any
    ) -> ConsejosLista:
        self.calls.append(("list_tips", (session, user_id, hogar_id), kw))
        return ConsejosLista(consejos=list(self.tips))

    def update_tip_status(
        self,
        session: object,
        user_id: UUID,
        hogar_id: UUID,
        consejo_id: UUID,
        payload: ConsejoEstadoActualizar,
        **kw: Any,
    ) -> Consejo:
        self.calls.append(
            ("update_tip_status", (session, user_id, hogar_id, consejo_id, payload), kw)
        )
        tip = next((t for t in self.tips if t.id == consejo_id), None)
        if tip is None:  # sin fila en consejos_usuario (RN-XV-06)
            raise ApiError(404, CodigoError.NO_ENCONTRADO, NOT_FOUND_MESSAGE)
        completed_at = ALERTS_READ_AT if payload.estado == "completada" else None
        return tip.model_copy(update={"estado": payload.estado, "completada_en": completed_at})


@pytest.fixture
def alerts_world(monkeypatch: pytest.MonkeyPatch, store: FakeStore) -> AlertsWorld:
    world = AlertsWorld(session=store.session, memberships=[make_membership_row(USER_ID, HOGAR_ID)])

    def fake_get_active_membership(
        session: object, usuario_id: UUID, hogar_id: UUID
    ) -> ActiveMembershipRow | None:
        world.guard_sessions.append(session)
        return next(
            (m for m in world.memberships if m.usuario_id == usuario_id and m.hogar_id == hogar_id),
            None,
        )

    monkeypatch.setattr(memberships_data, "get_active_membership", fake_get_active_membership)
    for name in ALERTS_SERVICE_FUNCTIONS.values():
        assert hasattr(alerts_tips_service, name), name
        monkeypatch.setattr(alerts_tips_service, name, getattr(world, name))
    return world


# Preparaciones de los casos (reciben el `AlertsWorld`).
def without_alerts(world: AlertsWorld) -> None:
    world.alerts.clear()


def without_tips(world: AlertsWorld) -> None:
    world.tips.clear()  # sin pendientes: card «Todo bajo control»


def without_alerts_permission(world: AlertsWorld) -> None:
    world.memberships[:] = [make_membership_row(USER_ID, HOGAR_ID, recibir_alertas=False)]


def admin_without_any_permission(world: AlertsWorld) -> None:
    """El administrador recibe alertas aunque sus permisos guardados sean false (RN-XII-02)."""
    world.memberships[:] = [
        make_membership_row(
            USER_ID,
            HOGAR_ID,
            rol="administrador",
            ver_consumo_actual=False,
            ver_historial=False,
            recibir_alertas=False,
        )
    ]


def member_without_any_permission(world: AlertsWorld) -> None:
    """Los consejos solo exigen membresía activa: sin ningún permiso, igual responden."""
    world.memberships[:] = [
        make_membership_row(
            USER_ID, HOGAR_ID, ver_consumo_actual=False, ver_historial=False, recibir_alertas=False
        )
    ]


def without_alerts_membership(world: AlertsWorld) -> None:
    world.memberships.clear()


@dataclass(frozen=True)
class AlertsCase:
    name: str
    operation_id: str
    status: int
    setup: Callable[[AlertsWorld], None] | None = None
    authenticated: bool = True
    codigo: str | None = None
    hogar_id: str | None = None  # por defecto, el hogar de la prueba
    consejo_id: str | None = None  # por defecto, el primer consejo del usuario
    query: tuple[tuple[str, str], ...] = ()
    body: Any = NO_BODY  # por defecto, el cuerpo válido de la operación (si tiene)


DEFAULT_ALERTS_BODIES: dict[str, Any] = {
    "marcarAlertasLeidas": {"alerta_ids": [str(sample_id(1, i)) for i in range(3)]},
    "actualizarEstadoConsejo": {"estado": "completada"},
}


def _guard_cases(operation_id: str, *, permission: bool) -> list[AlertsCase]:
    def case(name: str, status: int, **kw: Any) -> AlertsCase:
        return AlertsCase(name, operation_id, status, **kw)

    cases = [
        case("sin-token", 401, authenticated=False, codigo="NO_AUTENTICADO"),
        case("sin-membresia", 404, setup=without_alerts_membership, codigo="NO_ENCONTRADO"),
        case("hogar-ajeno", 404, hogar_id=str(OTHER_HOUSEHOLD_ID), codigo="NO_ENCONTRADO"),
        case("hogar-no-uuid", 422, hogar_id="no-es-un-uuid", codigo="VALIDACION"),
    ]
    if permission:
        cases += [
            case(
                "sin-permiso",
                403,
                setup=without_alerts_permission,
                codigo="SIN_PERMISO_RECIBIR_ALERTAS",
            ),
            case("admin-sin-permisos", 200, setup=admin_without_any_permission),
        ]
    else:
        cases.append(case("miembro-sin-permisos", 200, setup=member_without_any_permission))
    return cases


def _alerts_cases() -> tuple[AlertsCase, ...]:
    def listing(name: str, status: int, query: tuple[tuple[str, str], ...], **kw: Any) -> AlertsCase:
        return AlertsCase(name, "listarAlertas", status, query=query, **kw)

    def mark(name: str, status: int, body: Any, **kw: Any) -> AlertsCase:
        return AlertsCase(name, "marcarAlertasLeidas", status, body=body, **kw)

    def tip(name: str, status: int, **kw: Any) -> AlertsCase:
        return AlertsCase(name, "actualizarEstadoConsejo", status, **kw)

    return (
        # listarAlertas (RN-XIV-01, RN-XIV-04, RN-XIV-05)
        listing("todas", 200, ()),
        *(
            listing(f"categoria-{c.value}", 200, (("categoria", c.value),))
            for c in CategoriaAlerta
        ),
        listing("limite-1", 200, (("limite", "1"),)),
        listing("limite-100", 200, (("limite", "100"),)),
        listing("filtro-y-limite", 200, (("categoria", "consumo"), ("limite", "2"))),
        listing("sin-alertas", 200, (), setup=without_alerts),
        *_guard_cases("listarAlertas", permission=True),
        listing("limite-0", 422, (("limite", "0"),), codigo="VALIDACION"),
        listing("limite-101", 422, (("limite", "101"),), codigo="VALIDACION"),
        listing("limite-no-entero", 422, (("limite", "diez"),), codigo="VALIDACION"),
        listing("categoria-invalida", 422, (("categoria", "sobreconsumo"),), codigo="VALIDACION"),
        # contarAlertasNoLeidas (RN-XII-02)
        AlertsCase("con-no-leidas", "contarAlertasNoLeidas", 200),
        AlertsCase("sin-alertas", "contarAlertasNoLeidas", 200, setup=without_alerts),
        *_guard_cases("contarAlertasNoLeidas", permission=True),
        # marcarAlertasLeidas (RN-XIV-03, RN-VI-05)
        mark("marca", 200, DEFAULT_ALERTS_BODIES["marcarAlertasLeidas"]),
        mark("ids-ajenos-se-ignoran", 200, {"alerta_ids": [FOREIGN_ID]}),
        *_guard_cases("marcarAlertasLeidas", permission=True),
        mark("lista-vacia", 422, {"alerta_ids": []}, codigo="VALIDACION"),
        mark("ids-repetidos", 422, {"alerta_ids": [FOREIGN_ID, FOREIGN_ID]}, codigo="VALIDACION"),
        mark("campo-de-mas", 422, {"alerta_ids": [FOREIGN_ID], "todas": True}, codigo="VALIDACION"),
        mark("sin-alerta-ids", 422, {}, codigo="VALIDACION"),
        mark("id-no-uuid", 422, {"alerta_ids": ["no-es-un-uuid"]}, codigo="VALIDACION"),
        mark("alerta-ids-no-lista", 422, {"alerta_ids": FOREIGN_ID}, codigo="VALIDACION"),
        # listarConsejos (RN-VI-03, RN-XV-02 a RN-XV-05)
        AlertsCase("con-consejos", "listarConsejos", 200),
        AlertsCase("todo-bajo-control", "listarConsejos", 200, setup=without_tips),
        *_guard_cases("listarConsejos", permission=False),
        # actualizarEstadoConsejo (RN-XV-03, RN-XV-06, RN-VI-05)
        tip("completa", 200, body={"estado": "completada"}),
        tip("desmarca", 200, consejo_id=str(COMPLETED_TIP_ID), body={"estado": "pendiente"}),
        *_guard_cases("actualizarEstadoConsejo", permission=False),
        tip("consejo-ajeno", 404, consejo_id=FOREIGN_ID, codigo="NO_ENCONTRADO"),
        tip("estado-invalido", 422, body={"estado": "hecho"}, codigo="VALIDACION"),
        tip(
            "campo-de-mas",
            422,
            body={"estado": "completada", "completada_en": None},
            codigo="VALIDACION",
        ),
        tip("sin-estado", 422, body={}, codigo="VALIDACION"),
        tip("consejo-no-uuid", 422, consejo_id="no-es-un-uuid", codigo="VALIDACION"),
    )


ALERTS_CASES: tuple[AlertsCase, ...] = _alerts_cases()
# Casos que la guardia corta antes de llegar al servicio (los 422 tampoco llegan).
ALERTS_GUARD_STOPS = frozenset({"sin-token", "sin-permiso", "sin-membresia", "hogar-ajeno"})


def _body_of(case: AlertsCase) -> Any:
    return case.body if case.body is not NO_BODY else DEFAULT_ALERTS_BODIES.get(case.operation_id)


def alerts_url(case: AlertsCase) -> str:
    _method, path, _op = OPERATIONS[case.operation_id]
    url = API_PREFIX + path.format(
        hogar_id=case.hogar_id or str(HOGAR_ID), consejo_id=case.consejo_id or str(FIRST_TIP_ID)
    )
    return url + ("?" + urlencode(case.query) if case.query else "")


def send_alerts(client: TestClient, case: AlertsCase) -> Any:
    method, _path, _op = OPERATIONS[case.operation_id]
    headers = auth_header(make_token(USER_ID, CORREO)) if case.authenticated else {}
    kwargs: dict[str, Any] = {"headers": headers}
    body = _body_of(case)
    if body is not None:
        kwargs["json"] = body
    return client.request(method.upper(), alerts_url(case), **kwargs)


def expected_service_args(case: AlertsCase, world: AlertsWorld) -> tuple[Any, ...]:
    """Lo que el router debe pasar al servicio: la sesión de la petición, el usuario del token, el
    hogar de la ruta y la entrada ya validada (sin `now`: lo decide el servicio)."""
    base: tuple[Any, ...] = (world.session, USER_ID, HOGAR_ID)
    query = dict(case.query)
    body = _body_of(case)
    if case.operation_id == "listarAlertas":
        categoria = query.get("categoria")
        limite = int(query.get("limite", 50))  # default del contrato
        return (*base, None if categoria is None else CategoriaAlerta(categoria), limite)
    if case.operation_id == "marcarAlertasLeidas":
        return (*base, AlertasMarcar(alerta_ids=[UUID(i) for i in body["alerta_ids"]]))
    if case.operation_id == "actualizarEstadoConsejo":
        consejo_id = UUID(case.consejo_id or str(FIRST_TIP_ID))
        return (*base, consejo_id, ConsejoEstadoActualizar(estado=body["estado"]))
    return base


@pytest.mark.parametrize("case", ALERTS_CASES, ids=lambda c: f"{c.operation_id}-{c.status}-{c.name}")
def test_alerts_tips_response_matches_contract_schema(
    case: AlertsCase, client: TestClient, alerts_world: AlertsWorld
) -> None:
    world = alerts_world
    if case.setup is not None:
        case.setup(world)
    response = send_alerts(client, case)
    assert response.status_code == case.status, response.text
    assert_matches_contract(case.operation_id, response)
    assert all(s is world.session for s in world.guard_sessions)
    assert world.session.commits == 0  # el router no confirma: lo hace el servicio
    if case.status == 200 or case.name == "consejo-ajeno":
        assert world.guard_sessions == [world.session]
        ((name, args, kwargs),) = world.calls
        assert name == ALERTS_SERVICE_FUNCTIONS[case.operation_id]
        assert kwargs == {}
        assert args[0] is world.session  # la misma sesión que usó la guardia
        assert args == expected_service_args(case, world)
    if case.status == 200:
        return
    assert response.json()["codigo"] == case.codigo
    assert (response.headers.get("WWW-Authenticate") == "Bearer") == (case.status == 401)
    if case.status == 422 or case.name in ALERTS_GUARD_STOPS:
        assert world.calls == []  # no llegó al servicio


def test_alerts_tips_cases_cover_every_code_of_the_operations() -> None:
    for operation_id, expected in ALERTS_ERROR_CODES.items():
        cases = [c for c in ALERTS_CASES if c.operation_id == operation_id]
        assert {c.codigo for c in cases} - {None} == expected, operation_id
        assert any(c.status == 200 for c in cases), operation_id


def test_sample_rows_cover_nulls_and_every_value_of_the_catalog() -> None:
    """Las filas de ejemplo ejercitan los nulos y los enum que salen del catálogo del backend."""
    alerts, tips = sample_alerts(), sample_tips()
    assert {a.categoria for a in alerts} == set(CategoriaAlerta)
    assert {a.severidad for a in alerts} == {"informativa", "advertencia", "critica"}
    assert {a.zona_id is None for a in alerts} == {True, False}
    assert {a.leida_en is None for a in alerts} == {True, False}
    assert [t.prioridad for t in tips] == ["alta", "media", "baja"]
    assert {t.estado for t in tips} == {"pendiente", "completada"}


def test_tips_never_answer_403(client: TestClient, alerts_world: AlertsWorld) -> None:
    """El contrato no declara 403 en los consejos: sin `recibir_alertas` responden 200."""
    without_alerts_permission(alerts_world)
    for operation_id in ("listarConsejos", "actualizarEstadoConsejo"):
        response = send_alerts(client, AlertsCase("x", operation_id, 200))
        assert response.status_code == 200, (operation_id, response.text)


def test_list_alerts_body_is_the_service_result_in_its_order(
    client: TestClient, alerts_world: AlertsWorld
) -> None:
    """El router no reordena ni recorta: devuelve las alertas del servicio tal cual."""
    response = send_alerts(client, AlertsCase("x", "listarAlertas", 200))
    body = response.json()["alertas"]
    assert [a["id"] for a in body] == [str(a.id) for a in alerts_world.alerts]
    assert body == [a.model_dump(mode="json") for a in alerts_world.alerts]


def test_unread_count_and_marked_are_the_service_numbers(
    client: TestClient, alerts_world: AlertsWorld
) -> None:
    unread = sum(a.leida_en is None for a in alerts_world.alerts)
    assert unread > 0
    response = send_alerts(client, AlertsCase("x", "contarAlertasNoLeidas", 200))
    assert response.json() == {"cantidad": unread}
    ids = [str(a.id) for a in alerts_world.alerts]
    response = send_alerts(
        client, AlertsCase("x", "marcarAlertasLeidas", 200, body={"alerta_ids": ids})
    )
    assert response.json() == {"marcadas": unread}


def test_repeated_alert_ids_are_422_without_echoing_them(
    client: TestClient, alerts_world: AlertsWorld
) -> None:
    """`AlertasMarcar.alerta_ids` tiene `uniqueItems: true`: un id repetido es 422 `VALIDACION`
    con la ubicación del campo y sin repetir el valor enviado."""
    repeated = str(sample_id(1, 1))
    response = send_alerts(
        client,
        AlertsCase("x", "marcarAlertasLeidas", 422, body={"alerta_ids": [repeated, repeated]}),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["codigo"] == "VALIDACION"
    assert [c["ubicacion"] for c in body["detalles"]["campos"]] == [["body", "alerta_ids"]]
    assert repeated not in response.text
    assert alerts_world.calls == []


@pytest.mark.parametrize(("estado", "completed"), [("completada", True), ("pendiente", False)])
def test_update_tip_status_body_is_the_updated_tip(
    estado: str, completed: bool, client: TestClient, alerts_world: AlertsWorld
) -> None:
    """RN-XV-03: `completada` trae `completada_en`; `pendiente` lo deja null."""
    response = send_alerts(
        client, AlertsCase("x", "actualizarEstadoConsejo", 200, body={"estado": estado})
    )
    body = response.json()
    assert body["id"] == str(FIRST_TIP_ID)
    assert body["estado"] == estado
    assert (body["completada_en"] is not None) is completed


# --- miembros e invitaciones (fase 9) -----------------------------------------------------
# Las 11 operaciones con el servicio reemplazado por un doble (monkeypatch de
# `app.services.members_invitations`): aquí se prueba la capa HTTP (validación de la entrada,
# guardias, la sesión de la petición, el usuario y el correo del token, y el cuerpo contra el
# contrato). Las reglas (RN-II-01..04, RN-X-05..08, RN-IX-03, DC-04, DC-25, DC-41, DC-42) están
# probadas con el servicio real en `tests/services/test_members_invitations_service.py`.
# Los errores que decide el servicio los lanza el doble con el código del contrato.

MEMBERS_SERVICE_FUNCTIONS = {
    "listarMiembros": "list_members",
    "actualizarPermisos": "update_permissions",
    "expulsarMiembro": "remove_member",
    "transferirAdministracion": "transfer_admin",
    "salirDelHogar": "leave_household",
    "crearInvitacion": "create_invitation",
    "revocarInvitacion": "revoke_invitation",
    "listarInvitacionesRecibidas": "list_received_invitations",
    "resolverTokenInvitacion": "resolve_invitation_token",
    "aceptarInvitacion": "accept_invitation",
    "rechazarInvitacion": "reject_invitation",
}
MEMBERS_ADMIN_OPERATIONS = frozenset(
    {
        "actualizarPermisos",
        "expulsarMiembro",
        "transferirAdministracion",
        "crearInvitacion",
        "revocarInvitacion",
    }
)
INVITEE_OPERATIONS = frozenset(
    {
        "listarInvitacionesRecibidas",
        "resolverTokenInvitacion",
        "aceptarInvitacion",
        "rechazarInvitacion",
    }
)
_MEMBER_GUARD_CODES = frozenset({"NO_AUTENTICADO", "NO_ENCONTRADO", "VALIDACION"})
_ADMIN_GUARD_CODES = _MEMBER_GUARD_CODES | {"NO_ES_ADMINISTRADOR"}
_INVITATION_STATE_CODES = frozenset({"INVITACION_NO_PENDIENTE", "INVITACION_EXPIRADA"})
_INVITEE_CODES = (
    frozenset({"NO_AUTENTICADO", "CORREO_NO_COINCIDE", "NO_ENCONTRADO", "VALIDACION"})
    | _INVITATION_STATE_CODES
)
MEMBERS_ERROR_CODES = {
    "listarMiembros": _MEMBER_GUARD_CODES,
    "actualizarPermisos": _ADMIN_GUARD_CODES,
    "expulsarMiembro": _ADMIN_GUARD_CODES | {"ADMIN_DEBE_TRANSFERIR", "ADMIN_UNICO_MIEMBRO"},
    "transferirAdministracion": _ADMIN_GUARD_CODES,
    "salirDelHogar": _MEMBER_GUARD_CODES | {"ADMIN_DEBE_TRANSFERIR", "ADMIN_UNICO_MIEMBRO"},
    "crearInvitacion": _ADMIN_GUARD_CODES
    | {"LIMITE_MIEMBROS", "INVITACION_PENDIENTE_EXISTENTE", "YA_ES_MIEMBRO"},
    "revocarInvitacion": _ADMIN_GUARD_CODES | _INVITATION_STATE_CODES,
    "listarInvitacionesRecibidas": frozenset({"NO_AUTENTICADO"}),
    "resolverTokenInvitacion": _INVITEE_CODES,
    "aceptarInvitacion": _INVITEE_CODES | {"LIMITE_MIEMBROS", "MEMBRESIA_ACTIVA_EXISTENTE"},
    "rechazarInvitacion": _INVITEE_CODES,
}
MEMBERS_JOINED_AT = datetime(2026, 11, 2, 9, 30, tzinfo=TIMEZONE)
INVITED_AT = datetime(2026, 11, 23, 10, 0, tzinfo=TIMEZONE)
INVITATION_EXPIRES_AT = INVITED_AT + timedelta(days=7)  # RN-X-05
OTHER_MEMBER_ID = sample_id(3, 1)  # membresía de otra persona del hogar
INVITATION_ID = sample_id(5, 0)
NEW_MEMBERSHIP_ID = sample_id(3, 9)
INVITED_EMAIL = "invitada@example.com"
INVITATION_TOKEN = "token-de-prueba-sin-valor-real"
MEMBERS_HOUSEHOLD_NAME = "Casa Gómez"
DEFAULT_PERMISSIONS = Permisos(  # permisos por defecto de un hogar nuevo (RN-II-03)
    ver_consumo_actual=True, ver_historial=True, recibir_alertas=True, modificar_metas=False
)


def sample_members() -> list[Miembro]:
    """Administrador (quien llama, con foto) y dos miembros sin foto (`avatar_url` null)."""
    people = [
        (MEMBRESIA_ID, USER_ID, "Laura Gómez", f"{USER_ID}/avatar.png", Rol.ADMINISTRADOR),
        (OTHER_MEMBER_ID, sample_id(4, 1), "Andrés Gómez", None, Rol.MIEMBRO),
        (sample_id(3, 2), sample_id(4, 2), "Sofía Gómez", None, Rol.MIEMBRO),
    ]
    return [
        Miembro(
            membresia_id=membresia_id,
            usuario_id=usuario_id,
            nombre_completo=nombre,
            avatar_url=avatar,
            rol=rol,
            estado="activo",
            fecha_ingreso=MEMBERS_JOINED_AT + timedelta(days=index),
        )
        for index, (membresia_id, usuario_id, nombre, avatar, rol) in enumerate(people)
    ]


def sample_pending_invitations() -> list[InvitacionPendiente]:
    return [
        InvitacionPendiente(
            id=sample_id(5, index + 1),
            correo_invitado=f"invitada{index}@example.com",
            estado="pendiente",
            expira_en=INVITATION_EXPIRES_AT - timedelta(days=index),
        )
        for index in range(2)
    ]


def sample_received_invitations() -> list[InvitacionRecibida]:
    return [
        InvitacionRecibida(
            id=INVITATION_ID,
            hogar_nombre=MEMBERS_HOUSEHOLD_NAME,
            invitado_por_nombre="Laura Gómez",
            expira_en=INVITATION_EXPIRES_AT,
        )
    ]


@dataclass
class MembersWorld:
    """Membresías de la guardia, respuestas del doble del servicio y llamadas recibidas.

    Los dobles tienen la firma posicional de `app.services.members_invitations` (ver sus
    docstrings): un argumento de más o de menos es un TypeError (500) y la prueba falla. Si
    `error` no es None, el doble lo lanza tras registrar la llamada (ese error lo decide el
    servicio, con los códigos del contrato para RN-X-05 a RN-X-08).
    """

    session: RecordingSession
    memberships: list[ActiveMembershipRow]
    members: list[Miembro] = field(default_factory=sample_members)
    pending: list[InvitacionPendiente] = field(default_factory=sample_pending_invitations)
    received: list[InvitacionRecibida] = field(default_factory=sample_received_invitations)
    error: ApiError | None = None
    guard_sessions: list[object] = field(default_factory=list)
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)

    def _record(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.calls.append((name, args, kwargs))
        if self.error is not None:
            raise self.error

    def _view(self, *, is_admin: bool) -> MiembrosHogar:
        return MiembrosHogar(
            miembros_activos=len(self.members),
            miembros=list(self.members),
            invitaciones_pendientes=list(self.pending) if is_admin else None,
            permisos=DEFAULT_PERMISSIONS,
            puede_gestionar=is_admin,
        )

    def list_members(
        self, session: object, user_id: UUID, hogar_id: UUID, **kw: Any
    ) -> MiembrosHogar:
        self._record("list_members", (session, user_id, hogar_id), kw)
        own = next(m for m in self.memberships if m.usuario_id == user_id)
        return self._view(is_admin=own.rol == "administrador")

    def update_permissions(
        self, session: object, user_id: UUID, hogar_id: UUID, payload: PermisosActualizar, **kw: Any
    ) -> Permisos:
        self._record("update_permissions", (session, user_id, hogar_id, payload), kw)
        return DEFAULT_PERMISSIONS.model_copy(update=payload.model_dump(exclude_unset=True))

    def remove_member(
        self, session: object, user_id: UUID, hogar_id: UUID, membresia_id: UUID, **kw: Any
    ) -> None:
        self._record("remove_member", (session, user_id, hogar_id, membresia_id), kw)

    def transfer_admin(
        self, session: object, user_id: UUID, hogar_id: UUID, membresia_id: UUID, **kw: Any
    ) -> MiembrosHogar:
        self._record("transfer_admin", (session, user_id, hogar_id, membresia_id), kw)
        self.members = [
            m.model_copy(
                update={"rol": Rol.ADMINISTRADOR if m.membresia_id == membresia_id else Rol.MIEMBRO}
            )
            for m in self.members
        ]
        return self._view(is_admin=False)  # quien transfirió ya es miembro

    def leave_household(self, session: object, user_id: UUID, hogar_id: UUID, **kw: Any) -> None:
        self._record("leave_household", (session, user_id, hogar_id), kw)

    def create_invitation(
        self,
        session: object,
        settings: Settings,
        user_id: UUID,
        hogar_id: UUID,
        payload: InvitacionCrear,
        **kw: Any,
    ) -> InvitacionPendiente:
        self._record("create_invitation", (session, settings, user_id, hogar_id, payload), kw)
        return InvitacionPendiente(
            id=INVITATION_ID,
            correo_invitado=payload.correo_invitado.strip().lower(),
            estado="pendiente",
            expira_en=INVITATION_EXPIRES_AT,
        )

    def revoke_invitation(
        self, session: object, user_id: UUID, hogar_id: UUID, invitacion_id: UUID, **kw: Any
    ) -> None:
        self._record("revoke_invitation", (session, user_id, hogar_id, invitacion_id), kw)

    def list_received_invitations(
        self, session: object, user_id: UUID, correo: str, **kw: Any
    ) -> InvitacionesRecibidasLista:
        self._record("list_received_invitations", (session, user_id, correo), kw)
        return InvitacionesRecibidasLista(invitaciones=list(self.received))

    def resolve_invitation_token(
        self, session: object, user_id: UUID, correo: str, payload: InvitacionToken, **kw: Any
    ) -> InvitacionRecibida:
        self._record("resolve_invitation_token", (session, user_id, correo, payload), kw)
        return self.received[0]

    def accept_invitation(
        self, session: object, user_id: UUID, correo: str, invitacion_id: UUID, **kw: Any
    ) -> MembresiaResumen:
        self._record("accept_invitation", (session, user_id, correo, invitacion_id), kw)
        return MembresiaResumen(membresia_id=NEW_MEMBERSHIP_ID, hogar_id=HOGAR_ID, rol=Rol.MIEMBRO)

    def reject_invitation(
        self, session: object, user_id: UUID, correo: str, invitacion_id: UUID, **kw: Any
    ) -> None:
        self._record("reject_invitation", (session, user_id, correo, invitacion_id), kw)


@pytest.fixture
def members_world(monkeypatch: pytest.MonkeyPatch, store: FakeStore) -> MembersWorld:
    world = MembersWorld(
        session=store.session,
        memberships=[
            make_membership_row(USER_ID, HOGAR_ID, rol="administrador", membresia_id=MEMBRESIA_ID)
        ],
    )

    def fake_get_active_membership(
        session: object, usuario_id: UUID, hogar_id: UUID
    ) -> ActiveMembershipRow | None:
        world.guard_sessions.append(session)
        return next(
            (m for m in world.memberships if m.usuario_id == usuario_id and m.hogar_id == hogar_id),
            None,
        )

    monkeypatch.setattr(memberships_data, "get_active_membership", fake_get_active_membership)
    for name in MEMBERS_SERVICE_FUNCTIONS.values():
        assert hasattr(members_service, name), name
        monkeypatch.setattr(members_service, name, getattr(world, name))
    return world


# Preparaciones de los casos (reciben el `MembersWorld`).
def as_member(world: MembersWorld) -> None:
    """Quien llama es miembro, con todos los permisos: ninguno lo convierte en administrador."""
    world.memberships[:] = [
        make_membership_row(
            USER_ID,
            HOGAR_ID,
            rol="miembro",
            membresia_id=MEMBRESIA_ID,
            ver_consumo_actual=True,
            ver_historial=True,
            recibir_alertas=True,
            modificar_metas=True,
        )
    ]


def without_members_membership(world: MembersWorld) -> None:
    world.memberships.clear()


def without_pending(world: MembersWorld) -> None:
    world.pending.clear()


def without_received(world: MembersWorld) -> None:
    world.received.clear()


def service_raises(status: int, codigo: str, **detalles: Any) -> Callable[[MembersWorld], None]:
    """El servicio responde con ese error del contrato (mensaje corto; la app usa el código)."""

    def setup(world: MembersWorld) -> None:
        world.error = ApiError(status, CodigoError(codigo), "Error del servicio.", detalles or None)

    return setup


def as_member_and_service_raises(status: int, codigo: str) -> Callable[[MembersWorld], None]:
    def setup(world: MembersWorld) -> None:
        as_member(world)
        service_raises(status, codigo)(world)

    return setup


@dataclass(frozen=True)
class MembersCase:
    name: str
    operation_id: str
    status: int
    setup: Callable[[MembersWorld], None] | None = None
    authenticated: bool = True
    codigo: str | None = None
    hogar_id: str | None = None  # por defecto, el hogar de la prueba
    target_id: str | None = None  # membresia_id o invitacion_id de la ruta (por defecto, uno válido)
    body: Any = NO_BODY  # por defecto, el cuerpo válido de la operación (si tiene)


DEFAULT_MEMBERS_BODIES: dict[str, Any] = {
    "actualizarPermisos": {"ver_historial": False, "modificar_metas": True},
    "crearInvitacion": {"correo_invitado": INVITED_EMAIL},
    "resolverTokenInvitacion": {"token": INVITATION_TOKEN},
}


def _members_guard_cases(operation_id: str) -> list[MembersCase]:
    """Guardias de las rutas de `/hogares/{hogar_id}`: 401 → 404 → 403 (solo administrador)."""

    def case(name: str, status: int, **kw: Any) -> MembersCase:
        return MembersCase(name, operation_id, status, **kw)

    cases = [
        case("sin-token", 401, authenticated=False, codigo="NO_AUTENTICADO"),
        case("sin-membresia", 404, setup=without_members_membership, codigo="NO_ENCONTRADO"),
        case("hogar-ajeno", 404, hogar_id=str(OTHER_HOUSEHOLD_ID), codigo="NO_ENCONTRADO"),
        case("hogar-no-uuid", 422, hogar_id="no-es-un-uuid", codigo="VALIDACION"),
    ]
    if operation_id in MEMBERS_ADMIN_OPERATIONS:
        cases.append(case("miembro", 403, setup=as_member, codigo="NO_ES_ADMINISTRADOR"))
    return cases


def _invitee_cases(operation_id: str, *, by_id: bool) -> list[MembersCase]:
    """Errores de la persona invitada: los decide el servicio (la ruta solo exige el token)."""

    def case(name: str, status: int, **kw: Any) -> MembersCase:
        return MembersCase(name, operation_id, status, **kw)

    cases = [
        case("sin-token", 401, authenticated=False, codigo="NO_AUTENTICADO"),
        case(
            "correo-distinto",
            403,
            setup=service_raises(403, "CORREO_NO_COINCIDE"),
            codigo="CORREO_NO_COINCIDE",
        ),
        case("no-existe", 404, setup=service_raises(404, "NO_ENCONTRADO"), codigo="NO_ENCONTRADO"),
        case(
            "no-pendiente",
            409,
            setup=service_raises(409, "INVITACION_NO_PENDIENTE"),
            codigo="INVITACION_NO_PENDIENTE",
        ),
        case(
            "vencida",
            409,
            setup=service_raises(409, "INVITACION_EXPIRADA"),
            codigo="INVITACION_EXPIRADA",
        ),
    ]
    if by_id:
        cases.append(
            case("invitacion-no-uuid", 422, target_id="no-es-un-uuid", codigo="VALIDACION")
        )
    return cases


def _members_cases() -> tuple[MembersCase, ...]:
    def op(operation_id: str) -> Callable[..., MembersCase]:
        def case(name: str, status: int, **kw: Any) -> MembersCase:
            return MembersCase(name, operation_id, status, **kw)

        return case

    listing = op("listarMiembros")
    permissions = op("actualizarPermisos")
    remove = op("expulsarMiembro")
    transfer = op("transferirAdministracion")
    leave = op("salirDelHogar")
    invite = op("crearInvitacion")
    revoke = op("revocarInvitacion")
    received = op("listarInvitacionesRecibidas")
    resolve = op("resolverTokenInvitacion")
    accept = op("aceptarInvitacion")
    reject = op("rechazarInvitacion")
    all_off = dict.fromkeys(DEFAULT_PERMISSIONS.model_dump(), False)
    return (
        # listarMiembros (RN-XVI-07, RN-X-08)
        listing("admin-con-invitaciones", 200),
        listing("admin-sin-invitaciones", 200, setup=without_pending),
        listing("miembro-sin-invitaciones", 200, setup=as_member),
        *_members_guard_cases("listarMiembros"),
        # actualizarPermisos (RN-II-03, RN-X-08)
        permissions("cambia-dos", 200),
        permissions("cambia-todos", 200, body=all_off),
        *_members_guard_cases("actualizarPermisos"),
        permissions("cuerpo-vacio", 422, body={}, codigo="VALIDACION"),
        permissions("permiso-null", 422, body={"ver_historial": None}, codigo="VALIDACION"),
        permissions("no-booleano", 422, body={"ver_historial": "talvez"}, codigo="VALIDACION"),
        permissions("campo-de-mas", 422, body={"es_admin": True}, codigo="VALIDACION"),
        permissions("cuerpo-no-objeto", 422, body=[True], codigo="VALIDACION"),
        # expulsarMiembro (RN-II-04, RN-X-07)
        remove("expulsa", 204),
        *_members_guard_cases("expulsarMiembro"),
        remove(
            "membresia-inactiva-o-ajena",
            404,
            setup=service_raises(404, "NO_ENCONTRADO"),
            codigo="NO_ENCONTRADO",
            target_id=FOREIGN_ID,
        ),
        remove(
            "a-si-mismo-con-otros",
            409,
            setup=service_raises(409, "ADMIN_DEBE_TRANSFERIR"),
            codigo="ADMIN_DEBE_TRANSFERIR",
            target_id=str(MEMBRESIA_ID),
        ),
        remove(
            "a-si-mismo-unico",
            409,
            setup=service_raises(409, "ADMIN_UNICO_MIEMBRO"),
            codigo="ADMIN_UNICO_MIEMBRO",
            target_id=str(MEMBRESIA_ID),
        ),
        remove("membresia-no-uuid", 422, target_id="no-es-un-uuid", codigo="VALIDACION"),
        # transferirAdministracion (RN-II-04, RN-X-07)
        transfer("transfiere", 200),
        *_members_guard_cases("transferirAdministracion"),
        transfer(
            "destino-inactivo-o-ajeno",
            404,
            setup=service_raises(404, "NO_ENCONTRADO"),
            codigo="NO_ENCONTRADO",
            target_id=FOREIGN_ID,
        ),
        transfer(
            "a-si-mismo",
            422,
            setup=service_raises(
                422,
                "VALIDACION",
                campos=[{"ubicacion": ["path", "membresia_id"], "mensaje": "Es la propia."}],
            ),
            codigo="VALIDACION",
            target_id=str(MEMBRESIA_ID),
        ),
        transfer("membresia-no-uuid", 422, target_id="no-es-un-uuid", codigo="VALIDACION"),
        # salirDelHogar (RN-II-04, RN-X-07)
        leave("miembro-sale", 204, setup=as_member),
        *_members_guard_cases("salirDelHogar"),
        leave(
            "admin-con-otros",
            409,
            setup=service_raises(409, "ADMIN_DEBE_TRANSFERIR"),
            codigo="ADMIN_DEBE_TRANSFERIR",
        ),
        leave(
            "admin-unico",
            409,
            setup=service_raises(409, "ADMIN_UNICO_MIEMBRO"),
            codigo="ADMIN_UNICO_MIEMBRO",
        ),
        # crearInvitacion (RN-X-05, RN-IX-03, DC-04, DC-41, DC-42)
        invite("crea", 201),
        invite("correo-con-mayusculas", 201, body={"correo_invitado": "Invitada@Example.com"}),
        *_members_guard_cases("crearInvitacion"),
        invite(
            "limite", 409, setup=service_raises(409, "LIMITE_MIEMBROS"), codigo="LIMITE_MIEMBROS"
        ),
        invite(
            "pendiente-existente",
            409,
            setup=service_raises(409, "INVITACION_PENDIENTE_EXISTENTE"),
            codigo="INVITACION_PENDIENTE_EXISTENTE",
        ),
        invite(
            "ya-es-miembro", 409, setup=service_raises(409, "YA_ES_MIEMBRO"), codigo="YA_ES_MIEMBRO"
        ),
        invite(
            "correo-invalido", 422, body={"correo_invitado": "no-es-correo"}, codigo="VALIDACION"
        ),
        invite("sin-correo", 422, body={}, codigo="VALIDACION"),
        invite(
            "campo-de-mas",
            422,
            body={"correo_invitado": INVITED_EMAIL, "rol": "administrador"},
            codigo="VALIDACION",
        ),
        # revocarInvitacion (RN-X-06, DC-42)
        revoke("revoca", 204),
        *_members_guard_cases("revocarInvitacion"),
        revoke(
            "de-otro-hogar",
            404,
            setup=service_raises(404, "NO_ENCONTRADO"),
            codigo="NO_ENCONTRADO",
            target_id=FOREIGN_ID,
        ),
        revoke(
            "no-pendiente",
            409,
            setup=service_raises(409, "INVITACION_NO_PENDIENTE"),
            codigo="INVITACION_NO_PENDIENTE",
        ),
        revoke(
            "vencida",
            409,
            setup=service_raises(409, "INVITACION_EXPIRADA"),
            codigo="INVITACION_EXPIRADA",
        ),
        revoke("invitacion-no-uuid", 422, target_id="no-es-un-uuid", codigo="VALIDACION"),
        # listarInvitacionesRecibidas (RN-X-01, DC-42)
        received("con-invitaciones", 200),
        received("sin-invitaciones", 200, setup=without_received),
        received("sin-hogar", 200, setup=without_members_membership),  # no exige membresía
        received("sin-token", 401, authenticated=False, codigo="NO_AUTENTICADO"),
        # resolverTokenInvitacion (RN-X-05)
        resolve("resuelve", 200),
        *_invitee_cases("resolverTokenInvitacion", by_id=False),
        resolve("token-vacio", 422, body={"token": ""}, codigo="VALIDACION"),
        resolve("sin-token-en-cuerpo", 422, body={}, codigo="VALIDACION"),
        resolve(
            "campo-de-mas",
            422,
            body={"token": INVITATION_TOKEN, "correo": INVITED_EMAIL},
            codigo="VALIDACION",
        ),
        # aceptarInvitacion (RN-X-05, RN-X-06, RN-II-02, DC-25)
        accept("acepta", 200, setup=without_members_membership),
        *_invitee_cases("aceptarInvitacion", by_id=True),
        accept(
            "sin-ficha", 404, setup=service_raises(404, "NO_ENCONTRADO"), codigo="NO_ENCONTRADO"
        ),
        accept(
            "limite", 409, setup=service_raises(409, "LIMITE_MIEMBROS"), codigo="LIMITE_MIEMBROS"
        ),
        accept(
            "con-hogar-activo",
            409,
            setup=as_member_and_service_raises(409, "MEMBRESIA_ACTIVA_EXISTENTE"),
            codigo="MEMBRESIA_ACTIVA_EXISTENTE",
        ),
        # rechazarInvitacion (RN-X-06)
        reject("rechaza", 204),
        *_invitee_cases("rechazarInvitacion", by_id=True),
    )


MEMBERS_CASES: tuple[MembersCase, ...] = _members_cases()
# Casos que la guardia corta antes de llegar al servicio (los 422 de entrada tampoco llegan).
MEMBERS_GUARD_STOPS = frozenset({"sin-token", "sin-membresia", "hogar-ajeno", "miembro"})


def _members_body_of(case: MembersCase) -> Any:
    return case.body if case.body is not NO_BODY else DEFAULT_MEMBERS_BODIES.get(case.operation_id)


def _members_target(case: MembersCase) -> str | None:
    """Id de la ruta: el del caso o uno válido (otra membresía del hogar o la invitación)."""
    _method, path, _op = OPERATIONS[case.operation_id]
    if "{membresia_id}" in path:
        return case.target_id or str(OTHER_MEMBER_ID)
    if "{invitacion_id}" in path:
        return case.target_id or str(INVITATION_ID)
    return None


def members_url(case: MembersCase) -> str:
    _method, path, _op = OPERATIONS[case.operation_id]
    target = _members_target(case)
    return API_PREFIX + path.format(
        hogar_id=case.hogar_id or str(HOGAR_ID), membresia_id=target, invitacion_id=target
    )


def send_members(client: TestClient, case: MembersCase) -> Any:
    method, _path, _op = OPERATIONS[case.operation_id]
    headers = auth_header(make_token(USER_ID, CORREO)) if case.authenticated else {}
    kwargs: dict[str, Any] = {"headers": headers}
    body = _members_body_of(case)
    if body is not None:
        kwargs["json"] = body
    return client.request(method.upper(), members_url(case), **kwargs)


def expected_members_service_args(case: MembersCase, world: MembersWorld) -> tuple[Any, ...]:
    """Lo que el router debe pasar al servicio (firmas de `app.services.members_invitations`):
    la sesión de la petición, el usuario del token, el hogar de la ruta (o el correo del token en
    `/invitaciones`, para el 403 `CORREO_NO_COINCIDE` de RN-X-05), el id de la ruta y la entrada
    ya validada; sin `now` (lo decide el servicio). `crearInvitacion` recibe además la
    configuración (se compara aparte)."""
    body = _members_body_of(case)
    target = _members_target(case)
    rest: tuple[Any, ...] = () if target is None else (UUID(target),)
    if case.operation_id == "actualizarPermisos":
        rest = (PermisosActualizar(**body),)
    elif case.operation_id == "crearInvitacion":
        rest = (InvitacionCrear(**body),)
    elif case.operation_id == "resolverTokenInvitacion":
        rest = (InvitacionToken(**body),)
    if case.operation_id in INVITEE_OPERATIONS:
        return (world.session, USER_ID, CORREO, *rest)
    return (world.session, USER_ID, HOGAR_ID, *rest)


@pytest.mark.parametrize(
    "case", MEMBERS_CASES, ids=lambda c: f"{c.operation_id}-{c.status}-{c.name}"
)
def test_members_invitations_response_matches_contract_schema(
    case: MembersCase, client: TestClient, members_world: MembersWorld
) -> None:
    world = members_world
    if case.setup is not None:
        case.setup(world)
    response = send_members(client, case)
    assert response.status_code == case.status, response.text
    assert_matches_contract(case.operation_id, response)
    assert all(s is world.session for s in world.guard_sessions)
    assert world.session.commits == 0  # el router no confirma: lo hace el servicio
    reaches_service = case.name not in MEMBERS_GUARD_STOPS and (
        case.status != 422 or world.error is not None
    )
    if reaches_service:
        uses_guard = case.operation_id not in INVITEE_OPERATIONS
        assert world.guard_sessions == ([world.session] if uses_guard else [])
        ((name, args, kwargs),) = world.calls
        assert name == MEMBERS_SERVICE_FUNCTIONS[case.operation_id]
        assert kwargs == {}
        assert args[0] is world.session  # la misma sesión que usó la guardia
        if case.operation_id == "crearInvitacion":
            settings = args[1]
            assert isinstance(settings, Settings)
            assert settings.supabase_url == TEST_SUPABASE_URL  # la de `get_settings`
            args = (args[0], *args[2:])
        assert args == expected_members_service_args(case, world)
    else:
        assert world.calls == []  # no llegó al servicio
    if case.status < 300:
        return
    assert response.json()["codigo"] == case.codigo
    assert (response.headers.get("WWW-Authenticate") == "Bearer") == (case.status == 401)


def test_members_invitations_cases_cover_every_code_of_the_operations() -> None:
    assert set(MEMBERS_ERROR_CODES) == set(MEMBERS_SERVICE_FUNCTIONS) == MEMBERS_OPERATIONS
    for operation_id, expected in MEMBERS_ERROR_CODES.items():
        cases = [c for c in MEMBERS_CASES if c.operation_id == operation_id]
        assert {c.codigo for c in cases} - {None} == expected, operation_id
        assert any(c.status < 300 for c in cases), operation_id


def test_guard_cases_use_the_contract_guard_of_each_operation() -> None:
    """Gestión (5): administrador; ver miembros y salir: membresía; `/invitaciones` (4): token."""
    for operation_id in MEMBERS_OPERATIONS:
        names = {c.name for c in MEMBERS_CASES if c.operation_id == operation_id}
        assert ("miembro" in names) is (operation_id in MEMBERS_ADMIN_OPERATIONS), operation_id
        assert ("sin-membresia" in names) is (operation_id not in INVITEE_OPERATIONS), operation_id


def test_patch_permissions_passes_only_the_sent_fields(
    client: TestClient, members_world: MembersWorld
) -> None:
    """PATCH parcial: el servicio recibe solo los permisos enviados (`model_fields_set`)."""
    body = {"recibir_alertas": False}
    response = send_members(client, MembersCase("x", "actualizarPermisos", 200, body=body))
    assert response.json() == {**DEFAULT_PERMISSIONS.model_dump(), "recibir_alertas": False}
    ((_name, args, _kwargs),) = members_world.calls
    assert args[-1].model_fields_set == {"recibir_alertas"}


def test_list_members_hides_pending_invitations_from_members(
    client: TestClient, members_world: MembersWorld
) -> None:
    """Sección 7.3: el administrador ve las invitaciones pendientes; un miembro recibe null."""
    admin = send_members(client, MembersCase("x", "listarMiembros", 200)).json()
    assert [i["id"] for i in admin["invitaciones_pendientes"]] == [
        str(i.id) for i in members_world.pending
    ]
    assert admin["puede_gestionar"] is True
    as_member(members_world)
    member = send_members(client, MembersCase("x", "listarMiembros", 200)).json()
    assert member["invitaciones_pendientes"] is None
    assert member["puede_gestionar"] is False
    assert member["miembros"] == [m.model_dump(mode="json") for m in members_world.members]


def test_invitation_token_is_not_in_the_response_nor_echoed_on_errors(
    client: TestClient, members_world: MembersWorld
) -> None:
    """RN-X-05: el token viaja en el cuerpo y no vuelve en la respuesta ni en los errores."""
    ok = send_members(client, MembersCase("x", "resolverTokenInvitacion", 200))
    assert INVITATION_TOKEN not in ok.text
    bad = send_members(
        client,
        MembersCase(
            "x",
            "resolverTokenInvitacion",
            422,
            body={"token": INVITATION_TOKEN, "de_mas": INVITATION_TOKEN},
        ),
    )
    assert bad.status_code == 422
    assert INVITATION_TOKEN not in bad.text


def test_invalid_invited_email_is_422_without_echoing_it(
    client: TestClient, members_world: MembersWorld
) -> None:
    """S-01: el correo inválido no se repite en la respuesta; el error ubica el campo."""
    wrong = "persona-sin-arroba.example.com"
    response = send_members(
        client, MembersCase("x", "crearInvitacion", 422, body={"correo_invitado": wrong})
    )
    assert response.status_code == 422
    body = response.json()
    assert [c["ubicacion"] for c in body["detalles"]["campos"]] == [["body", "correo_invitado"]]
    assert wrong not in response.text
    assert members_world.calls == []


# --- operaciones pendientes ---------------------------------------------------------------


def test_health_body_is_exactly_ok(client: TestClient) -> None:
    body = send(client, Case("x", "obtenerSalud", 200, authenticated=False)).json()
    assert body == {"estado": "ok"}


@pytest.mark.parametrize("operation_id", sorted(set(OPERATIONS) - COVERED_OPERATIONS))
def test_pending_operations(operation_id: str) -> None:
    pytest.skip(f"TODO(C-01): {operation_id} aún no implementada")
