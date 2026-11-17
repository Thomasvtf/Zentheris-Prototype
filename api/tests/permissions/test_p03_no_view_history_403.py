"""P-03 · Permisos: Miembro sin `ver_historial` pide `historial`.

Esperado: 403 `SIN_PERMISO_VER_HISTORIAL`. Regla: RN-XVII-02.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

A nivel de dependencia: `require_permission("ver_historial")`.
"""

from tests.permissions.guarded_app import FORBIDDEN_MESSAGE, MEMBER_ID, CallRoute, member_row


def test_member_without_view_history_gets_403(call: CallRoute) -> None:
    response = call("GET", "/historial", user_id=MEMBER_ID, rows=[member_row(ver_historial=False)])
    assert response.status_code == 403
    assert response.json() == {
        "codigo": "SIN_PERMISO_VER_HISTORIAL",
        "mensaje": FORBIDDEN_MESSAGE,
        "detalles": None,
    }


def test_member_with_view_history_passes(call: CallRoute) -> None:
    response = call("GET", "/historial", user_id=MEMBER_ID, rows=[member_row(ver_historial=True)])
    assert response.status_code == 200


def test_view_consumption_does_not_grant_history(call: CallRoute) -> None:
    row = member_row(ver_consumo_actual=True, ver_historial=False)
    response = call("GET", "/historial", user_id=MEMBER_ID, rows=[row])
    assert response.status_code == 403
    assert response.json()["codigo"] == "SIN_PERMISO_VER_HISTORIAL"
