"""Comprobaciones de integración del repositorio de Zentheris.

Parte A (PR 3 y 6): las copias de `api/app/config_files/` y el catálogo de la app deben ser
idénticos, byte a byte, a sus originales en `docs/` (PENDIENTES #4 y #5). Se compara el SHA-256.
Parte B (PR 5 y 6): contrato ↔ routers ↔ servicios ↔ app ↔ mapa de integración, sin importar
código: lee el contrato con PyYAML, los routers y servicios con `ast`, las etiquetas
`@operationId` de `app/src/api/*.ts` y la tabla del mapa. Los hooks se agregan en la sesión 9.

Uso: `cd api && uv run python ../scripts/check_integration.py` (la parte B necesita PyYAML).
Termina con código 0 si todo coincide y con código 1 si algo falta o difiere.
"""

import ast
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs/api/zentheris-api-v0.2.5.yaml"
ROUTERS_DIR = ROOT / "api/app/routers"
SERVICES_DIR = ROOT / "api/app/services"
APP_API_DIR = ROOT / "app/src/api"
MAP_FILE = ROOT / "docs/MAPA-DE-INTEGRACION.md"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

CONFIG_COPIES = (
    ("api/app/config_files/umbrales-estado.v1.json", "docs/datos/umbrales-estado.v1.json"),
    ("api/app/config_files/textos-backend.es-CO.json", "docs/textos/textos-backend.es-CO.json"),
    ("app/src/texts/catalogo.es-CO.json", "docs/textos/catalogo.es-CO.json"),
)


def sha256_of(path: Path) -> str:
    """SHA-256 de los bytes del archivo, tal cual están en disco."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_config_copies() -> list[str]:
    """Parte A. Devuelve la lista de problemas; vacía si las copias coinciden."""
    problems = []
    for copy_rel, original_rel in CONFIG_COPIES:
        copy_path, original_path = ROOT / copy_rel, ROOT / original_rel
        missing = [rel for rel, p in ((copy_rel, copy_path), (original_rel, original_path))
                   if not p.is_file()]
        if missing:
            problems.append(f"falta: {', '.join(missing)}")
            continue
        copy_hash, original_hash = sha256_of(copy_path), sha256_of(original_path)
        if copy_hash != original_hash:
            problems.append(
                f"{copy_rel} difiere de {original_rel}\n"
                f"  copia:    {copy_hash}\n"
                f"  original: {original_hash}"
            )
    return problems


def contract_operations() -> dict[str, tuple[str, str]]:
    """operationId → (MÉTODO, ruta) del contrato."""
    import yaml  # solo la parte B lo necesita

    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    ops = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method in HTTP_METHODS:
                ops[op["operationId"]] = (method.upper(), path)
    return ops


def router_operations() -> tuple[dict[str, tuple[str, str, str]], list[str]]:
    """operationId → (MÉTODO, ruta, 'modulo.funcion') leídos de los decoradores."""
    ops, problems = {}, []
    for file in sorted(ROUTERS_DIR.glob("*.py")):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for deco in node.decorator_list:
                if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                        and deco.func.attr in HTTP_METHODS):
                    continue
                path = deco.args[0].value if deco.args else None
                op_id = next((k.value.value for k in deco.keywords if k.arg == "operation_id"), None)
                where = f"{file.stem}.{node.name}"
                if not op_id:
                    problems.append(f"router sin operation_id: {where}")
                    continue
                if op_id in ops:
                    problems.append(f"operation_id repetido en routers: {op_id}")
                ops[op_id] = (deco.func.attr.upper(), path, where)
    return ops, problems


def service_functions() -> set[str]:
    """'modulo.funcion' de todas las funciones de servicios/."""
    names = set()
    for file in SERVICES_DIR.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        names |= {f"{file.stem}.{n.name}" for n in tree.body if isinstance(n, ast.FunctionDef)}
    return names


def app_functions() -> tuple[dict[str, str], list[str]]:
    """operationId → 'modulo.funcion' de app/src/api/*.ts (etiqueta `@operationId`)."""
    ops, problems = {}, []
    pattern = re.compile(r"@operationId (\w+)\s*\*/\s*export function (\w+)")
    for file in sorted(APP_API_DIR.glob("*.ts")):
        for op_id, func in pattern.findall(file.read_text(encoding="utf-8")):
            if op_id in ops:
                problems.append(f"operationId repetido en la app: {op_id}")
            ops[op_id] = f"{file.stem}.{func}"
    return ops, problems


