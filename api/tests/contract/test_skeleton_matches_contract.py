"""Paridad del esqueleto con el contrato (prueba real, no omitida).

Compara el OpenAPI que genera FastAPI con docs/api/zentheris-api.yaml:
operaciones (ruta, método, operationId, etiqueta, parámetros, cuerpo, respuestas y
seguridad) y los 48 esquemas (propiedades, obligatorios, nulos, enum, formatos,
límites y referencias). También comprueba que domain/ no importe FastAPI ni la base.
"""

import ast
import re
from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import API_PREFIX, create_app
from tests.helpers.auth import (
    auth_header,
    install_fake_memberships,
    install_test_jwks,
    make_membership_row,
    make_test_settings,
    make_token,
    override_db_session,
)

API_DIR = Path(__file__).resolve().parents[2]
CONTRACT_PATH = API_DIR.parent / "docs/api/zentheris-api.yaml"
# Componentes con otro nombre en el código.
NAME_MAP = {"ErrorResponse": "Error"}
KEEP = (
    "type",
    "format",
    "enum",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "pattern",
    "additionalProperties",
)


@cache
def contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


@cache
def generated() -> dict[str, Any]:
    return create_app(Settings(_env_file=None)).openapi()


def contract_components() -> dict[str, Any]:
    return contract()["components"]["schemas"]


def nullable_components() -> set[str]:
    return {
        name
        for name, s in contract_components().items()
        if isinstance(s.get("type"), list) and "null" in s["type"]
    }


def canon(schema: dict[str, Any], side: str) -> dict[str, Any]:
    """Forma canónica de un esquema, para comparar contrato y OpenAPI generado."""
    comps = contract_components() if side == "contract" else generated()["components"]["schemas"]
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        mapped = NAME_MAP.get(name, name)
        if mapped in contract_components():
            out = {"$ref": mapped}
            if side == "contract" and mapped in nullable_components():
                out["nullable"] = True
            return out
        return canon(comps[name], side)  # objeto en línea en el contrato
    for key in ("oneOf", "anyOf"):
        if key in schema:
            options = [o for o in schema[key] if o.get("type") != "null"]
            assert len(options) == 1, schema
            out = canon(options[0], side)
            if len(options) < len(schema[key]):
                out["nullable"] = True
            return out
    out: dict[str, Any] = {}
    type_ = schema.get("type")
    if isinstance(type_, list):
        if "null" in type_:
            out["nullable"] = True
        rest = [t for t in type_ if t != "null"]
        type_ = rest[0] if len(rest) == 1 else rest
    if type_ is not None:
        out["type"] = type_
    for key in KEEP[1:]:
        if key in schema:
            out[key] = schema[key]
    if "const" in schema:
        out["enum"] = [schema["const"]]
    if "enum" in out:
        if None in out["enum"]:
            out["nullable"] = True
        out["enum"] = [v for v in out["enum"] if v is not None]
    if "properties" in schema:
        out["properties"] = {k: canon(v, side) for k, v in schema["properties"].items()}
        out["required"] = sorted(schema.get("required", []))
    if "items" in schema:
        out["items"] = canon(schema["items"], side)
    if schema.get("default") is not None:
        out["default"] = schema["default"]
    return out


def contract_operations() -> dict[str, tuple[str, str, dict[str, Any], list[dict[str, Any]]]]:
    params = contract()["components"]["parameters"]
    ops = {}
    for path, item in contract()["paths"].items():
        for method, op in item.items():
            if method == "parameters":
                continue
            raw = item.get("parameters", []) + op.get("parameters", [])
            resolved = [params[p["$ref"].split("/")[-1]] if "$ref" in p else p for p in raw]
            ops[op["operationId"]] = (method, path, op, resolved)
    return ops


def generated_operation(method: str, path: str) -> dict[str, Any]:
    return generated()["paths"][API_PREFIX + path][method]


