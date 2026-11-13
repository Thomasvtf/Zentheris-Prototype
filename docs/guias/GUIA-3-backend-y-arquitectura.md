# Guía 3 · Construir el backend y la arquitectura general

Versión 2 · 03/11/2026 (actualizada el 10/11/2026: carpetas en inglés y nombres de ramas). Para quien programa la API (FastAPI) y configura Supabase, **y para Claude Code**, que escribirá la mayor parte del código. Personas: lean los puntos 0, 1, 3 y 10. Claude Code: siga `CLAUDE.md`, `api/CLAUDE.md` y `supabase/CLAUDE.md`, y use esta guía como especificación. Las rutas `docs/…` son las del repositorio después de instalar `11_guias-de-desarrollo/paquete-repo/`. Fuentes: reglas v4.9, contrato 0.2.5, `02_base-de-datos/especificacion-supabase-v1.md`, `04_datos-simulados/` (Avance 03 y calibración de umbrales v1), catálogo de textos v1 y el prototipo (lectura estática; **no se ejecutó**).

**Antes de empezar:** la base de datos ya está creada (08/11/2026) en el proyecto `zentheris`, con las 6 migraciones aplicadas (ver `supabase/migrations/` y `docs/supabase/especificacion-supabase-v1.md`, v1.1). Nada de esto se vuelve a crear.

## 0. Tipo de arquitectura (DC-56)

**Cliente-servidor de tres niveles, contrato primero.** La API es un **monolito modular por capas** con el dominio aislado (hexagonal ligera). Por debajo, Supabase como backend gestionado (BaaS).

| Decisión | Elegido | Por qué | Descartado |
|---|---|---|---|
| Estilo general | Cliente móvil → API REST propia → Supabase | Reglas de negocio y permisos en un solo lugar (RN-I-03); el simulador necesita servidor | App directa a Supabase con RLS como única defensa (lógica repartida, difícil de probar) |
| Backend | **Monolito modular** (un servicio FastAPI) | Equipo pequeño, MVP y plan gratuito de Render | Microservicios (costo y complejidad sin beneficio) |
| Capas | routers → servicios → dominio puro y datos | El dominio (simulador, estados, alertas) se prueba sin base ni HTTP | Lógica y SQL en los routers |
| Contrato | **OpenAPI 0.2.5 primero**; tipos de la app generados desde él | App y API avanzan en paralelo sin romperse | Contrato implícito en el código |
| Datos | PostgreSQL de Supabase con migraciones; RLS como segunda defensa | Integridad (restricciones de v4.9) y trazabilidad (RN-XIX-02) | Esquema editado a mano en el panel |
| Procesos de fondo | Dentro del mismo servicio: recuperación de horas antes de consultar + tarea programada | Render gratuito se suspende (DC-34) | Colas o workers aparte |
| Textos y umbrales | Archivos de configuración versionados | Cambian sin migraciones (RN-XI-07, RN-XI-09) | Tablas de configuración |
| App | Organizada por funcionalidad; React Query; componentes de presentación | Ver guía 2 | Estado global en Redux |

## 1. La arquitectura en un dibujo

```
 App Expo (Android/iOS)
   │  1. registro, acceso, recuperación, cambio de correo ──► Supabase Auth (correos con Brevo)
   │  2. sube su foto ─────────────────────────────────────► Supabase Storage (bucket privado «avatares»)
   │  3. todo lo demás, con «Authorization: Bearer <JWT>» ─► API FastAPI (Render, Virginia)
   │                                                           │ valida el JWT (JWKS)
   │                                                           │ comprueba membresía, rol y permiso
   │                                                           │ completa horas faltantes (simulador)
   │                                                           │ calcula estados (umbrales v1)
   │                                                           ▼
   │                                                    PostgreSQL de Supabase (us-east-1, 17 tablas + RLS)
   │
   └─ Textos: la app lee su catálogo; el backend escribe alertas y consejos desde textos-backend.es-CO.json
```

Datos simulados (`calidad = 'simulada'`); no hay IA (RN-VIII-01).

## 2. Carpetas de `api/`

