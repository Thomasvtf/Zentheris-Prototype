"""Seguridad de punta a punta (fase 2): token → membresía → rol y permiso, sobre la app real.

Usa `create_app(make_test_settings())` con sus routers reales, el JWKS de prueba, membresías
falsas y una sesión falsa: sin base, sin red y sin secretos. Las operaciones salen del
contrato `docs/api/zentheris-api.yaml` (no de una lista escrita a mano); de las
reglas solo se toman qué operaciones exigen cada permiso (RN-XVII-01…04) y cuáles son solo
del administrador (RN-X-08, RN-XVI-05).

Cuando los guardias dejan pasar, responde el esqueleto del servicio: 501 `TODO(<operationId>)`.
Eso prueba que el guardia no bloquea, no que la operación devuelva 200: el 200 de P-06 y los
valores ocultos de P-07 se prueban cuando cada servicio exista.

Operaciones ya implementadas (`IMPLEMENTED_OPERATIONS`, fase 6: las 3 de consumo actual; fase
7: `obtenerHistorial`; fase 8: las 5 de alertas y consejos): con la guardia superada responden 200
con un cuerpo válido según el contrato. Para las de alertas y consejos, `call_api` reemplaza las
funciones de `data/alerts.py` y `data/tips.py` por dobles mínimos (sin alertas; un consejo
pendiente con el `consejo_id` de la ruta) y entrega una sesión que admite `commit`; su
contenido se prueba en `test_alerts_e2e.py`. Para que lleguen al servicio sin base, `call_api` instala los dobles de `app.data` de
`tests/services/consumption_fakes.py` (un hogar con una zona, sin lecturas ni tarifas; incluye
`tariffs_data.list_tariffs_between`; la recuperación de horas es un espía) y los umbrales de
`make_test_settings()`. La prueba sigue siendo de la guardia: el contenido de la respuesta se
prueba en `test_consumption_e2e.py` y `test_history_e2e.py`.

Fase 9 (las 11 de «Miembros e invitaciones»): `call_api` instala el doble en memoria de
`tests/services/members_fakes.py` sembrado con lo que dicen las membresías de la prueba (el rol de
quien llama en `HOGAR_ID`, otro miembro activo con el `membresia_id` de la ruta y una invitación
pendiente vigente con el `invitacion_id` de la ruta) y una sesión que admite `commit` y
`rollback`. Superada la guardia responden su éxito del contrato (200, 201 o 204). Única
excepción: un administrador que pide `salirDelHogar` pasa la guardia y recibe la respuesta de la
regla RN-X-07 (409 `ADMIN_DEBE_TRANSFERIR`, hay otro miembro), no un 403/404 de la guardia. Su
contenido se prueba en `test_members_e2e.py`.

Los 401 llevan `codigo` = `NO_AUTENTICADO` (con `WWW-Authenticate: Bearer`) y el 404 sin
membresía `NO_ENCONTRADO`; ambos cuerpos validan contra el esquema `Error` del contrato.

Matriz: docs/pruebas/matriz-pruebas-backend-v1.md (P-01…P-06).
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import jsonschema
import jwt
import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.config import get_settings
from app.data import alerts as alerts_data
from app.data import tips as tips_data
from app.data.database import get_session
from app.data.memberships import ActiveMembershipRow
from app.data.tips import UserTipRow
from app.domain.simulator import TIMEZONE
from app.errors import NOT_FOUND_MESSAGE, UNAUTHORIZED_MESSAGE
from app.main import API_PREFIX, create_app
from app.security.invitation_tokens import hash_invitation_token
from app.services import backend_texts as backend_texts_service
from app.services import consumption as consumption_service
from app.services import members_invitations as members_service
from app.services import thresholds as thresholds_service
from tests.contract.test_c01_responses_match_schema import assert_matches_contract
from tests.helpers.auth import (
    TEST_KEY_ID,
    auth_header,
    install_fake_memberships,
    install_test_jwks,
    make_membership_row,
    make_test_settings,
    make_token,
    override_db_session,
)
from tests.services.consumption_fakes import FakeSession as CountingSession
from tests.services.consumption_fakes import install_fake_consumption_database
from tests.services.members_fakes import FakeMembersDatabase, install_fake_members_database

# --- Contrato -------------------------------------------------------------------------------

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "docs/api/zentheris-api.yaml"
CONTRACT: dict[str, Any] = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
SCHEMAS: dict[str, Any] = CONTRACT["components"]["schemas"]
HTTP_METHODS = ("get", "post", "put", "patch", "delete")


@dataclass(frozen=True)
class Operation:
    """Una operación del contrato, con lo necesario para llamarla."""

    operation_id: str
    method: str
    path: str
    path_params: tuple[str, ...]
    required_query: tuple[tuple[str, dict[str, Any]], ...]
    body_schema: dict[str, Any] | None
    public: bool  # `security: []` en el contrato

    @property
    def has_household(self) -> bool:
        return "hogar_id" in self.path_params


def _resolve_parameter(parameter: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in parameter:
        return CONTRACT["components"]["parameters"][parameter["$ref"].split("/")[-1]]
    return parameter


def load_operations() -> dict[str, Operation]:
    """operationId → operación, leída del YAML del contrato."""
    operations: dict[str, Operation] = {}
    for path, item in CONTRACT["paths"].items():
        for method, op in item.items():
            if method not in HTTP_METHODS:
                continue
            raw = item.get("parameters", []) + op.get("parameters", [])
            params = [_resolve_parameter(p) for p in raw]
            body = op.get("requestBody")
            operations[op["operationId"]] = Operation(
                operation_id=op["operationId"],
                method=method.upper(),
                path=path,
                path_params=tuple(p["name"] for p in params if p["in"] == "path"),
                required_query=tuple(
                    (p["name"], p["schema"])
                    for p in params
                    if p["in"] == "query" and p.get("required")
                ),
                body_schema=body["content"]["application/json"]["schema"] if body else None,
                public=op.get("security", CONTRACT.get("security")) == [],
            )
    return operations


OPERATIONS = load_operations()
HOUSEHOLD_OPERATIONS = sorted(op_id for op_id, op in OPERATIONS.items() if op.has_household)
PROTECTED_OPERATIONS = sorted(op_id for op_id, op in OPERATIONS.items() if not op.public)
BODY_OPERATIONS = sorted(op_id for op_id, op in OPERATIONS.items() if op.body_schema)

# --- Reglas (qué exige cada operación) ------------------------------------------------------

# RN-XVII-01…04: operación → (permiso del hogar, `CodigoError` del 403).
PERMISSION_OPERATIONS: dict[str, tuple[str, str]] = {
    "obtenerConsumoActual": ("ver_consumo_actual", "SIN_PERMISO_VER_CONSUMO"),  # P-02
    "obtenerConsumoZonas": ("ver_consumo_actual", "SIN_PERMISO_VER_CONSUMO"),  # P-02
    "obtenerConsumoZona": ("ver_consumo_actual", "SIN_PERMISO_VER_CONSUMO"),  # P-02
    "obtenerHistorial": ("ver_historial", "SIN_PERMISO_VER_HISTORIAL"),  # P-03
    "listarAlertas": ("recibir_alertas", "SIN_PERMISO_RECIBIR_ALERTAS"),  # RN-XVII-03
    "contarAlertasNoLeidas": ("recibir_alertas", "SIN_PERMISO_RECIBIR_ALERTAS"),
    "marcarAlertasLeidas": ("recibir_alertas", "SIN_PERMISO_RECIBIR_ALERTAS"),
    "crearMeta": ("modificar_metas", "SIN_PERMISO_MODIFICAR_METAS"),  # P-04
}
# RN-X-08 y RN-XVI-05: solo el administrador (P-05).
ADMIN_OPERATIONS: frozenset[str] = frozenset(
    {
        "actualizarPermisos",
        "expulsarMiembro",
        "transferirAdministracion",
        "crearInvitacion",
        "revocarInvitacion",
        "crearTarifa",
    }
)
PERMISSIONS = ("ver_consumo_actual", "ver_historial", "recibir_alertas", "modificar_metas")
# Operaciones con hogar que solo exigen membresía activa (incluye `obtenerFuentesDatos`:
# P-07 oculta valores en el servicio, no responde 403).
MEMBERSHIP_ONLY_OPERATIONS = sorted(
    set(HOUSEHOLD_OPERATIONS) - set(PERMISSION_OPERATIONS) - ADMIN_OPERATIONS
)


def operations_requiring(permission: str) -> list[str]:
    return sorted(op for op, (perm, _) in PERMISSION_OPERATIONS.items() if perm == permission)


def guard_kind(op_id: str) -> str:
    """Tipo de guardia que las reglas piden para la operación."""
    op = OPERATIONS[op_id]
    if op.public:
        return "ninguno"
    if op_id in ADMIN_OPERATIONS:
        return "administrador"
    if op_id in PERMISSION_OPERATIONS:
        return PERMISSION_OPERATIONS[op_id][0]
    return "membresía" if op.has_household else "usuario"


# Una operación por tipo de guardia (la primera en orden alfabético), y si existe, una con
# cuerpo de cada tipo, para la prueba del orden 401 → 404/422.
GUARD_SAMPLE: list[str] = sorted(
    {
        next(op for op in sorted(PROTECTED_OPERATIONS) if guard_kind(op) == kind)
        for kind in {guard_kind(op) for op in PROTECTED_OPERATIONS}
    }
    | {
        next(op for op in BODY_OPERATIONS if guard_kind(op) == kind)
        for kind in {guard_kind(op) for op in BODY_OPERATIONS if not OPERATIONS[op].public}
    }
)

# --- Datos de prueba ------------------------------------------------------------------------

USER_ID = UUID("00000000-0000-4000-8000-0000000000a1")
HOGAR_ID = UUID("00000000-0000-4000-8000-000000000101")
OTHER_HOGAR_ID = UUID("00000000-0000-4000-8000-000000000202")
OTHER_PATH_IDS: dict[str, UUID] = {
    "membresia_id": UUID("00000000-0000-4000-8000-000000000301"),
    "invitacion_id": UUID("00000000-0000-4000-8000-000000000302"),
    "zona_id": UUID("00000000-0000-4000-8000-000000000303"),
    "consejo_id": UUID("00000000-0000-4000-8000-000000000304"),
}
# Clave EC que el JWKS de prueba NO publica: firma tokens «de otra clave».
FOREIGN_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())

# Operaciones con servicio real: la guardia superada da 200 (no el 501 del esqueleto).
IMPLEMENTED_OPERATIONS: frozenset[str] = frozenset(
    {
        "obtenerConsumoActual",
        "obtenerConsumoZonas",
        "obtenerConsumoZona",
        "obtenerHistorial",
        "listarAlertas",
        "contarAlertasNoLeidas",
        "marcarAlertasLeidas",
        "listarConsejos",
        "actualizarEstadoConsejo",
        # Fase 9: miembros e invitaciones (las 4 de /invitaciones no llevan hogar).
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
# Las 11 de la etiqueta «Miembros e invitaciones» del contrato (fase 9).
MEMBERS_OPERATIONS: frozenset[str] = frozenset(
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
# La guardia deja pasar y responde la regla, no la guardia (ver el módulo): (operación, rol).
BUSINESS_ANSWER_AFTER_GUARDS: dict[tuple[str, str], tuple[int, str]] = {
    ("salirDelHogar", "administrador"): (409, "ADMIN_DEBE_TRANSFERIR"),  # RN-X-07
}

ERROR_BODY_KEYS = {"codigo", "mensaje", "detalles"}
UNAUTHORIZED_BODY = {
    "codigo": "NO_AUTENTICADO",
    "mensaje": UNAUTHORIZED_MESSAGE,
    "detalles": None,
}
NOT_FOUND_BODY = {"codigo": "NO_ENCONTRADO", "mensaje": NOT_FOUND_MESSAGE, "detalles": None}

# --- Cuerpos válidos según el contrato ------------------------------------------------------

PATTERN_EXAMPLES = {"^[0-9]{4}-(0[1-9]|1[0-2])$": "2026-11"}
FORMAT_EXAMPLES = {
    "uuid": "00000000-0000-4000-8000-000000000401",
    "email": "invitado@example.com",
    "password": "ClaveSegura1",
}


def _resolve(schema: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = SCHEMAS[schema["$ref"].split("/")[-1]]
    return schema


def example_value(schema: dict[str, Any]) -> Any:
    """Valor mínimo y válido para un esquema del contrato (obligatorios y `minProperties`)."""
    schema = _resolve(schema)
    if "enum" in schema:
        return next(v for v in schema["enum"] if v is not None)
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next(t for t in kind if t != "null")
    if kind == "object":
        properties = schema.get("properties", {})
        names = schema.get("required") or list(properties)[: schema.get("minProperties", 0)]
        return {name: example_value(properties[name]) for name in names}
    if kind == "array":
        count = max(schema.get("minItems", 1), 1)
        items = _resolve(schema["items"])
        if "enum" in items:
            values = [v for v in items["enum"] if v is not None]
            assert len(values) >= count, schema
            return values[:count]
        if items.get("format") == "uuid":
            return [str(UUID(int=0x501 + i)) for i in range(count)]
        assert count == 1 or not schema.get("uniqueItems"), schema
        return [example_value(items)] * count
    if kind == "string":
        if "pattern" in schema:
            return PATTERN_EXAMPLES[schema["pattern"]]
        value = FORMAT_EXAMPLES.get(schema.get("format", ""), "valor de prueba")
        assert len(value) >= schema.get("minLength", 0), schema
        return value
    if kind in ("number", "integer"):
        base = schema.get("minimum", schema.get("exclusiveMinimum", 0))
        return int(base) + 1 if kind == "integer" else float(base) + 1.5
    if kind == "boolean":
        return True
    raise AssertionError(f"Esquema sin ejemplo: {schema}")


def valid_body(op_id: str) -> Any:
    schema = OPERATIONS[op_id].body_schema
    return None if schema is None else example_value(schema)


# --- Cliente --------------------------------------------------------------------------------


def token_headers(kind: str, user_id: UUID = USER_ID) -> dict[str, str]:
    """Cabeceras para cada caso de token: válido, ausente, vencido o firmado con otra clave."""
    if kind == "valido":
        return auth_header(make_token(user_id))
    if kind == "sin_token":
        return {}
    if kind == "vencido":
        return auth_header(make_token(user_id, expired=True))
    if kind == "otra_clave":
        claims = jwt.decode(make_token(user_id), options={"verify_signature": False})
        token = jwt.encode(
            claims, FOREIGN_PRIVATE_KEY, algorithm="ES256", headers={"kid": TEST_KEY_ID}
        )
        return auth_header(token)
    raise ValueError(kind)


INVALID_TOKENS = ("sin_token", "vencido", "otra_clave")
VALID_BODY = object()  # centinela: «manda el cuerpo válido del contrato»

CallApi = Callable[..., httpx.Response]


@pytest.fixture(scope="module")
def e2e_client() -> Iterator[TestClient]:
    """App real con el JWKS de prueba y la sesión falsa; limpia `dependency_overrides`."""
    with pytest.MonkeyPatch.context() as module_patch:
        install_test_jwks(module_patch)
        app = create_app(make_test_settings())
        app.dependency_overrides[get_settings] = make_test_settings
        override_db_session(app)
        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            app.dependency_overrides.clear()


@pytest.fixture
def call_api(e2e_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> CallApi:
    """Llama a una operación del contrato con las membresías dadas.

    `hogar` reemplaza `{hogar_id}` (puede ser un texto inválido); `body=VALID_BODY` manda el
    cuerpo válido del contrato; `token` es uno de `token_headers`.
    """

    def _call(
        op_id: str,
        *,
        rows: list[ActiveMembershipRow],
        token: str = "valido",
        hogar: UUID | str = HOGAR_ID,
        body: Any = VALID_BODY,
        include_required_query: bool = True,
    ) -> httpx.Response:
        install_fake_memberships(monkeypatch, rows)
        if op_id in MEMBERS_OPERATIONS:
            members_db = install_members_data(monkeypatch, rows)

            def members_session() -> Iterator[Any]:
                yield members_db.session()

            monkeypatch.setitem(e2e_client.app.dependency_overrides, get_session, members_session)
        elif op_id in IMPLEMENTED_OPERATIONS:
            install_implemented_operation_data(monkeypatch)
            # Las escrituras de la fase 8 hacen commit: sesión que lo admite (y lo cuenta).
            monkeypatch.setitem(
                e2e_client.app.dependency_overrides, get_session, committing_session
            )
        op = OPERATIONS[op_id]
        values = {
            name: str(hogar) if name == "hogar_id" else str(OTHER_PATH_IDS[name])
            for name in op.path_params
        }
        query = (
            {name: example_value(schema) for name, schema in op.required_query}
            if include_required_query
            else {}
        )
        payload = valid_body(op_id) if body is VALID_BODY else body
        return e2e_client.request(
            op.method,
            API_PREFIX + op.path.format(**values),
            params=query,
            json=payload,
            headers=token_headers(token),
        )

    return _call


def install_implemented_operation_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dobles de `app.data` para las operaciones de consumo (fases 6 y 7), sin base ni `.env`.

    `HOGAR_ID` tiene una zona activa (la de `OTHER_PATH_IDS["zona_id"]`, así el detalle no da
    404) sin lecturas: la respuesta es 200 con «sin datos». La recuperación es un espía.
    """
    fake = install_fake_consumption_database(monkeypatch)
    fake.add_zone(HOGAR_ID, "cocina", "Cocina", zona_id=OTHER_PATH_IDS["zona_id"])
    monkeypatch.setattr(thresholds_service, "get_settings", make_test_settings)
    # Caché propia de la prueba (la de producción no queda con estos umbrales), en el nombre
    # que llama el servicio de consumo.
    fresh = cache(thresholds_service.get_thresholds.__wrapped__)
    monkeypatch.setattr(thresholds_service, "get_thresholds", fresh)
    monkeypatch.setattr(consumption_service, "get_thresholds", fresh)
    install_alert_and_tip_data(monkeypatch)


