# CLAUDE.md · supabase/ (migraciones y semilla)

Complementa al `CLAUDE.md` de la raíz. Fuente: `docs/supabase/especificacion-supabase-v1.md` y las reglas v4.9 §3.

## Reglas

- La base solo cambia con **migraciones numeradas** de Supabase CLI en `supabase/migrations/` (RN-XIX-02). Una migración aplicada no se edita: se crea otra.
- Las migraciones `0001` a `0006` **ya están aplicadas** en `zentheris` (08/11/2026): no se editan ni se repiten. Una migración nueva empieza en `0007` y lleva marca de tiempo al inicio del nombre, como las existentes.
- Cada migración tiene su prueba de verificación (conteo de tablas, columnas, restricciones y RLS activa) según la especificación §7.
- Semilla: `seed.sql` o un script que cargue las 5 personalidades desde `docs/datos/perfiles/consolidado_perfiles_simulacion.json`, **después de comprobar su SHA-256** (`6cfa9715…0a90922`).
- **Nunca** apliques una migración contra el proyecto remoto sin que una persona del equipo la revise y lo pida de forma explícita. Primero en local (`supabase start`) o en una rama de base.
- Sin datos personales ni credenciales en la semilla ni en las migraciones.

## Si alguien cambia la base desde el panel

No se hace. Si ocurre, compara con `supabase migration list` y avisa a una persona del equipo antes de tocar nada. El criterio DC-54 (reutilizar un proyecto con tablas a mano) ya no aplica: `zentheris` se creó nuevo y limpio (M-1).
