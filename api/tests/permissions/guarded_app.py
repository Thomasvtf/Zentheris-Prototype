"""App FastAPI mínima con los guardias de seguridad, para probar P-01…P-06 por dependencia.

Las rutas imitan las del contrato, pero solo devuelven la membresía resuelta: lo que se
prueba es el guardia (401 → 404 → 403), no el servicio.
"""

from collections.abc import Callable
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI

from app.config import get_settings
from app.data.memberships import ActiveMembershipRow
from app.errors import ERROR_DESCRIPTIONS, register_error_handlers
from app.security.dependencies import (
    AdminMembership,
    CurrentMembership,
    Membership,
    require_permission,
)
from tests.helpers.auth import (
    ADMIN_ID,
    HOGAR_ID,
    MEMBER_ID,
    OTHER_HOGAR_ID,
    OUTSIDER_ID,
    make_membership_row,
    make_test_settings,
    override_db_session,
)

# Los ids viven en tests/helpers/auth.py; se re-exportan aquí para quien ya los importe.
__all__ = [
    "ADMIN_ID",
    "ADMIN_ROUTES",
    "ALL_ROUTES",
    "FORBIDDEN_MESSAGE",
    "HOGAR_ID",
    "MEMBER_ID",
    "MEMBER_ROUTES",
    "OTHER_HOGAR_ID",
    "OUTSIDER_ID",
    "PERMISSION_ROUTES",
    "CallRoute",
    "admin_row",
    "build_guarded_app",
    "member_row",
]


# (método, ruta relativa a /hogares/{hogar_id}) por guardia.
MEMBER_ROUTES = [("GET", "/miembros")]
PERMISSION_ROUTES = {
    "ver_consumo_actual": ("GET", "/consumo/actual"),
    "ver_historial": ("GET", "/historial"),
    "recibir_alertas": ("GET", "/alertas"),
    "modificar_metas": ("POST", "/metas"),
}
ADMIN_ROUTES = [("POST", "/tarifas"), ("POST", "/invitaciones"), ("PATCH", "/permisos")]
ALL_ROUTES = [*MEMBER_ROUTES, *PERMISSION_ROUTES.values(), *ADMIN_ROUTES]

FORBIDDEN_MESSAGE = ERROR_DESCRIPTIONS[403]

# Firma de la fixture `call` (conftest.py).
CallRoute = Callable[..., httpx.Response]


def _member_body(member: Membership) -> dict[str, str]:
    return {"membresia_id": str(member.membresia_id), "rol": member.rol}


def build_guarded_app() -> FastAPI:
    """App con una ruta por guardia: `CurrentMembership`, `require_permission` y admin."""
    app = FastAPI()
    register_error_handlers(app)
    base = "/hogares/{hogar_id}"

    @app.get(base + "/miembros")
    def any_member(member: CurrentMembership) -> dict[str, str]:
        return _member_body(member)

    for permission, (method, path) in PERMISSION_ROUTES.items():

        guard = require_permission(permission)

        def guarded(member: Annotated[Membership, Depends(guard)]) -> dict[str, str]:
            return _member_body(member)

        app.add_api_route(base + path, guarded, methods=[method], name=f"prueba_{permission}")

    for method, path in ADMIN_ROUTES:

        def admin_only(member: AdminMembership) -> dict[str, str]:
            return _member_body(member)

        app.add_api_route(base + path, admin_only, methods=[method], name=f"prueba_admin{path}")

    app.dependency_overrides[get_settings] = make_test_settings
    override_db_session(app)
    return app


def admin_row(**permissions: bool) -> ActiveMembershipRow:
    """Administrador de `HOGAR_ID` con los permisos indicados (el resto, por defecto)."""
    return make_membership_row(ADMIN_ID, HOGAR_ID, rol="administrador", **permissions)


def member_row(**permissions: bool) -> ActiveMembershipRow:
    """Miembro de `HOGAR_ID` con los permisos indicados (el resto, por defecto)."""
    return make_membership_row(MEMBER_ID, HOGAR_ID, **permissions)
