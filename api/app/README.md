# api/app/

Código de la API, por capas. Cada carpeta tiene su README.

```
routers/  →  services/  →  domain/  y  data/
   ↑              ↑
security/      schemas/ (los usan routers y services)
```

**Regla de dependencias:** `routers` solo llama a `services`; `services` llama a `domain` y a `data`; `domain` no importa FastAPI ni la base de datos (una prueba lo comprueba). `main.py` crea la app, `config.py` lee el entorno y `errors.py` define el formato `{codigo, mensaje, detalles}`.

**Ejemplo:** `GET /api/v1/hogares/{hogar_id}` → `routers/households.get_household` → `services/households.get_household` → `data/households` (y `domain/` si hay reglas). Ver [`docs/MAPA-DE-INTEGRACION.md`](../../docs/MAPA-DE-INTEGRACION.md).
