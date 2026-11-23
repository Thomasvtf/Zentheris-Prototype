# api/

API REST de Zentheris: FastAPI y Python, monolito modular por capas (DC-56). Contrato primero: [`docs/api/zentheris-api.yaml`](../docs/api/zentheris-api.yaml). Reglas para Claude Code en [`CLAUDE.md`](CLAUDE.md); guía humana en [`docs/guias/GUIA-3-backend-y-arquitectura.md`](../docs/guias/GUIA-3-backend-y-arquitectura.md).

## Comandos (desde `api/`)

| Para qué | Comando |
|---|---|
| Instalar dependencias | `uv sync` |
| Levantar la API en local | `uv run uvicorn app.main:app --reload` (docs en `http://localhost:8000/docs`) |
| Revisar estilo | `uv run ruff check .` |
| Pruebas | `uv run pytest` |
| Comprobar integración | `uv run python ../scripts/check_integration.py` |

**Generación horaria (RN-IV-05, DC-34).** Al arrancar con `DATABASE_URL`, la API completa las horas que faltan de todos los hogares y luego repite esa tarea cada hora, en el minuto 0 (hora de Colombia). Sin `DATABASE_URL` no programa nada: lo avisa en la consola con un WARNING. Cada copia de la API que arranca con la misma base corre su propia tarea. Un candado por hogar y la restricción única de `lecturas` impiden duplicados, pero la carga se multiplica. Por eso:

- En Render, arranca con **un solo proceso**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, sin `--workers` ni `--reload`.
- En local, si no necesitas la base, deja `DATABASE_URL` vacía. Si la usas, ten presente que tu copia también genera las horas de todos los hogares de ese proyecto.

Variables de entorno: copia [`.env.example`](.env.example) como `api/.env` y rellénalo (guía de claves v3). `api/.env` nunca se sube.

## Qué va aquí y qué no

- **Va:** el código de la API (`app/`), sus pruebas (`tests/`) y su configuración (`pyproject.toml`, `uv.lock`, `requirements.txt`, `.python-version`).
- **No va:** claves ni `.env`, SQL de migraciones (van en `supabase/migrations/`), textos de interfaz de la app ni copias de `docs/` fuera de `app/config_files/`.
