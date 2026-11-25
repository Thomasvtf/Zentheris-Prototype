"""Guardia de cada operación (fase 2 · Seguridad; RN-I-03, RN-X-08, RN-XVII-01…05).

Recorre el árbol de dependencias de cada ruta de `create_app()` y comprueba que cada
`operationId` del contrato tiene EXACTAMENTE el guardia de la tabla: solo
`current_user`, `membership`, `require_admin` o la función de `require_permission(<permiso>)`
(comparada por identidad). Orden de los guardias: 401 → 404 → 403.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from app.config import Settings
from app.main import create_app
from app.security.dependencies import (
    Permission,
    current_user,
    membership,
    require_admin,
    require_permission,
)

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "docs/api/zentheris-api.yaml"
CONTRACT: dict[str, Any] = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
PERMISSIONS: tuple[Permission, ...] = (
    "ver_consumo_actual",
    "ver_historial",
    "recibir_alertas",
    "modificar_metas",
)
GUARD_FUNCTIONS: frozenset[Callable[..., Any]] = frozenset(
    {current_user, membership, require_admin, *(require_permission(p) for p in PERMISSIONS)}
)

NONE = "ninguno"
USER = "current_user"
MEMBER = "membership"
ADMIN = "require_admin"

# Guardia esperado por operación (RN-I-03, RN-X-08, RN-XVII-01…05; seguridad de cada operación
# en el contrato).
EXPECTED_GUARD: dict[str, str] = {
    # Sistema
    "obtenerSalud": NONE,
    # Usuario (10)
    "obtenerUsuarioActual": USER,
    "crearFichaUsuario": USER,
    "actualizarPerfil": USER,
    "eliminarCuenta": USER,
    "guardarAvatar": USER,
    "eliminarAvatar": USER,
    "obtenerPreferencias": USER,
    "actualizarPreferencias": USER,
    "verificarContrasenaActual": USER,
    "cambiarContrasena": USER,
    # Hogares
    "obtenerHogarActual": USER,
    "obtenerHogar": MEMBER,
    "listarZonas": MEMBER,
    # Onboarding
    "crearHogarOnboarding": USER,
    # Miembros e invitaciones
    "listarMiembros": MEMBER,
    "actualizarPermisos": ADMIN,
    "expulsarMiembro": ADMIN,
    "transferirAdministracion": ADMIN,
    "salirDelHogar": MEMBER,
    "crearInvitacion": ADMIN,
    "revocarInvitacion": ADMIN,
    "listarInvitacionesRecibidas": USER,
    "resolverTokenInvitacion": USER,
    "aceptarInvitacion": USER,
    "rechazarInvitacion": USER,
    # Consumo
    "obtenerConsumoActual": "ver_consumo_actual",
    "obtenerConsumoZonas": "ver_consumo_actual",
    "obtenerConsumoZona": "ver_consumo_actual",
    "obtenerHistorial": "ver_historial",
    "obtenerFuentesDatos": MEMBER,  # P-07 (valores ocultos) es del servicio
    # Metas y tarifa
    "obtenerMeta": MEMBER,
    "crearMeta": "modificar_metas",
    "obtenerTarifa": MEMBER,
    "crearTarifa": ADMIN,
    # Alertas y consejos
    "listarAlertas": "recibir_alertas",
    "contarAlertasNoLeidas": "recibir_alertas",
    "marcarAlertasLeidas": "recibir_alertas",  # decisión de la persona (fase 2)
    "listarConsejos": MEMBER,
    "actualizarEstadoConsejo": MEMBER,
}


def expected_guards(guard: str) -> frozenset[Callable[..., Any]]:
    """Guardias que deben aparecer en el árbol: el de la tabla y los que este arrastra."""
    if guard == NONE:
        return frozenset()
    if guard == USER:
        return frozenset({current_user})
    if guard == MEMBER:
        return frozenset({current_user, membership})
    if guard == ADMIN:
        return frozenset({current_user, membership, require_admin})
    return frozenset({current_user, membership, require_permission(guard)})  # type: ignore[arg-type]


def guards_in(dependant: Dependant) -> set[Callable[..., Any]]:
    """Funciones de guardia en todo el árbol de dependencias (recursivo)."""
    found: set[Callable[..., Any]] = set()
    for sub in dependant.dependencies:
        if sub.call in GUARD_FUNCTIONS:
            found.add(sub.call)
        found |= guards_in(sub)
    return found


def contract_operation_ids() -> set[str]:
    return {
        op["operationId"]
        for item in CONTRACT["paths"].values()
        for method, op in item.items()
        if method in HTTP_METHODS
    }


def contract_response_codes() -> dict[str, set[str]]:
    """operationId → códigos de respuesta declarados en el contrato."""
    return {
        op["operationId"]: {str(code) for code in op.get("responses", {})}
        for item in CONTRACT["paths"].values()
        for method, op in item.items()
        if method in HTTP_METHODS
    }


def app_dependants() -> dict[str, Dependant]:
    """operationId → árbol de dependencias efectivo de la ruta.

    Desde FastAPI 0.141, `app.routes` guarda cada `include_router` como un nodo perezoso;
    `iter_route_contexts` (el mismo recorrido que usa el OpenAPI) da cada ruta con su
    `dependant` efectivo, que ya incluye las dependencias del router y del prefijo.
    """
    contexts = [
        ctx
        for ctx in iter_route_contexts(create_app(Settings(_env_file=None)).routes)
        if isinstance(ctx.original_route, APIRoute)
    ]
    by_id = {ctx.original_route.operation_id: ctx.dependant for ctx in contexts}
    assert None not in by_id, "hay rutas sin operation_id"
    assert len(by_id) == len(contexts), "hay operation_id repetidos"
    return by_id


ROUTES = app_dependants()
CONTRACT_RESPONSE_CODES = contract_response_codes()


def test_table_covers_every_contract_operation() -> None:
    contract_ids = contract_operation_ids()
    assert len(contract_ids) == 40
    assert set(EXPECTED_GUARD) == contract_ids
    assert set(ROUTES) == contract_ids
    for guard in EXPECTED_GUARD.values():
        assert guard in {NONE, USER, MEMBER, ADMIN, *PERMISSIONS}, guard


def test_require_permission_returns_the_same_function_per_permission() -> None:
    for permission in PERMISSIONS:
        assert require_permission(permission) is require_permission(permission)
    assert len({require_permission(p) for p in PERMISSIONS}) == len(PERMISSIONS)


@pytest.mark.parametrize("operation_id", sorted(EXPECTED_GUARD))
def test_operation_has_exactly_its_guard(operation_id: str) -> None:
    guard = EXPECTED_GUARD[operation_id]
    assert guards_in(ROUTES[operation_id]) == expected_guards(guard), guard


DENYING_GUARDS = {ADMIN, *PERMISSIONS}


@pytest.mark.parametrize(
    "operation_id", sorted(op for op, guard in EXPECTED_GUARD.items() if guard in DENYING_GUARDS)
)
def test_denying_guard_requires_403_in_contract(operation_id: str) -> None:
    """Un guardia que puede negar (administrador o permiso) exige el 403 en el contrato.

    La inversa no aplica: resolver, aceptar y rechazar invitación declaran 403 por
    `CORREO_NO_COINCIDE`, que lo decide el servicio y no un guardia.
    """
    assert "403" in CONTRACT_RESPONSE_CODES[operation_id], EXPECTED_GUARD[operation_id]
