"""P-04 · Permisos: Miembro sin permiso de metas crea una meta.

Esperado: 403 `SIN_PERMISO_MODIFICAR_METAS`. Regla: RN-XVII-04.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

A nivel de dependencia: `require_permission("modificar_metas")`. El permiso de metas está
desactivado por defecto (`make_membership_row`), como en `hogares`.
"""

from tests.permissions.guarded_app import FORBIDDEN_MESSAGE, MEMBER_ID, CallRoute, member_row


def test_member_without_modify_goals_gets_403(call: CallRoute) -> None:
    response = call("POST", "/metas", user_id=MEMBER_ID, rows=[member_row()])
    assert response.status_code == 403
    assert response.json() == {
        "codigo": "SIN_PERMISO_MODIFICAR_METAS",
        "mensaje": FORBIDDEN_MESSAGE,
        "detalles": None,
    }


def test_member_with_modify_goals_passes(call: CallRoute) -> None:
    response = call("POST", "/metas", user_id=MEMBER_ID, rows=[member_row(modificar_metas=True)])
    assert response.status_code == 200
