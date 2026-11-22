# security/

Autenticación y autorización. `jwt.py` valida el token de Supabase por JWKS (DC-44). `dependencies.py` tiene las dependencias de FastAPI: `current_user`, `membership`, `require_permission` y `require_admin`.

- **Va:** validación del token, membresía activa (404 si no existe, RN-I-03) y permisos (403 con el `CodigoError` exacto, RN-XVII).
- **No va:** reglas de negocio ni consultas que no sean de membresía o permisos (la consulta vive en `data/memberships.py`).
- **Ejemplo:** `def get_history(hogar_id: UUID, member: Annotated[Membership, Depends(require_permission("ver_historial"))], …)`.

Guardias, en este orden: `CurrentUser` (401) → `CurrentMembership` (404) → `require_permission(...)` o `AdminMembership` (403). El administrador pasa todos los permisos (RN-XVII-05).

- JWKS (`SUPABASE_JWKS_URL`): solo `ES256`/`RS256`, emisor `SUPABASE_URL/auth/v1`, audiencia `authenticated`. Sin JWKS, HS256 con `SUPABASE_JWT_SECRET`. Nunca `alg=none`.
- 401 `NO_AUTENTICADO` (con `WWW-Authenticate: Bearer`), 404 `NO_ENCONTRADO` (sin membresía) y 500 `ERROR_INTERNO` (manejador genérico de `app/errors.py`, sin exponer la excepción).
- Pruebas: `tests/permissions/` (P-01…P-06), `tests/security/` (JWT y S-01) y el helper `tests/helpers/auth.py`.