def contract_response(response: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in response:
        return contract()["components"]["responses"][response["$ref"].split("/")[-1]]
    return response


def response_schema(response: dict[str, Any], side: str) -> dict[str, Any] | None:
    content = response.get("content")
    if not content:
        return None
    return canon(content["application/json"]["schema"], side)


def param_key(p: dict[str, Any], side: str) -> tuple[str, str, bool, str]:
    schema = canon(p["schema"], side)
    if not p.get("required"):
        schema.pop("nullable", None)  # FastAPI escribe los opcionales como «X | null»
    return (p["in"], p["name"], bool(p.get("required")), repr(sorted(schema.items())))


OPERATION_IDS = sorted(contract_operations())


def test_same_forty_operations() -> None:
    expected = {(m, API_PREFIX + p) for m, p, _, _ in contract_operations().values()}
    actual = {(m, p) for p, item in generated()["paths"].items() for m in item}
    assert len(expected) == 40
    assert actual == expected


@pytest.mark.parametrize("operation_id", OPERATION_IDS)
def test_operation_matches_contract(operation_id: str) -> None:
    method, path, op, params = contract_operations()[operation_id]
    gen = generated_operation(method, path)
    assert gen["operationId"] == operation_id
    assert gen["tags"] == op["tags"]
    assert gen["summary"] == op["summary"]
    assert sorted(param_key(p, "gen") for p in gen.get("parameters", [])) == sorted(
        param_key(p, "contract") for p in params
    )
    body = op.get("requestBody")
    gen_body = gen.get("requestBody")
    assert (body is None) == (gen_body is None)
    if body:
        assert gen_body.get("required", False) == body.get("required", False)
        assert response_schema(gen_body, "gen") == response_schema(body, "contract")
    expected_codes = {str(c) for c in op["responses"]}
    gen_codes = set(gen["responses"])
    extra = gen_codes - expected_codes
    # FastAPI documenta un 422 en toda ruta con parámetros o cuerpo; es la única diferencia admitida.
    assert extra <= {"422"}, extra
    if extra:
        assert params or body
    for code in expected_codes:
        assert code in gen_codes, code
        assert response_schema(gen["responses"][code], "gen") == response_schema(
            contract_response(op["responses"][code]), "contract"
        ), code
    effective = op.get("security", contract().get("security", []))
    assert gen.get("security", []) == effective


def test_security_scheme_matches_contract() -> None:
    expected = contract()["components"]["securitySchemes"]["supabaseJwt"]
    actual = generated()["components"]["securitySchemes"]["supabaseJwt"]
    keys = ("type", "scheme", "bearerFormat")
    assert {k: actual.get(k) for k in keys} == {k: expected.get(k) for k in keys}


@pytest.mark.parametrize("name", sorted(contract_components()))
def test_schema_matches_contract(name: str) -> None:
    gen_components = generated()["components"]["schemas"]
    gen_name = next((g for g, c in NAME_MAP.items() if c == name), name)
    assert gen_name in gen_components, f"falta el esquema {name}"
    expected = canon(contract_components()[name], "contract")
    actual = canon(gen_components[gen_name], "gen")
    if name in nullable_components():
        expected.pop("nullable", None)  # el «null» va en cada campo que lo usa
    assert actual == expected


# `minProperties` no entra en `canon` (KEEP): se compara aparte, esquema por esquema.
MIN_PROPERTIES_PENDING = {
    # TODO(actualizarPermisos): falta `minProperties: 1` en el esquema al implementar la operación.
    "PermisosActualizar",
}


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            name,
            marks=pytest.mark.skip(reason="TODO(actualizarPermisos)")
            if name in MIN_PROPERTIES_PENDING
            else (),
        )
        for name, schema in sorted(contract_components().items())
        if "minProperties" in schema
    ],
)
def test_min_properties_matches_contract(name: str) -> None:
    gen_schema = generated()["components"]["schemas"][name]
    assert gen_schema.get("minProperties") == contract_components()[name]["minProperties"]


# `uniqueItems` tampoco entra en `canon`: Pydantic no lo publica ni lo comprueba por su cuenta.
UNIQUE_ITEMS_PENDING = {
    # TODO(marcarAlertasLeidas): falta publicar `uniqueItems` al implementar la operación.
    ("AlertasMarcar", "alerta_ids"),
}


@pytest.mark.parametrize(
    ("name", "field"),
    [
        pytest.param(
            name,
            field,
            marks=pytest.mark.skip(reason="TODO(marcarAlertasLeidas)")
            if (name, field) in UNIQUE_ITEMS_PENDING
            else (),
        )
        for name, schema in sorted(contract_components().items())
        for field, prop in schema.get("properties", {}).items()
        if prop.get("uniqueItems")
    ],
)
def test_unique_items_matches_contract(name: str, field: str) -> None:
    gen_schema = generated()["components"]["schemas"][name]
    assert gen_schema["properties"][field].get("uniqueItems") is True


