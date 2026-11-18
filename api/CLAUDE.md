# CLAUDE.md · api/ (FastAPI + Python)

Complementa al `CLAUDE.md` de la raíz. Guía humana: `docs/guias/GUIA-3-backend-y-arquitectura.md`.

## Estructura obligatoria (monolito modular por capas)

```
app/main.py            crea la app y registra los routers con el prefijo /api/v1
app/config.py          variables de entorno (docs/supabase/especificacion-supabase-v1.md §8)
app/errors.py          ApiError y respuesta {codigo, mensaje, detalles}; manejadores de error
app/security/          validate_jwt (JWKS), current_user, membership(hogar_id), require_permission(...), require_admin
app/schemas/           modelos Pydantic iguales al contrato (campos en español, como el YAML)
app/routers/           un archivo por etiqueta: system, users, households, onboarding, members_invitations, consumption, goals_tariff, alerts_tips; solo validan la entrada y llaman a servicios
app/services/          casos de uso (crear hogar, invitar, historial…) con los mismos nombres que routers/; manejan las transacciones. Más hour_recovery.py, scheduler.py y email.py
app/domain/            código puro y probado: simulator/ (portado de zentheris_sim), states.py, history.py, zone_rules.py, alert_rules.py, formats.py
app/data/              consultas SQL e inserción por lotes (COPY o INSERT de varias filas); un archivo por grupo de tablas
app/config_files/      umbrales-estado.v1.json y textos-backend.es-CO.json (copias exactas de docs/, conservan su nombre)
tests/                 unitarias de dominio, contrato y permisos (docs/pruebas/matriz-pruebas-backend-v1.md)
```

Nombres de carpetas, archivos, variables y funciones en inglés (decisión del 10/11/2026). Los campos de los esquemas, `CodigoError`, las tablas y `VERSION_MODELO` **no se renombran**: se quedan como en el contrato, las tablas y las reglas.

Dependencias permitidas entre capas: routers → services → domain y data. El dominio (`domain/`) no importa FastAPI ni la base de datos.

## Reglas

- Esquemas Pydantic **iguales** al contrato 0.2.5: mismos nombres, tipos y nulos. Una prueba de contrato compara cada respuesta con el YAML.
- Errores: `{codigo, mensaje, detalles}` con `codigo` del enum `CodigoError`. 404 si no hay membresía; 403 con el código exacto si falta el permiso.
- Simulador: porta `docs/datos/referencia/…zip › codigo/zentheris_sim/` con sus 59 pruebas. Cambia solo lo necesario para leer los perfiles desde la tabla.
- Motor de estados: debe reproducir `docs/datos/motor_estados_ref.py` y pasar los 13 escenarios de `test_escenarios_umbrales.py`.
- Onboarding: una sola transacción con el backfill e inserción por lotes. Mide el tiempo y regístralo en el log.
- Antes de responder consumo, historial, fuentes o alertas: completa las horas faltantes (RN-IV-05, DC-34).
- Las alertas y los consejos se generan solo sobre horas en vivo. `clave_evento` según DC-25.
- Texto de alertas y consejos: se rellena la plantilla del archivo y se guarda resuelto en la fila.
- Sin SMTP configurado (desarrollo local): escribe en el log el enlace de invitación.

## Comandos (confirma con pyproject.toml)

`uv sync` · `uv run uvicorn app.main:app --reload` · `uv run ruff check .` · `uv run pytest`.
