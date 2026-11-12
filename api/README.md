# api/

API REST de Zentheris: FastAPI y Python, monolito modular por capas (DC-56). Contrato primero: [`docs/api/zentheris-api-v0.2.5.yaml`](../docs/api/zentheris-api-v0.2.5.yaml). Reglas para Claude Code en [`CLAUDE.md`](CLAUDE.md); guía humana en [`docs/guias/GUIA-3-backend-y-arquitectura.md`](../docs/guias/GUIA-3-backend-y-arquitectura.md).

## Comandos (desde `api/`)

| Para qué | Comando |
|---|---|
| Instalar dependencias | `uv sync` |
| Levantar la API en local | `uv run uvicorn app.main:app --reload` (docs en `http://localhost:8000/docs`) |
| Revisar estilo | `uv run ruff check .` |
| Pruebas | `uv run pytest` |
| Comprobar integración | `uv run python ../scripts/check_integration.py` |

Variables de entorno: copia [`.env.example`](.env.example) como `api/.env` y rellénalo (guía de claves v3). `api/.env` nunca se sube.

## Qué va aquí y qué no

- **Va:** el código de la API (`app/`), sus pruebas (`tests/`) y su configuración (`pyproject.toml`, `uv.lock`, `requirements.txt`, `.python-version`).
- **No va:** claves ni `.env`, SQL de migraciones (van en `supabase/migrations/`), textos de interfaz de la app ni copias de `docs/` fuera de `app/config_files/`.
