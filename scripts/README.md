# scripts/

Herramientas del repositorio que no son parte de la app ni de la API. Se ejecutan desde la raíz.

| Script | Qué hace | Dónde corre |
|---|---|---|
| `check_integration.py` | **Parte A:** comprueba con SHA-256 que las copias de `api/app/config_files/` son idénticas a sus originales de `docs/`. **Parte B** (PR 5): contrato, routers, app y mapa de integración. | En el CI de cada PR y en local: `python scripts/check_integration.py` |

**Qué no va aquí:** código que use la app o la API en ejecución, ni scripts con claves o que se conecten a la base.