MEMBER_JOINED_AT = datetime(2026, 11, 1, 12, tzinfo=TIMEZONE)
OTHER_USER_ID = UUID("00000000-0000-4000-8000-0000000000a2")
# `make_token` usa este correo por defecto: la invitación de la ruta es para quien llama.
TOKEN_EMAIL = "persona@example.com"


def install_members_data(
    monkeypatch: pytest.MonkeyPatch, rows: list[ActiveMembershipRow]
) -> FakeMembersDatabase:
    """Doble de `app.data` de la fase 9, coherente con las membresías de la guardia.

    `HOGAR_ID` existe; quien llama tiene ficha y, si `rows` lo dice, su membresía con ese rol; hay
    otro miembro activo con `OTHER_PATH_IDS["membresia_id"]` y una invitación pendiente que vence
    dentro de 7 días con `OTHER_PATH_IDS["invitacion_id"]` (para el correo del token de
    `USER_ID`). El correo de la invitación nueva no es de ningún miembro. Textos del backend de
    `make_test_settings()` (caché propia de la prueba); el envío del correo es un doble.
    """
    db = FakeMembersDatabase()
    db.add_household(HOGAR_ID, "Casa de prueba")
    db.add_user(USER_ID, "Persona de prueba", TOKEN_EMAIL)
    db.add_user(OTHER_USER_ID, "Otra persona", "otra@example.com")
    for row in rows:
        if (row.usuario_id, row.hogar_id) == (USER_ID, HOGAR_ID):
            db.add_membership(
                HOGAR_ID,
                USER_ID,
                row.rol,
                fecha_ingreso=MEMBER_JOINED_AT,
                membresia_id=row.membresia_id,
            )
    db.add_membership(
        HOGAR_ID,
        OTHER_USER_ID,
        "miembro",
        fecha_ingreso=MEMBER_JOINED_AT,
        membresia_id=OTHER_PATH_IDS["membresia_id"],
    )
    db.add_invitation(
        HOGAR_ID,
        TOKEN_EMAIL,
        invitado_por=OTHER_USER_ID,
        expira_en=datetime.now(TIMEZONE) + timedelta(days=7),
        invitacion_id=OTHER_PATH_IDS["invitacion_id"],
        # El token del cuerpo válido de `resolverTokenInvitacion` (solo se guarda su hash).
        token_hash=hash_invitation_token(valid_body("resolverTokenInvitacion")["token"]),
    )
    install_fake_members_database(monkeypatch, db)
    monkeypatch.setattr(backend_texts_service, "get_settings", make_test_settings)
    texts = cache(backend_texts_service.get_backend_texts.__wrapped__)
    monkeypatch.setattr(members_service, "get_backend_texts", texts)
    return db


