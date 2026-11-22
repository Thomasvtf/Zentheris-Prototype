"""P-01 · Permisos: Usuario sin membresía consulta un hogar ajeno.

Esperado: 404. Regla: RN-I-03.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

A nivel de dependencia: todo guardia que recibe `hogar_id` (`CurrentMembership`,
`require_permission(...)` y `AdminMembership`) responde 404, nunca 403, si el usuario no
tiene membresía activa en ese hogar. El cuerpo es `NO_ENCONTRADO` y valida contra el esquema
`Error` del contrato; el 401 (sin token) es `NO_AUTENTICADO` con `WWW-Authenticate: Bearer`.
"""

import pytest

from app.errors import NOT_FOUND_MESSAGE, UNAUTHORIZED_MESSAGE
from tests.permissions.guarded_app import (
    ADMIN_ID,
    ALL_ROUTES,
    MEMBER_ID,
    OTHER_HOGAR_ID,
    OUTSIDER_ID,
    CallRoute,
    admin_row,
    member_row,
)
from tests.security.error_schema import assert_contract_error

NOT_FOUND_BODY = {"codigo": "NO_ENCONTRADO", "mensaje": NOT_FOUND_MESSAGE, "detalles": None}
UNAUTHORIZED_BODY = {
    "codigo": "NO_AUTENTICADO",
    "mensaje": UNAUTHORIZED_MESSAGE,
    "detalles": None,
}


@pytest.mark.parametrize(("method", "path"), ALL_ROUTES)
def test_user_without_membership_gets_404(call: CallRoute, method: str, path: str) -> None:
    response = call(method, path, user_id=OUTSIDER_ID, rows=[admin_row(), member_row()])
    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert_contract_error(response.json(), "NO_ENCONTRADO")


@pytest.mark.parametrize(("method", "path"), ALL_ROUTES)
def test_member_of_another_household_gets_404(call: CallRoute, method: str, path: str) -> None:
    # Tiene membresía activa en HOGAR_ID, pero pide OTHER_HOGAR_ID (hogar ajeno).
    rows = [admin_row(), member_row()]
    for user_id in (ADMIN_ID, MEMBER_ID):
        response = call(method, path, user_id=user_id, rows=rows, hogar_id=OTHER_HOGAR_ID)
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY
        assert_contract_error(response.json(), "NO_ENCONTRADO")


def test_missing_membership_wins_over_missing_permission(call: CallRoute) -> None:
    # Orden 404 → 403: sin membresía no se revela si existiría el permiso.
    rows = [member_row(ver_consumo_actual=False, modificar_metas=False)]
    for method, path in (("GET", "/consumo/actual"), ("POST", "/metas"), ("POST", "/tarifas")):
        response = call(method, path, user_id=MEMBER_ID, rows=rows, hogar_id=OTHER_HOGAR_ID)
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY


@pytest.mark.parametrize(("method", "path"), ALL_ROUTES)
def test_missing_token_wins_over_missing_membership(
    call: CallRoute, method: str, path: str
) -> None:
    # Orden 401 → 404: sin token no se consulta la membresía.
    response = call(method, path, user_id=OUTSIDER_ID, rows=[], token="")
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY
    assert_contract_error(response.json(), "NO_AUTENTICADO")
    assert response.headers["WWW-Authenticate"] == "Bearer"
