# tests/

Pruebas de la API con `pytest`. Se corren desde `api/` con `uv run pytest`; no usan una base real ni leen `api/.env` (`conftest.py`).

- **Una carpeta por grupo de la matriz** [`docs/pruebas/matriz-pruebas-backend-v1.md`](../../docs/pruebas/matriz-pruebas-backend-v1.md): `permissions/` (P), `rls/` (R), `zones/` (Z), `backfill/` (B), `thresholds/` (U), `alerts/` (A), `contract/` (C), `integrity/` (I) y `security/` (S).
- **Nombre:** `test_<id>_<caso>.py`; por ejemplo, `permissions/test_p02_no_view_consumption_403.py` para P-02.
- **Pendientes:** los 35 archivos de la matriz tienen `pytest.skip("TODO(<ID>)")` hasta su sesión; así cada pendiente se ve y la suite queda en verde.
- **Reales desde ya:** `test_health.py`, `test_errors.py`, `test_config.py` y `contract/test_skeleton_matches_contract.py` (paridad del esqueleto con el contrato).