def committing_session() -> Iterator[CountingSession]:
    yield CountingSession()


def install_alert_and_tip_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dobles mínimos de `data/alerts.py` y `data/tips.py` (fase 8), filtrando por hogar.

    `HOGAR_ID` no tiene alertas; tiene un consejo pendiente con el `consejo_id` de la ruta, así
    `actualizarEstadoConsejo` no da 404. La recuperación de horas ya es un espía.
    """
    tip = UserTipRow(
        id=OTHER_PATH_IDS["consejo_id"],
        categoria="general",
        prioridad="baja",
        titulo="Consejo de prueba",
        descripcion="Descripción de prueba",
        zona_id=None,
        zona_tipo=None,
        estado="pendiente",
        completada_en=None,
        created_at=datetime(2026, 11, 20, tzinfo=TIMEZONE),
    )

    def get_user_tip(_s: object, _u: UUID, hogar_id: UUID, consejo_id: UUID) -> UserTipRow | None:
        return tip if (hogar_id, consejo_id) == (HOGAR_ID, tip.id) else None

    def update_user_tip_status(_s: object, _u: UUID, hogar_id: UUID, consejo_id: UUID,
                               *_args: object) -> bool:
        return (hogar_id, consejo_id) == (HOGAR_ID, tip.id)

    for module, name, value in (
        (alerts_data, "list_user_alerts", lambda *_args: []),
        (alerts_data, "count_unread_alerts", lambda *_args: 0),
        (alerts_data, "mark_alerts_read", lambda *_args: 0),
        (tips_data, "list_user_tips", lambda *_args: []),
        (tips_data, "get_user_tip", get_user_tip),
        (tips_data, "update_user_tip_status", update_user_tip_status),
    ):
        monkeypatch.setattr(module, name, value)


def member(hogar_id: UUID = HOGAR_ID, **permissions: bool) -> ActiveMembershipRow:
    return make_membership_row(USER_ID, hogar_id, rol="miembro", **permissions)


def admin(hogar_id: UUID = HOGAR_ID, **permissions: bool) -> ActiveMembershipRow:
    return make_membership_row(USER_ID, hogar_id, rol="administrador", **permissions)


ALL_TRUE = dict.fromkeys(PERMISSIONS, True)
ALL_FALSE = dict.fromkeys(PERMISSIONS, False)


def success_status(op_id: str) -> int:
    """El único estado 2xx que declara el contrato para la operación (200, 201 o 204)."""
    op = OPERATIONS[op_id]
    responses = CONTRACT["paths"][op.path][op.method.lower()]["responses"]
    (status,) = [int(code) for code in responses if str(code).startswith("2")]
    return status


def assert_passes_guards(response: httpx.Response, op_id: str, rol: str = "miembro") -> None:
    """Los guardias dejaron pasar: el éxito del contrato si el servicio existe (o la respuesta de
    la regla de `BUSINESS_ANSWER_AFTER_GUARDS`); si no existe, su esqueleto (501)."""
    if (op_id, rol) in BUSINESS_ANSWER_AFTER_GUARDS:
        status, codigo = BUSINESS_ANSWER_AFTER_GUARDS[op_id, rol]
        assert response.status_code == status, (op_id, response.status_code, response.text)
        assert response.json()["codigo"] == codigo
        assert_matches_contract(op_id, response)
        return
    if op_id in IMPLEMENTED_OPERATIONS:
        expected = success_status(op_id)
        assert response.status_code == expected, (op_id, response.status_code, response.text)
        assert_matches_contract(op_id, response)
        return
    assert response.status_code == 501, (op_id, response.status_code, response.text)
    assert response.json() == {"detail": f"TODO({op_id})"}


def assert_forbidden(response: httpx.Response, codigo: str) -> None:
    """403 con el `CodigoError` exacto y la forma del esquema `Error` del contrato."""
    assert response.status_code == 403, (response.status_code, response.text)
    body = response.json()
    assert body["codigo"] == codigo
    assert set(body) <= ERROR_BODY_KEYS
    jsonschema.validate(body, {**SCHEMAS["Error"], "components": CONTRACT["components"]})


# --- Coherencia del contrato con las reglas -------------------------------------------------


def test_rules_name_operations_that_exist_in_the_contract() -> None:
    """Las operaciones que nombran las reglas existen, tienen `{hogar_id}` y piden token.

    Esperado: 40 operaciones, 23 con hogar; los códigos del 403 están en `CodigoError`.
    Regla: RN-XVII-01…05, RN-X-08, RN-XVI-05.
    """
    assert len(OPERATIONS) == 40
    assert len(HOUSEHOLD_OPERATIONS) == 23
    assert [op for op in OPERATIONS if OPERATIONS[op].public] == ["obtenerSalud"]
    named = set(PERMISSION_OPERATIONS) | ADMIN_OPERATIONS
    assert named <= set(HOUSEHOLD_OPERATIONS)
    codes = set(SCHEMAS["CodigoError"]["enum"])
    assert {code for _, code in PERMISSION_OPERATIONS.values()} | {"NO_ES_ADMINISTRADOR"} <= codes
    assert {perm for perm, _ in PERMISSION_OPERATIONS.values()} == set(PERMISSIONS)


@pytest.mark.parametrize("op_id", BODY_OPERATIONS)
def test_generated_body_is_valid_per_contract(op_id: str) -> None:
    """El cuerpo que mandan estas pruebas cumple el esquema del contrato.

    Esperado: válido según JSON Schema (con formatos). Así un 403/404 no se confunde con 422.
    """
    schema = {**OPERATIONS[op_id].body_schema, "components": CONTRACT["components"]}
    jsonschema.validate(
        valid_body(op_id), schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )


# --- P-01 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("rol", ["miembro", "administrador"])
@pytest.mark.parametrize("op_id", HOUSEHOLD_OPERATIONS)
def test_p01_member_of_another_household_gets_404(call_api: CallApi, op_id: str, rol: str) -> None:
    """P-01 · Usuario sin membresía en ese hogar (sí en otro, incluso como administrador).

    Esperado: 404 `NO_ENCONTRADO`, nunca 403 ni 501. Regla: RN-I-03.
    """
    rows = [make_membership_row(USER_ID, OTHER_HOGAR_ID, rol=rol, **ALL_TRUE)]
    response = call_api(op_id, rows=rows, hogar=HOGAR_ID)
    assert response.status_code == 404, (response.status_code, response.text)
    # El cuerpo del guardia, no el 404 genérico de FastAPI («Not Found») por ruta mal armada.
    assert response.json() == NOT_FOUND_BODY
    jsonschema.validate(response.json(), {**SCHEMAS["Error"], "components": CONTRACT["components"]})


# --- P-02, P-03, RN-XVII-03 y P-04 ----------------------------------------------------------


def _missing_permission_case(call_api: CallApi, op_id: str) -> None:
    permission, codigo = PERMISSION_OPERATIONS[op_id]
    rows = [member(**{**ALL_TRUE, permission: False})]
    assert_forbidden(call_api(op_id, rows=rows), codigo)


@pytest.mark.parametrize("op_id", operations_requiring("ver_consumo_actual"))
def test_p02_member_without_view_consumption_gets_403(call_api: CallApi, op_id: str) -> None:
    """P-02 · Miembro sin `ver_consumo_actual` (los demás permisos en True).

    Esperado: 403 `SIN_PERMISO_VER_CONSUMO`. Regla: RN-XVII-01.
    """
    _missing_permission_case(call_api, op_id)


def test_p02_data_sources_is_not_blocked_by_view_consumption(call_api: CallApi) -> None:
    """P-02 (límite) · Miembro sin `ver_consumo_actual` pide `obtenerFuentesDatos`.

    Esperado: pasa el guardia (501 del servicio), no 403: P-07 oculta valores en el servicio
    (RN-XVI-06, fase 10; no verificado aquí).
    """
    rows = [member(**{**ALL_TRUE, "ver_consumo_actual": False})]
    assert_passes_guards(call_api("obtenerFuentesDatos", rows=rows), "obtenerFuentesDatos")


@pytest.mark.parametrize("op_id", operations_requiring("ver_historial"))
def test_p03_member_without_view_history_gets_403(call_api: CallApi, op_id: str) -> None:
    """P-03 · Miembro sin `ver_historial`. Esperado: 403 `SIN_PERMISO_VER_HISTORIAL`.

    Regla: RN-XVII-02.
    """
    _missing_permission_case(call_api, op_id)


@pytest.mark.parametrize("op_id", operations_requiring("recibir_alertas"))
def test_member_without_receive_alerts_gets_403(call_api: CallApi, op_id: str) -> None:
    """RN-XVII-03 (sin ID en la matriz) · Miembro sin `recibir_alertas`.

    Esperado: 403 `SIN_PERMISO_RECIBIR_ALERTAS` en listar, contar y marcar leídas.
    """
    _missing_permission_case(call_api, op_id)


@pytest.mark.parametrize("op_id", operations_requiring("modificar_metas"))
def test_p04_member_without_modify_goals_gets_403(call_api: CallApi, op_id: str) -> None:
    """P-04 · Miembro sin `modificar_metas` crea una meta.

    Esperado: 403 `SIN_PERMISO_MODIFICAR_METAS`. Regla: RN-XVII-04.
    """
    _missing_permission_case(call_api, op_id)


@pytest.mark.parametrize("op_id", sorted(PERMISSION_OPERATIONS))
def test_member_with_only_the_required_permission_passes(call_api: CallApi, op_id: str) -> None:
    """P-02/P-03/P-04/RN-XVII-03 (caso positivo) · Miembro con SOLO el permiso que pide.

    Esperado: pasa el guardia (200 si el servicio existe, si no 501 del esqueleto). Para
    `crearMeta`, cierra P-04: con el permiso, un miembro sí llega al servicio.
    Regla: RN-XVII-01…04.
    """
    permission, _ = PERMISSION_OPERATIONS[op_id]
    rows = [member(**{**ALL_FALSE, permission: True})]
    assert_passes_guards(call_api(op_id, rows=rows), op_id)


@pytest.mark.parametrize("op_id", MEMBERSHIP_ONLY_OPERATIONS)
def test_member_without_permissions_passes_membership_only_operations(
    call_api: CallApi, op_id: str
) -> None:
    """Miembro con los 4 permisos en False pide una operación que solo exige membresía.

    Esperado: pasa el guardia (501), nunca 403: ningún permiso de más. Regla: RN-I-03,
    RN-XVII (solo las operaciones de RN-XVII-01…04 exigen permiso).
    """
    assert_passes_guards(call_api(op_id, rows=[member(**ALL_FALSE)]), op_id)


INVITATION_OPERATIONS = sorted(op for op in MEMBERS_OPERATIONS if not OPERATIONS[op].has_household)


@pytest.mark.parametrize("op_id", INVITATION_OPERATIONS)
def test_invitation_operations_need_only_the_token(call_api: CallApi, op_id: str) -> None:
    """Las 4 de `/invitaciones` solo exigen token válido: sin ninguna membresía, éxito del contrato.

    La invitación es para el correo del token (RN-X-05: el servicio compara el correo, no la
    membresía). Regla: RN-X-01, RN-X-05, RN-X-06.
    """
    assert len(INVITATION_OPERATIONS) == 4
    assert {guard_kind(op) for op in INVITATION_OPERATIONS} == {"usuario"}
    assert_passes_guards(call_api(op_id, rows=[]), op_id)


# --- P-05 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("op_id", sorted(ADMIN_OPERATIONS))
def test_p05_member_with_all_permissions_gets_403_on_admin_operations(
    call_api: CallApi, op_id: str
) -> None:
    """P-05 · Miembro con los 4 permisos en True pide una operación del administrador.

    Esperado: 403 `NO_ES_ADMINISTRADOR`. Regla: RN-X-08, RN-XVI-05.
    """
    assert_forbidden(call_api(op_id, rows=[member(**ALL_TRUE)]), "NO_ES_ADMINISTRADOR")


# --- P-06 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("op_id", HOUSEHOLD_OPERATIONS)
def test_p06_admin_without_permissions_passes_every_guard(call_api: CallApi, op_id: str) -> None:
    """P-06 · Administrador con los 4 permisos del hogar en False.

    Esperado: pasa los guardias de todas las operaciones con hogar, nunca 403 ni 404: 200 en
    las ya implementadas (`IMPLEMENTED_OPERATIONS`, el 200 de la matriz); 501 del esqueleto en
    las demás, cuyo 200 queda para cuando exista su servicio. Regla: RN-XVII-05.
    """
    assert_passes_guards(call_api(op_id, rows=[admin(**ALL_FALSE)]), op_id, "administrador")


# --- 401 ------------------------------------------------------------------------------------


@pytest.mark.parametrize("token", INVALID_TOKENS)
@pytest.mark.parametrize("op_id", PROTECTED_OPERATIONS)
def test_invalid_token_gets_401(call_api: CallApi, op_id: str, token: str) -> None:
    """401 · Sin token, token vencido o firmado con una clave que el JWKS no publica.

    El usuario SÍ es administrador del hogar: el rechazo es solo por el token.
    Esperado: 401 `NO_AUTENTICADO` con `WWW-Authenticate: Bearer`. Regla: DC-44.
    """
    response = call_api(op_id, rows=[admin(**ALL_TRUE)], token=token)
    assert response.status_code == 401, (response.status_code, response.text)
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json() == UNAUTHORIZED_BODY
    jsonschema.validate(response.json(), {**SCHEMAS["Error"], "components": CONTRACT["components"]})


def test_public_health_needs_no_token(call_api: CallApi) -> None:
    """`obtenerSalud` es pública (`security: []`). Esperado: 200 sin token."""
    assert call_api("obtenerSalud", rows=[], token="sin_token").status_code == 200


def _invalid_inputs(op_id: str) -> list[tuple[str, dict[str, Any]]]:
    """Entradas que darían 422 si el token fuera válido.

    El cuerpo inválido es JSON bien formado con otra forma (una lista). Un cuerpo que ni
    siquiera es JSON da 422 antes que el 401, porque FastAPI lo lee antes de resolver las
    dependencias (documentado en `app/security/dependencies.py`); ese caso no se prueba aquí.
    """
    op = OPERATIONS[op_id]
    cases: list[tuple[str, dict[str, Any]]] = []
    if op.has_household:
        cases.append(("hogar_id inválido", {"hogar": "no-es-un-uuid"}))
    if op.body_schema:
        cases.append(("cuerpo inválido", {"body": ["no-es-un-objeto"]}))
    if op.required_query:
        cases.append(("falta query obligatoria", {"include_required_query": False}))
    return cases


ORDER_CASES = [
    pytest.param(op_id, label, kwargs, id=f"{op_id}-{label}")
    for op_id in GUARD_SAMPLE
    for label, kwargs in _invalid_inputs(op_id)
]


def test_guard_sample_covers_every_guard_kind() -> None:
    """La muestra del orden 401 → 404/422 incluye una operación de cada tipo de guardia."""
    kinds = {guard_kind(op) for op in PROTECTED_OPERATIONS}
    assert {guard_kind(op) for op in GUARD_SAMPLE} == kinds
    assert kinds == {"usuario", "membresía", "administrador", *PERMISSIONS}


@pytest.mark.parametrize("token", INVALID_TOKENS)
@pytest.mark.parametrize("op_id", [op for op in GUARD_SAMPLE if OPERATIONS[op].has_household])
def test_401_comes_before_404(call_api: CallApi, op_id: str, token: str) -> None:
    """Orden 401 → 404 · Token inválido y sin membresía en el hogar.

    Esperado: 401 (no 404); con token válido, la misma petición da 404. Regla: RN-I-03, DC-44.
    """
    response = call_api(op_id, rows=[], token=token)
    assert response.status_code == 401, (response.status_code, response.text)
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert call_api(op_id, rows=[]).status_code == 404


@pytest.mark.parametrize("token", INVALID_TOKENS)
@pytest.mark.parametrize(("op_id", "label", "kwargs"), ORDER_CASES)
def test_401_comes_before_422(
    call_api: CallApi, op_id: str, label: str, kwargs: dict[str, Any], token: str
) -> None:
    """Orden 401 → 422 · Token inválido y entrada inválida (ruta, cuerpo o query).

    Esperado: 401; con token válido y administrador, la misma entrada da 422 `VALIDACION`
    (prueba que la entrada era de verdad inválida). Regla: DC-44.
    """
    response = call_api(op_id, rows=[], token=token, **kwargs)
    assert response.status_code == 401, (label, response.status_code, response.text)
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    control = call_api(op_id, rows=[admin(**ALL_TRUE)], **kwargs)
    assert control.status_code == 422, (label, control.status_code, control.text)
    assert control.json()["codigo"] == "VALIDACION"
