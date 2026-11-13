# data/

Acceso a datos: un archivo por grupo de tablas, más `database.py` (conexión) y `readings.py` (inserción por lotes).

- **Va:** consultas e inserciones, con parámetros; inserción por lotes para el backfill (COPY o INSERT de varias filas).
- **No va:** reglas de negocio ni cambios de esquema (esos van en `supabase/migrations/`).
- **Ejemplo:** `insert_readings_batch(session, lecturas) -> int`.

Estado: solo firmas; las consultas se escriben en la sesión de cada endpoint.