```
api/
  .env.example           # nombres de variables, sin valores
  .python-version        # versión de Python que lee Render
  pyproject.toml · uv.lock · requirements.txt   # requirements.txt en UTF-8, generado desde uv
  app/
    main.py              # crea la app, registra los routers con /api/v1 y el CORS por variable
    config.py            # lee variables de entorno (especificación Supabase §8)
    errors.py            # errores con {codigo, mensaje, detalles} y sus manejadores
    security/            # validar JWT; dependencias: current_user, membership(hogar_id), require_permission(...), require_admin
    schemas/             # modelos Pydantic iguales al contrato (campos en español, como el YAML)
    routers/             # un archivo por tag del contrato: system, users, households, onboarding, members_invitations, consumption, goals_tariff, alerts_tips; las funciones de cada router van en inglés (por ejemplo `get_health` para `obtenerSalud`; la tabla completa está en `docs/MAPA-DE-INTEGRACION.md`)
    services/            # la lógica de cada caso de uso, con los mismos nombres que routers/; más hour_recovery.py, scheduler.py y email.py
    domain/              # código puro, sin FastAPI ni SQL
      simulator/         # el paquete zentheris_sim del Avance 03 (DC-53)
      states.py          # motor de estados (mismo comportamiento que motor_estados_ref.py)
      history.py         # comparación de periodos, pico y proyección (RN-XIII)
      zone_rules.py      # validación de zonas (Z-01 a Z-04)
      alert_rules.py     # alertas y consejos: catálogo inicial (RN-XIV-07, RN-XV-07)
      formats.py         # claves de evento y textos del backend con variables
    data/                # acceso a PostgreSQL: un archivo por grupo de tablas
    config_files/        # umbrales-estado.v1.json y textos-backend.es-CO.json (copias exactas, conservan su nombre)
  tests/                 # unitarias, de contrato y de permisos: una subcarpeta por grupo de la matriz y un archivo por ID (matriz en 09_pruebas/)
scripts/check_integration.py   # comprueba que contrato, routers, app y mapa coincidan
supabase/migrations/     # migraciones numeradas (RN-XIX-02)
supabase/LEEME.md        # huella de las migraciones aplicadas
```

**Nombres en el código (decisión del 10/11/2026):** carpetas, archivos, variables y funciones en inglés (en el texto de esta guía las capas se nombran en español: routers, servicios `services/`, dominio `domain/`, datos `data/`, seguridad `security/`). Con la convención de Python: `snake_case` para módulos y funciones, `PascalCase` para clases. No se renombran los campos del contrato, `CodigoError`, las tablas ni `VERSION_MODELO`. Los nombres de los archivos de `routers/` quedaron fijados en la propuesta de la Fase 2 (10/11/2026).

### ¿Dónde va cada cosa?

| Quiero… | Va en… |
|---|---|
| Una operación nueva del contrato | Su ruta en `routers/`, su caso de uso en `services/` y su modelo en `schemas/`; se agrega al `docs/MAPA-DE-INTEGRACION.md` |
| Una regla de negocio o un cálculo (estados, historial, zonas, alertas) | `domain/`, sin FastAPI ni SQL |
| Una consulta a la base de datos | `data/` |
| Seguridad (validar el JWT, permisos) | `security/` |
| Umbrales o textos del backend | `config_files/` |
| Un error de la API | `errors.py` |
| Una tarea programada, la recuperación de horas o el envío de correo | `services/` (`scheduler.py`, `hour_recovery.py`, `email.py`) |
| Una prueba | `tests/`, en la subcarpeta de su grupo de la matriz |
| Un cambio en la base de datos | Una migración nueva en `supabase/migrations/` (la aplica una persona) |
| Comprobar que contrato, routers y app coinciden | `scripts/check_integration.py` |

## 3. Orden de construcción

