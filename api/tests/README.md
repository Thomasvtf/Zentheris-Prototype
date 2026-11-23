# tests/

Pruebas de la API con `pytest`. Se corren desde `api/` con `uv run pytest`; no usan una base real ni leen `api/.env` (`conftest.py`).

- **Una carpeta por grupo de la matriz** [`docs/pruebas/matriz-pruebas-backend-v1.md`](../../docs/pruebas/matriz-pruebas-backend-v1.md): `permissions/` (P), `rls/` (R), `zones/` (Z), `backfill/` (B), `thresholds/` (U), `alerts/` (A), `contract/` (C), `integrity/` (I) y `security/` (S).
- **Nombre:** `test_<id>_<caso>.py`; por ejemplo, `permissions/test_p02_no_view_consumption_403.py` para P-02.
- **Pendientes:** los archivos de la matriz que aún no tienen su sesión siguen con `pytest.skip("TODO(<ID>)")`; así cada pendiente se ve y la suite queda en verde. Desde la fase 4 ya son reales Z-01 a Z-04, B-01, B-02 y B-04 (B-03 sigue en skip: necesita Render) y la parte sin base de I-01.
- **Reales desde ya:** `test_health.py`, `test_errors.py`, `test_config.py` y `contract/test_skeleton_matches_contract.py` (paridad del esqueleto con el contrato).
- **Fuera de la matriz** (sin ID propio, por eso no siguen `test_<id>_<caso>.py`):
  - `helpers/`: utilidades compartidas. `personalities.py` (promedios de las 5 personalidades, SHA-256 comprobado) y `auth.py` (JWKS y tokens de prueba en memoria, membresías y sesión falsas).
  - `data/`: SQL generado y mapeo de filas de `app/data/`, con una sesión falsa.
  - `e2e/`: extremo a extremo sobre la app completa (fase 2: P-01 a P-06 y 401 en todas las operaciones del contrato).
  - `security/test_jwt.py`, `permissions/test_permission_guards.py` y `contract/test_route_guards.py`: validación del JWT y guardia exacto de cada operación.
  - `test_personalities_helper.py`: comprueba el helper de personalidades contra el orden de la regla de negocio.
  - `simulator/`: las pruebas portadas del simulador de referencia (E, M, F, K10–K12) y las de las 5 personalidades; `simulator/data/` guarda copias de los datos de la referencia.
  - `zones/test_reference_combinations.py`, `zones/selections.py` y `zones/data/`: K01–K09 (las 2.560 selecciones) contra el CSV y la implementación independiente del Avance 01.
  - `domain/`: lógica pura sin ID propio (por ejemplo, nombres de zona frente al catálogo es-CO).
  - `services/`: casos de uso con datos falsos en memoria (fase 4: onboarding).
  - `test_domain_purity.py`: falla si `app/domain/` importa FastAPI, la base, la configuración o usa reloj, archivos o azar sin semilla.
