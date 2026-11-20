"""Comprueba un cuerpo de error contra el esquema `Error` del contrato (codigo, mensaje, detalles).

Lee `docs/api/zentheris-api.yaml`; no copia el esquema a mano.
"""

from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import yaml

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "docs/api/zentheris-api.yaml"


@cache
def _error_schema() -> dict[str, Any]:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    components = contract["components"]
    return {**components["schemas"]["Error"], "components": components}


def assert_contract_error(body: Any, codigo: str, mensaje: str | None = None) -> None:
    """El cuerpo valida contra `Error`, solo trae sus 3 claves y lleva el `codigo` dado."""
    jsonschema.validate(body, _error_schema())
    assert set(body) == {"codigo", "mensaje", "detalles"}
    assert body["codigo"] == codigo
    if mensaje is not None:
        assert body["mensaje"] == mensaje
