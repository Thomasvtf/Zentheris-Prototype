"""App FastAPI mínima con los guardias de seguridad, para probar P-01…P-06 por dependencia.

Las rutas imitan las del contrato, pero solo devuelven la membresía resuelta: lo que se
prueba es el guardia (401 → 404 → 403), no el servicio.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

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
from tests.helpers.auth import make_membership_row, make_test_settings, override_db_session

HOGAR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_HOGAR_ID = UUID("22222222-2222-4222-8222-222222222222")
ADMIN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MEMBER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
OUTSIDER_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")

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
