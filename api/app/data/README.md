# data/

Acceso a datos: un archivo por grupo de tablas, más `database.py` (conexión) y `readings.py` (inserción por lotes).

- **Va:** consultas e inserciones, con parámetros; inserción por lotes para el backfill (COPY o INSERT de varias filas).
- **No va:** reglas de negocio ni cambios de esquema (esos van en `supabase/migrations/`).
- **Ejemplo:** `insert_readings_batch(session, lecturas) -> int`.

Estado: `memberships.py` (membresía activa, alta, cierre y destinatarios de alertas), `users.py`, `households.py` (alta del onboarding, bloqueo, borrado, hogares con sensores activos, zonas y fecha de alta), `simulation_profiles.py` (por nombre y del hogar), `readings.py` (inserción por lotes, huecos por sensor y lecturas horarias), `goals.py` (meta activa y meta vigente en un día), `alerts.py` (claves de evento, alta, entregas, listado, conteo y lectura) y `tips.py` (últimos por regla y zona, alta, asignación, listado y estado) tienen consultas; el resto se escribe en la sesión de cada endpoint.
