"""Pureza del dominio: `app/domain/` (incluido `simulator/`) no usa web, base, archivos ni reloj.

Recorre con `ast` todos los `.py` (api/CLAUDE.md, DC-56 y `app/domain/README.md`). De `app` solo
se puede importar `app.domain`: la dependencia va de los servicios al dominio, nunca al revés.
"""

import ast
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[1]
DOMAIN_DIR = API_DIR / "app" / "domain"

FORBIDDEN_MODULES = (
    "fastapi",
    "starlette",
    "sqlmodel",
    "sqlalchemy",
    "psycopg2",
    "app.data",
    "app.services",
    "app.routers",
    "app.config",
    # Red y log: el dominio devuelve valores; quien llama decide qué registrar.
    "httpx",
    "requests",
    "socket",
    "logging",
)
# Llamadas con efectos: archivos, entorno, reloj y azar. La hora y los textos entran por
# parámetro; el azar solo con `random.Random(semilla)` (semilla SHA-256 por hogar y fecha).
FORBIDDEN_FILE_CALLS = {"open", "read_text", "read_bytes", "write_text", "write_bytes"}
FORBIDDEN_CLOCK_CALLS = {"now", "utcnow", "today"}
FORBIDDEN_ATTRIBUTES = {
    "os.environ",
    "os.getenv",
    "time.time",
    "time.time_ns",
    "time.perf_counter",
    "time.perf_counter_ns",
    "time.monotonic",
    "time.monotonic_ns",
    "uuid.uuid1",
    "uuid.uuid4",
}
ALLOWED_RANDOM = "random.Random"


def _is_forbidden_attribute(name: str) -> bool:
    """`random.<x>` usa el generador global sin semilla; solo se permite `random.Random`."""
    if name in FORBIDDEN_ATTRIBUTES:
        return True
    return name.startswith("random.") and name != ALLOWED_RANDOM


def _matches(name: str, module: str) -> bool:
    return name == module or name.startswith(f"{module}.")


def _is_forbidden_import(name: str) -> bool:
    if any(_matches(name, module) for module in FORBIDDEN_MODULES):
        return True
    return name.startswith("app.") and not _matches(name, "app.domain")


def _imported_names(node: ast.AST, package: str) -> list[str]:
    """Nombres absolutos que importa un nodo; resuelve los imports relativos con `package`."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        base = node.module or ""
        if node.level:
            parent = package.split(".")[: len(package.split(".")) - (node.level - 1)]
            base = ".".join([*parent, base] if base else parent)
        # `from app import config` importa el módulo `app.config`.
        return [base, *(f"{base}.{alias.name}" for alias in node.names)]
    return []


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def find_violations(source: str, package: str) -> list[str]:
    """Imports y llamadas prohibidas en un módulo del dominio, con su línea."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        for name in _imported_names(node, package):
            if _is_forbidden_import(name):
                violations.append(f"{node.lineno}: import {name}")
            elif _is_forbidden_attribute(name):
                violations.append(f"{node.lineno}: {name}")
        if isinstance(node, ast.Attribute) and _is_forbidden_attribute(_dotted(node)):
            violations.append(f"{node.lineno}: {_dotted(node)}")
        if isinstance(node, ast.Call):
            function = _dotted(node.func).rpartition(".")[2]
            is_method = isinstance(node.func, ast.Attribute)
            is_clock = is_method and function in FORBIDDEN_CLOCK_CALLS
            if is_clock or function in FORBIDDEN_FILE_CALLS:
                violations.append(f"{node.lineno}: {function}()")
    return violations


def _package_of(path: Path) -> str:
    return ".".join(path.relative_to(API_DIR).parent.parts)


DOMAIN_FILES = sorted(DOMAIN_DIR.rglob("*.py"))


def test_domain_files_are_found() -> None:
    found = {path.relative_to(DOMAIN_DIR).as_posix() for path in DOMAIN_FILES}
    assert {"zone_rules.py", "formats.py", "states.py", "simulator/__init__.py"} <= found


@pytest.mark.parametrize(
    "path", DOMAIN_FILES, ids=lambda path: path.relative_to(DOMAIN_DIR).as_posix()
)
def test_domain_is_pure(path: Path) -> None:
    assert find_violations(path.read_text(encoding="utf-8"), _package_of(path)) == []


@pytest.mark.parametrize(
    "source",
    [
        *(f"import {module}" for module in FORBIDDEN_MODULES),
        *(f"from {module} import algo" for module in FORBIDDEN_MODULES),
        "import sqlalchemy.orm as orm",
        "from app import config",
        "from app.errors import CodigoError",
        "from app.schemas.common import TipoZona",
        "from ..data import readings",
        "from .. import services",
        "from ...data.readings import insert_readings_batch",
        "def f():\n    import fastapi",
        "open('x')",
        "Path('x').read_text()",
        "datetime.now()",
        "datetime.datetime.now(tz)",
        "date.today()",
        "import os\nos.environ['X']",
        "from os import environ",
        "os.getenv('X')",
        "time.time()",
        "time.perf_counter()",
        "time.monotonic()",
        "from time import perf_counter",
        "random.random()",
        "random.seed(1)",
        "random.choice([1, 2])",
        "random.SystemRandom()",
        "from random import random",
        "from random import shuffle",
        "uuid.uuid4()",
        "uuid.uuid1()",
        "from uuid import uuid4",
        "import httpx",
        "import requests",
        "import socket",
        "import logging",
        "from logging import getLogger",
    ],
)
def test_detector_finds_violations(source: str) -> None:
    """El detector no pasa en verde por no mirar: cada ejemplo prohibido se reporta."""
    package = "app.domain.simulator" if "..." in source else "app.domain"
    assert find_violations(source, package) != []


@pytest.mark.parametrize(
    "source",
    [
        "from app.domain.zone_rules import ZONE_TYPES",
        "from . import constants",
        "from .seeds import uniforms",
        "from ..zone_rules import ZONE_TYPES",
        "from datetime import datetime\ndef f(now: datetime): return now.date()",
        "import application.data",
        "import fastapi_like",
        "import random\nrng = random.Random(42)\nvalue = rng.random()",
        "from random import Random\nRandom(1).random()",
        "from uuid import UUID\nUUID(int=1)",
        "import uuid\nuuid.uuid5(uuid.NAMESPACE_URL, 'x')",
        "import time",
        "import loggingx",
    ],
)
def test_detector_accepts_pure_code(source: str) -> None:
    assert find_violations(source, "app.domain.simulator") == []
