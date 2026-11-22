"""I-04 · Integridad: Eliminar la cuenta de un miembro (no único).

Esperado: Membresía inactiva con usuario nulo; datos del hogar intactos. Regla: DC-36.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md."""

import pytest

pytest.skip(
    "TODO(I-04): requiere Postgres de prueba; la lógica está cubierta con datos falsos "
    "en tests/services y tests/e2e",
    allow_module_level=True,
)
