# data/

Acceso a datos: un archivo por grupo de tablas, más `database.py` (conexión) y `readings.py` (inserción por lotes).

- **Va:** consultas e inserciones, con parámetros; inserción por lotes para el backfill (COPY o INSERT de varias filas).
- **No va:** reglas de negocio ni cambios de esquema (esos van en `supabase/migrations/`).
- **Ejemplo:** `insert_readings_batch(session, lecturas) -> int`.

- `supabase_admin.py`: llamadas síncronas (httpx) a Supabase Auth y Storage con la clave de servicio (eliminar cuenta y avatares). Nunca registra la clave ni el cuerpo de la respuesta.

Estado: `memberships.py`, `users.py`, `households.py` (bloqueo y borrado del hogar) y `supabase_admin.py` tienen consultas; el resto se escribe en la sesión de cada endpoint.