def test_openapi_has_no_501_and_no_fastapi_validation_schemas() -> None:
    spec = generated()
    codes = {
        code for item in spec["paths"].values() for op in item.values() for code in op["responses"]
    }
    assert "501" not in codes
    assert not {"HTTPValidationError", "ValidationError"} & set(spec["components"]["schemas"])


SAMPLE_ID = "00000000-0000-0000-0000-000000000001"
SAMPLE_USER_ID = UUID("00000000-0000-0000-0000-0000000000aa")


# Operaciones ya implementadas (fase 3 · Usuario; fase 4 · Onboarding; fase 6 · Consumo): no
# responden 501.
IMPLEMENTED_OPERATIONS = frozenset(
    {
        "obtenerUsuarioActual",
        "crearFichaUsuario",
        "actualizarPerfil",
        "eliminarCuenta",
        "guardarAvatar",
        "eliminarAvatar",
        "obtenerPreferencias",
        "actualizarPreferencias",
        "crearHogarOnboarding",
        "obtenerConsumoActual",
        "obtenerConsumoZonas",
        "obtenerConsumoZona",
    }
)


def sample_url(path: str) -> str:
    return API_PREFIX + re.sub(r"\{[^}]+\}", SAMPLE_ID, path)


def test_implemented_operations_exist_in_contract() -> None:
    assert IMPLEMENTED_OPERATIONS <= set(contract_operations())


def test_unimplemented_operations_return_501_with_operation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con token válido y membresía de administrador, los guardias pasan y responde el servicio."""
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_settings] = make_test_settings
    install_test_jwks(monkeypatch)
    override_db_session(app)
    install_fake_memberships(
        monkeypatch,
        [make_membership_row(SAMPLE_USER_ID, UUID(SAMPLE_ID), rol="administrador")],
    )
    client = TestClient(app)
    headers = auth_header(make_token(SAMPLE_USER_ID))
    checked = 0
    for operation_id, (method, path, op, _params) in contract_operations().items():
        if operation_id == "obtenerSalud" or op.get("requestBody") or method != "get":
            continue
        if operation_id in IMPLEMENTED_OPERATIONS:
            continue
        url = sample_url(path)
        if operation_id == "obtenerHistorial":
            url += "?periodo=dia"
        response = client.get(url, headers=headers)
        assert response.status_code == 501, operation_id
        assert response.json() == {"detail": f"TODO({operation_id})"}
        checked += 1
    assert checked > 0


def test_operations_without_token_return_401() -> None:
    """Sin token, toda operación salvo `obtenerSalud` responde 401 antes de validar la entrada.

    Salvo un cuerpo que no es JSON válido: FastAPI lo lee antes de las dependencias y
    responde 422 `VALIDACION` (ver `test_malformed_body_without_token_returns_422`).
    """
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_settings] = make_test_settings
    client = TestClient(app)
    checked = 0
    for operation_id, (method, path, op, _params) in contract_operations().items():
        if operation_id == "obtenerSalud":
            continue
        body = {} if op.get("requestBody") else None
        response = client.request(method.upper(), sample_url(path), json=body)
        assert response.status_code == 401, operation_id
        assert response.headers.get("WWW-Authenticate") == "Bearer", operation_id
        checked += 1
    assert checked == len(contract_operations()) - 1


def test_malformed_body_without_token_returns_422() -> None:
    """Documenta la excepción al 401: un cuerpo que no es JSON se rechaza antes de autenticar."""
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_settings] = make_test_settings
    client = TestClient(app)
    method, path, op, _params = contract_operations()["crearFichaUsuario"]
    assert method == "post" and op.get("requestBody")
    response = client.request(
        method.upper(),
        sample_url(path),
        content=b'{"nombre_completo": ',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["codigo"] == "VALIDACION"
    assert "WWW-Authenticate" not in response.headers


FORBIDDEN_IN_DOMAIN = (
    "fastapi",
    "sqlmodel",
    "sqlalchemy",
    "psycopg2",
    "app.data",
    "app.routers",
    "app.services",
    "app.security",
)


def test_domain_is_pure() -> None:
    for file in (API_DIR / "app/domain").rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert not module.startswith(FORBIDDEN_IN_DOMAIN), f"{file.name} importa {module}"
