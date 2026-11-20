"""P-06 · Permisos: El administrador sin permisos activados ve todo.

Esperado: 200. Regla: RN-XVII-05.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

A nivel de dependencia: un administrador con los 4 permisos del hogar en False pasa
todos los guardias (`CurrentMembership`, `require_permission(...)` y `AdminMembership`).
"""

import pytest

from tests.permissions.guarded_app import ADMIN_ID, ALL_ROUTES, CallRoute, admin_row

ALL_PERMISSIONS_OFF = {
    "ver_consumo_actual": False,
    "ver_historial": False,
    "recibir_alertas": False,
    "modificar_metas": False,
}


@pytest.mark.parametrize(("method", "path"), ALL_ROUTES)
def test_admin_without_permissions_passes_every_guard(
    call: CallRoute, method: str, path: str
) -> None:
    row = admin_row(**ALL_PERMISSIONS_OFF)
    response = call(method, path, user_id=ADMIN_ID, rows=[row])
    assert response.status_code == 200
    assert response.json() == {"membresia_id": str(row.membresia_id), "rol": "administrador"}