| Paso | Qué | Listo cuando |
|---|---|---|
| 0 | Arreglar el prototipo (punto 8) y dejar CI en verde | `ruff` y `pytest` pasan |
| 1 | ~~Preparar Supabase~~ **Hecho el 08/11/2026** con un proyecto nuevo `zentheris` (M-1, reemplaza DC-54): 6 migraciones aplicadas y verificadas; Auth y SMTP de Brevo configurados. Solo falta tener las migraciones en el repositorio y cada persona su `.env` local | Comprobaciones §7 de la especificación: ya OK (acta del 08/11/2026) |
| 2 | Seguridad: JWT + `current_user` + `membership` + `require_permission` | Pruebas de permisos (P-*) pasan |
| 3 | `GET/POST/PATCH /usuarios/me`, preferencias, avatar | Ficha creada en el primer acceso (RN-IX-01) |
| 4 | Simulador + `POST /onboarding` en una transacción con backfill por lotes | 720 × zonas lecturas; mide el tiempo (DC-33) |
| 5 | Recuperación de horas antes de cada consulta (DC-34) + tarea programada | No hay huecos ni duplicados |
| 6 | Motor de estados + `consumo/actual`, `consumo/zonas`, `consumo/zonas/{id}` | 13 escenarios de umbrales iguales al de referencia |
| 7 | `historial` (comparación, pico, anillo, costo, proyección) | Casos de RN-XIII y DC-29 a DC-31 |
| 8 | Alertas y consejos sobre horas en vivo + cierre de mes | Una alerta por regla, zona y día |
| 9 | Miembros, invitaciones (SMTP Brevo), permisos, transferir, salir y eliminar cuenta | Casos RN-X y RN-IX-09 |
| 10 | Meta, tarifa y fuentes de datos | Casos RN-XVI |
| 11 | Despliegue en Render y medición del backfill | p95 ≤ 10 s; si no, plan 202 |

## 4. Receta para cada endpoint

1. Copia del contrato la ruta, los parámetros y los esquemas (no inventes campos).
2. Dependencias: `current_user` → `membership(hogar_id)` (si no hay, **404**) → `require_permission` o `require_admin` (si falta, **403** con el `CodigoError` exacto).
3. Si es de consumo, historial, fuentes o alertas: **primero** completa las horas faltantes del hogar.
4. Lógica en `services/`, cálculos en `domain/`. Nada de SQL dentro de los routers.
5. Responde números sin formato; `null` = sin dato.
6. Prueba: caso feliz + un caso por cada error del contrato + uno de permisos.

## 5. Reglas de cálculo (resumen; el detalle está en v4.9)

- **Última hora completa:** la hora anterior a la actual en America/Bogota. Su kWh es el kW promedio de esa hora.
- **Referencia:** promedio de la misma hora en los 30 días completos previos; con menos de 7 días con dato → `sin_referencia`. Con meta: límite diario × peso habitual de la hora.
- **Estados:** `umbrales-estado.v1.json`. Compara el porcentaje redondeado a 6 decimales; los límites son inclusivos.
- **Comparación:** mismo tramo del periodo anterior; si le falta alguna hora → `sin_anterior`.
- **Pico:** +10 % o más sobre su promedio.
- **Proyección:** acumulado + promedio de lo que falta; en COP, con el precio vigente hoy y el cargo fijo solo en Mes.
- **Costo de cada fecha:** con la tarifa vigente en esa fecha (intervalo `[desde, hasta)`).
- **Alertas:** solo sobre horas generadas en vivo; `clave_evento` según DC-25. Al crear un consejo, crea una fila `pendiente` por cada miembro activo y la alerta «Nuevo consejo» (RN-XV-06).
- **Entrega de alertas:** solo a quien tenga en ese momento el permiso del hogar y su interruptor encendido (RN-VI-02, RN-XIV-06).

Referencia ejecutable: `04_datos-simulados/calibracion-umbrales-v1/motor_estados_ref.py` y `test_escenarios_umbrales.py`. Las pruebas del backend deben dar los mismos resultados.

## 6. Simulador (DC-53)

- El módulo de producción parte de `codigo/zentheris_sim/` del Avance 03: semillas SHA-256, frontera, recuperación y validación. Trae sus 59 pruebas, que se copian a `tests/`.
- Mantener `VERSION_MODELO = "zentheris-4.3-ref-1"` como constante (RN-IV-04). Si cambia, cambian todas las lecturas y hay que emitir una nueva acta.
- Las personalidades se leen de la tabla `perfiles_simulacion`, sembrada desde el consolidado con su SHA-256 comprobado.
- Para guardar lecturas se usa `COPY` o `INSERT` de varias filas, en la misma transacción del onboarding.

