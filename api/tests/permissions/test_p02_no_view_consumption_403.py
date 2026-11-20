"""P-02 · Permisos: Miembro sin `ver_consumo_actual` pide `consumo/actual`.

Esperado: 403 `SIN_PERMISO_VER_CONSUMO`. Regla: RN-XVII-01.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

A nivel de dependencia: `require_permission("ver_consumo_actual")`.
"""

from tests.permissions.guarded_app import FORBIDDEN_MESSAGE, MEMBER_ID, CallRoute, member_row


def test_member_without_view_consumption_gets_403(call: CallRoute) -> None:
    response = call(
        "GET", "/consumo/actual", user_id=MEMBER_ID, rows=[member_row(ver_consumo_actual=False)]
    )
    assert response.status_code == 403
    assert response.json() == {
        "codigo": "SIN_PERMISO_VER_CONSUMO",
        "mensaje": FORBIDDEN_MESSAGE,
        "detalles": None,
    }


def test_member_with_view_consumption_passes(call: CallRoute) -> None:
    row = member_row(ver_consumo_actual=True)
    response = call("GET", "/consumo/actual", user_id=MEMBER_ID, rows=[row])
    assert response.status_code == 200
    assert response.json() == {"membresia_id": str(row.membresia_id), "rol": "miembro"}


def test_other_permissions_do_not_replace_view_consumption(call: CallRoute) -> None:
    row = member_row(
        ver_consumo_actual=False, ver_historial=True, recibir_alertas=True, modificar_metas=True
    )
    response = call("GET", "/consumo/actual", user_id=MEMBER_ID, rows=[row])
    assert response.status_code == 403
    assert response.json()["codigo"] == "SIN_PERMISO_VER_CONSUMO"
