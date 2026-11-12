# Zentheris

Zentheris es una app móvil (Android e iOS) que muestra y ayuda a reducir el consumo energético de un hogar colombiano.
Trabaja con **datos simulados**: cinco personalidades de consumo generan las lecturas de cada vivienda y de sus zonas.
Es un proyecto formativo del SENA con visión profesional y un alcance de MVP cerrado.
La app (Expo) habla con una API REST (FastAPI), y la API con Supabase (PostgreSQL, Auth y Storage).
El contrato OpenAPI va primero: ningún endpoint ni campo se crea fuera de él.

## Carpetas

| Carpeta | Qué contiene |
|---|---|
| [`app/`](app/) | App móvil: Expo, React Native y TypeScript. Reglas en [`app/CLAUDE.md`](app/CLAUDE.md). |
| [`api/`](api/) | API REST: FastAPI y Python, monolito modular por capas. Reglas en [`api/CLAUDE.md`](api/CLAUDE.md). |
| [`supabase/`](supabase/) | Migraciones numeradas de la base y tipos de referencia. Ver [`supabase/README.md`](supabase/README.md). |
| [`docs/`](docs/) | Fuentes de verdad del proyecto: reglas, contrato, decisiones, datos, textos y diseño. |

## Por dónde empezar

1. [`CLAUDE.md`](CLAUDE.md): contexto permanente, fuentes de verdad en orden y reglas que no se rompen.
2. [`docs/README.md`](docs/README.md): índice de la documentación.
3. [`docs/reglas/reglas-de-negocio-v4.9.md`](docs/reglas/reglas-de-negocio-v4.9.md): reglas de negocio, tablas y pantallas.
4. [`docs/api/zentheris-api-v0.2.5.yaml`](docs/api/zentheris-api-v0.2.5.yaml): contrato de la API.
5. [`docs/guias/`](docs/guias/): guías para el equipo (app, backend e integración con Supabase y GitHub).
6. [`docs/PENDIENTES-DE-REFACTORIZACION.md`](docs/PENDIENTES-DE-REFACTORIZACION.md): tareas de la refactorización en curso.
