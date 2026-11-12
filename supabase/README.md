# supabase/

Esquema de la base de Zentheris en Supabase (PostgreSQL, Auth y Storage). Reglas para Claude Code en [`CLAUDE.md`](CLAUDE.md). Fuente: [`docs/supabase/especificacion-supabase-v1.md`](../docs/supabase/especificacion-supabase-v1.md) y las reglas v4.9 §3.

## Qué va aquí

- `migrations/`: **migraciones numeradas** de Supabase CLI, con el nombre `<version>_<NNNN>_<nombre>.sql`. Las `0001` a `0006` ya están aplicadas en el proyecto definitivo (08/11/2026): no se editan ni se repiten.
- `types/database.types.ts`: tipos de la base generados el 08/11/2026 (17 tablas). Solo de referencia; se regeneran cuando cambia el esquema.
- [`LEEME.md`](LEEME.md): orden de las migraciones y huella esperada del esquema.

## Qué no va aquí

- SQL escrito a mano fuera de una migración, ni cambios hechos desde el panel de Supabase.
- Datos de prueba ni funciones de prueba: viven solo en el entorno de laboratorio.
- Claves, contraseñas, archivos `.env` ni datos personales.

## Cómo se crea una migración nueva

1. Crear un archivo nuevo en `migrations/`; la siguiente es la `0007`. Una migración aplicada nunca se edita: todo cambio es un archivo nuevo.
2. Probarla primero en el laboratorio (`zentheris-dev`) o en local (`supabase start`), con las comprobaciones posteriores de la especificación §7, punto 2 (tablas, RLS activa, personalidades y bucket privado).
3. Abrir un PR. Si cambia el esquema, se actualizan en el mismo PR la huella de `LEEME.md` y `types/database.types.ts`.

## Quién la aplica

Solo una persona designada del equipo, **después** de que otra persona apruebe el PR y lo pida de forma explícita. Nadie aplica migraciones contra el proyecto remoto por su cuenta.