def map_rows() -> dict[str, tuple[str, str, str, str, str]]:
    """operationId → (MÉTODO, ruta, router, servicio, función de la app) de la tabla del mapa."""
    rows = {}
    for line in MAP_FILE.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 9 or not cells[0].isdigit():
            continue
        match = re.fullmatch(r"`(GET|POST|PUT|PATCH|DELETE) (\S+)`", cells[1])
        op_id = cells[2].strip("`")
        if match:
            app_func = cells[8].split("→")[0].strip()
            rows[op_id] = (match.group(1), match.group(2), cells[3], cells[4], app_func)
    return rows


def check_integration_map() -> tuple[list[str], str]:
    """Parte B. Devuelve (problemas, resumen)."""
    problems = []
    contract = contract_operations()
    routers, router_problems = router_operations()
    problems += router_problems
    services = service_functions()
    app, app_problems = app_functions()
    problems += app_problems
    mapa = map_rows()
    for op_id in sorted(set(contract) - set(routers)):
        problems.append(f"falta en routers: {op_id}")
    for op_id in sorted(set(routers) - set(contract)):
        problems.append(f"sobra en routers (no está en el contrato): {op_id}")
    for op_id in sorted(set(contract) - set(app)):
        problems.append(f"falta en la app (app/src/api/): {op_id}")
    for op_id in sorted(set(app) - set(contract)):
        problems.append(f"sobra en la app (no está en el contrato): {op_id}")
    for op_id in sorted(set(contract) - set(mapa)):
        problems.append(f"falta en el mapa: {op_id}")
    for op_id in sorted(set(mapa) - set(contract)):
        problems.append(f"sobra en el mapa (no está en el contrato): {op_id}")
    for op_id, (method, path) in contract.items():
        if op_id in routers:
            r_method, r_path, _ = routers[op_id]
            if (r_method, r_path) != (method, path):
                problems.append(f"{op_id}: el router dice {r_method} {r_path}; "
                                f"el contrato, {method} {path}")
        if op_id in mapa:
            m_method, m_path, m_router, m_service, m_app = mapa[op_id]
            if (m_method, m_path) != (method, path):
                problems.append(f"{op_id}: el mapa dice {m_method} {m_path}; "
                                f"el contrato, {method} {path}")
            if op_id in routers and m_router != routers[op_id][2]:
                problems.append(f"{op_id}: el mapa dice router {m_router}; "
                                f"el código, {routers[op_id][2]}")
            if m_service not in services:
                problems.append(f"{op_id}: el servicio {m_service} del mapa no existe")
            if op_id in app and m_app != app[op_id].split(".")[1]:
                problems.append(f"{op_id}: el mapa dice función de la app {m_app}; "
                                f"el código, {app[op_id]}")
    summary = (f"Contrato {len(contract)} · routers {len(routers)} · app {len(app)} · "
               f"mapa {len(mapa)}")
    return problems, summary


def main() -> int:
    failed = False
    problems = check_config_copies()
    total = len(CONFIG_COPIES)
    if problems:
        failed = True
        print("copias: no coinciden con docs/ · ERROR")
        for problem in problems:
            print(f"- {problem}")
        print("Se editan en docs/ y se vuelven a copiar.")
    else:
        print(f"copias: {total}/{total} iguales a docs/ · OK")

    try:
        problems, summary = check_integration_map()
    except ModuleNotFoundError:
        print("integración: falta PyYAML; ejecuta desde api/ con `uv run` · ERROR")
        return 1
    if problems:
        failed = True
        print(f"{summary} · ERROR")
        for problem in problems:
            print(f"- {problem}")
    else:
        print(f"{summary} · OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
