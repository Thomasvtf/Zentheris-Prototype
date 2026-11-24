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
`PuntoSerie.zonas` solo con el filtro General, en el orden de `participacion_zonas`).
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
from app.main import API_PREFIX, create_app
from app.services import consumption as consumption_service
from app.services import hour_recovery, supabase_admin
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
# Operaciones con C-01 real: las de la fase 3, el onboarding, la salud (sin autenticación), las
# consultas de consumo de la fase 6 y el historial de la fase 7.
COVERED_OPERATIONS = PHASE_OPERATIONS | CONSUMPTION_OPERATIONS | {
    "obtenerSalud",
    "crearHogarOnboarding",
    HISTORY_OPERATION,
}
# Rangos del contrato que no se pueden provocar: `/salud` no tiene parámetros ni cuerpo, así que
# ninguna petición a esa operación da un 4XX propio.
UNREACHABLE_RANGES = frozenset({("obtenerSalud", "4XX")})
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
    """Sesión de la petición: solo cuenta commits; cualquier otro uso falla (sin SQL)."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

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
    cases = CASES + ONBOARDING_CASES + CONSUMPTION_CASES + HISTORY_CASES
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


# --- operaciones pendientes ---------------------------------------------------------------


def test_health_body_is_exactly_ok(client: TestClient) -> None:
    body = send(client, Case("x", "obtenerSalud", 200, authenticated=False)).json()
    assert body == {"estado": "ok"}


@pytest.mark.parametrize("operation_id", sorted(set(OPERATIONS) - COVERED_OPERATIONS))
def test_pending_operations(operation_id: str) -> None:
    pytest.skip(f"TODO(C-01): {operation_id} aún no implementada")
