# security/

Autenticación y autorización. `jwt.py` valida el token de Supabase por JWKS (DC-44). `dependencies.py` tiene las dependencias de FastAPI: `current_user`, `membership`, `require_permission` y `require_admin`.

- **Va:** validación del token, membresía activa (404 si no existe, RN-I-03) y permisos (403 con el `CodigoError` exacto, RN-XVII).
- **No va:** reglas de negocio ni consultas que no sean de membresía o permisos.
- **Ejemplo:** `def get_history(hogar_id: UUID, user: CurrentUser, …)`.

Estado: esqueleto. Se implementa en la sesión 3, después de decidir los códigos del 500 y del 401 (PENDIENTES #29).