## 7. Seguridad mínima

- La `service_role` y la cadena de conexión solo viven en Render. Nunca en la app, en el repositorio ni en Notion.
- CORS: en producción, solo los orígenes necesarios. La app nativa no necesita CORS; el comodín es solo para desarrollo.
- Los errores al cliente llevan `codigo` y un `mensaje` técnico corto. **Nunca** la excepción interna.
- Las invitaciones guardan solo el hash del token (RN-X-05).
- Las RLS existen, pero la API no depende de ellas: el backend comprueba siempre.

## 8. Refactorizar el prototipo (`api/` de `Thomasvtf/Zentheris-Prototype`)

Lectura estática del zip de `main` del 03/11/2026. **No se ejecutó.** Se refactoriza **en el mismo repositorio** (DC-55), en ramas `<tipo>/<descripcion>` que salen de `main` (decisión del 10/11/2026: sin `chore`; las ramas personales del equipo siguen con `<Persona>/feat-<Tema>`); no se empieza un repositorio de cero.

| Qué hay hoy | Qué hacer | Por qué |
|---|---|---|
| FastAPI 0.141, SQLModel, psycopg2, uvicorn, uv + ruff + pytest en CI | **Conservar** la base y el CI | Correcto |
| `requirements.txt` guardado en UTF-16 | Regenerarlo en UTF-8 desde `uv` (o quitarlo y usar solo `pyproject.toml` + `uv.lock`) | `pip` no lo lee bien |
| `requires-python >= 3.14` | Confirmar que Render tenga esa versión; si no, bajar a la que use Render y probar | Despliegue |
| `/salud/bd` consulta `zonas` y devuelve el texto del error | Quitar el detalle del error (no exponer excepciones); usar `SELECT 1` | Seguridad; la tabla aún no existe |
| `/salud` y `/` | Mantener solo `/api/v1/salud` según el contrato | Contrato 0.2.5 |
| CORS `allow_origins=["*"]` con `allow_credentials=True` | Lista de orígenes por variable de entorno | Seguridad |
| `config.py` con `SUPABASE_ANON_KEY` y `SIM_SEED` | Cambiar a las variables de la especificación §8. Quitar `SIM_SEED`: la semilla es SHA-256 por hogar y fecha | RN-IV-04 y la sección 5 de las reglas |
| `routers/` y `simulador/` vacíos | Crear según los puntos 2 y 6 | — |
| `.kilo/worktrees/*/api` | Borrar y añadir a `.gitignore` | Copias duplicadas |

## 9. Despliegue

- Render (servicio web, región Virginia). El plan gratuito se suspende: por eso existe la recuperación de horas (DC-34). La primera llamada después de una pausa tarda más; la app la cubre con su tiempo de espera de 15 s o 60 s.
- Supabase `zentheris` (us-east-1, organización «Zentheris»). Reactivarlo desde el panel si se pausó (plan gratuito: una semana sin actividad).
- EAS para las builds; incluye Satoshi con `.easignore` (DC-06).
- Antes de cada demostración: abrir `/api/v1/salud`, iniciar sesión con un usuario de prueba y revisar el Panel.

## 10. Hecho significa

Una función está **hecha** cuando tiene código, pruebas que pasan en CI, la regla RN- citada en el PR y un caso probado en Android y en iOS (si tiene interfaz). «Implementado» sin prueba no cuenta como hecho.

## 11. Cómo trabajar con Claude Code (DC-57)

1. Instala el paquete de contexto (`11_guias-de-desarrollo/paquete-repo/LEEME-paquete-repo.md`).
2. Una fase por sesión y un PR por fase, siguiendo la tabla de sesiones del paquete. Cada sesión empieza pidiéndole que lea `CLAUDE.md` y proponga un plan.
3. Claude Code escribe el código y las pruebas. **Una persona** revisa el diff, corre las pruebas y aprueba.
4. Claude Code no aplica migraciones al proyecto remoto ni fusiona PR por su cuenta, y nunca maneja secretos: los `.env` los llena una persona.
5. Si Claude Code encuentra una contradicción entre documentos, la reporta en el PR y gana la regla de número menor del `CLAUDE.md` raíz.
