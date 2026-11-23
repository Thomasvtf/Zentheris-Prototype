# data/

Acceso a datos: un archivo por grupo de tablas, más `database.py` (conexión) y `readings.py` (inserción por lotes).

- **Va:** consultas e inserciones, con parámetros; inserción por lotes para el backfill (COPY o INSERT de varias filas).
- **No va:** reglas de negocio ni cambios de esquema (esos van en `supabase/migrations/`).
- **Ejemplo:** `insert_readings_batch(session, lecturas) -> int`.

Estado: `memberships.py`, `users.py`, `households.py` (alta del onboarding, bloqueo y borrado), `simulation_profiles.py` y `readings.py` (inserción por lotes) tienen consultas; el resto se escribe en la sesión de cada endpoint.
