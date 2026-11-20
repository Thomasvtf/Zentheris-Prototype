"""P-05 · Permisos: Miembro crea una tarifa, invita o mueve permisos.

Esperado: 403 `NO_ES_ADMINISTRADOR`. Regla: RN-X-08, XVI-05.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

A nivel de dependencia: `AdminMembership` (`require_admin`). Ningún permiso del hogar
convierte a un miembro en administrador.
"""

import pytest

from tests.permissions.guarded_app import (
    ADMIN_ID,
    ADMIN_ROUTES,
    FORBIDDEN_MESSAGE,
    MEMBER_ID,
    CallRoute,
    admin_row,
    member_row,
)

ALL_PERMISSIONS_ON = {
    "ver_consumo_actual": True,
    "ver_historial": True,
    "recibir_alertas": True,
    "modificar_metas": True,
}


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_member_gets_403_no_es_administrador(call: CallRoute, method: str, path: str) -> None:
    rows = [member_row(**ALL_PERMISSIONS_ON), admin_row()]
    response = call(method, path, user_id=MEMBER_ID, rows=rows)
    assert response.status_code == 403
    assert response.json() == {
        "codigo": "NO_ES_ADMINISTRADOR",
        "mensaje": FORBIDDEN_MESSAGE,
        "detalles": None,
    }


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_passes_admin_guard(call: CallRoute, method: str, path: str) -> None:
    row = admin_row()
    response = call(method, path, user_id=ADMIN_ID, rows=[row])
    assert response.status_code == 200
    assert response.json() == {"membresia_id": str(row.membresia_id), "rol": "administrador"}
