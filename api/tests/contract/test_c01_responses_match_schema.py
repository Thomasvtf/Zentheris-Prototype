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
RN-X-03, RN-X-04, RN-IV-01, RN-IV-07, RN-II-01, RN-II-03; errores DC-16.
Las demás: TODO(C-01).
"""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.config import Settings, get_settings
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import users as users_data
from app.data.database import get_session
from app.data.memberships import ActiveMembershipExistsError, MembershipSummaryRow
from app.data.users import PreferencesRow, UserProfileRow
from app.domain.zone_rules import BASIC_ZONES, PERSONALITIES, ZONE_TYPES
from app.main import API_PREFIX, create_app
from app.services import supabase_admin
from tests.helpers.auth import (
    TEST_SUPABASE_URL,
    auth_header,
    install_test_jwks,
    make_test_settings,
    make_token,
)
from tests.helpers.onboarding import (
    REFERENCE_HOUSEHOLDS,
    FakeDatabase,
    install_fake_database,
)
from tests.helpers.personalities import PERSONALITY_ORDER

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
# Operaciones con C-01 real: las de la fase 3, el onboarding y la salud (sin autenticación).
COVERED_OPERATIONS = PHASE_OPERATIONS | {"obtenerSalud", "crearHogarOnboarding"}
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
    cases = CASES + ONBOARDING_CASES
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


# --- operaciones pendientes ---------------------------------------------------------------


def test_health_body_is_exactly_ok(client: TestClient) -> None:
    body = send(client, Case("x", "obtenerSalud", 200, authenticated=False)).json()
    assert body == {"estado": "ok"}


@pytest.mark.parametrize("operation_id", sorted(set(OPERATIONS) - COVERED_OPERATIONS))
def test_pending_operations(operation_id: str) -> None:
    pytest.skip(f"TODO(C-01): {operation_id} aún no implementada")
