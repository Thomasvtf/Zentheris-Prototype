# config_files/

Copias exactas que lee la API en ejecución. Conservan el nombre del original.

| Archivo | Original |
|---|---|
| `umbrales-estado.v1.json` | [`docs/datos/umbrales-estado.v1.json`](../../../docs/datos/umbrales-estado.v1.json) |
| `textos-backend.es-CO.json` | [`docs/textos/textos-backend.es-CO.json`](../../../docs/textos/textos-backend.es-CO.json) |

**No se editan aquí.** Se editan en `docs/` y se vuelven a copiar. El CI compara el SHA-256 de cada copia con su original (`scripts/check_integration.py`) y falla si difieren. Las rutas las leen `RUTA_UMBRALES` y `RUTA_TEXTOS_BACKEND`, relativas a `api/`.
