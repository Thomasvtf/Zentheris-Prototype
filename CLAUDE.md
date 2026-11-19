# CLAUDE.md · Zentheris (raíz del repositorio)

Contexto permanente para Claude Code. Léelo completo al empezar cada sesión. Si algo de aquí contradice una instrucción puntual del equipo, pregunta antes de actuar.

## Qué es

Zentheris es una app móvil (Android e iOS) que muestra y ayuda a reducir el consumo energético de un hogar colombiano con **datos simulados**. Es un proyecto formativo SENA con visión profesional. Su alcance es un MVP cerrado: **sin IA o ML, sin push, sin chatbot, sin descargas, sin lecturas manuales y sin transición energética**.

## Fuentes de verdad (en este orden)

1. `docs/reglas/reglas-de-negocio-v4.9.md`: reglas `RN-*`, las 18 tablas (§3) y las pantallas (§6).
2. `docs/api/zentheris-api-v0.2.5.yaml`: contrato OpenAPI (contract-first). **No inventes endpoints ni campos.**
3. `docs/decisiones/registro-decisiones-cierre-2026-11-03.md`: decisiones DC-01 a DC-67.
4. `docs/datos/umbrales-estado.v1.json` y `docs/datos/motor_estados_ref.py`: cálculo de estados. Las pruebas de referencia están en `test_escenarios_umbrales.py`.
5. `docs/textos/`: catálogo de textos (app, backend y Supabase). **Ningún texto de interfaz se escribe a mano.**
6. `docs/diseno/`: tokens y fichas de los 31 componentes más 3 gráficos de consumo (`ConsumptionGauge`, `ConsumptionRing`, `LineChart`). Primero lee `CORRECCIONES-LEER-PRIMERO.md`.
7. `docs/supabase/especificacion-supabase-v1.md`: tablas, restricciones, RLS, Storage y variables de entorno.
8. `docs/historias/` (27 historias) y `docs/pruebas/` (matriz de pruebas).

Si dos fuentes chocan, gana la de número menor. Avisa la contradicción en el PR. Las guías humanas están en `docs/guias/`.

## Arquitectura (DC-56)

- **Cliente-servidor de tres niveles:** app Expo (cliente) → API REST FastAPI (Render) → Supabase (PostgreSQL, Auth y Storage). Contrato OpenAPI primero.
- **Monorepo:** `app/` (Expo / React Native, TypeScript), `api/` (FastAPI, Python), `supabase/` (migraciones y semilla) y `docs/`.
- **Backend: monolito modular por capas** (routers → servicios → dominio → datos). El dominio es puro, sin FastAPI ni SQL: simulador, motor de estados y reglas de alertas.
- **App: organizada por funcionalidad,** con capas rutas (expo-router) → pantallas → hooks de datos (React Query) → cliente API tipado generado desde el contrato. Componentes del sistema de diseño solo de presentación.
- La app **solo** habla con Supabase para Auth y para subir su foto. Todo lo demás pasa por la API.

## Reglas que no se rompen

- Formato es-CO solo en la app: coma decimal, kW con 2 decimales, kWh con 1, COP sin decimales, «34 %». La API devuelve números.
- `null` es «sin dato», nunca cero. «Crítico», nunca «sobreconsumo».
- Estado = color + ícono + palabra. Rojo y amarillo solo para severidad. El pico usa `chart-peak` y nunca un componente de estado.
- El backend comprueba en **cada** llamada la membresía activa, el rol y el permiso. RLS es la segunda defensa, no la primera.
- Las alertas se evalúan solo sobre horas generadas en vivo, nunca sobre el backfill. Antes de responder consultas de consumo, se completan las horas faltantes.
- `VERSION_MODELO = "zentheris-4.3-ref-1"` es una constante (RN-IV-04).
- Cambios de esquema **solo** como migraciones nuevas en `supabase/migrations/`. Nunca se editan migraciones ya aplicadas ni se toca la base a mano.

## Nombres en el código

- Carpetas, archivos, variables y funciones **en inglés**, con la convención de cada lenguaje: TypeScript y JavaScript, `camelCase` (variables y funciones) y `PascalCase` (componentes y tipos); Python, `snake_case` (módulos y funciones), `PascalCase` (clases) y `MAYÚSCULAS_CON_GUION_BAJO` (constantes).
- **No se renombran:** el contrato de la API (rutas, campos y `CodigoError`), las tablas y columnas, la documentación, el catálogo es-CO, los componentes del sistema de diseño ni constantes que fijan las reglas (`VERSION_MODELO`).
- Los nombres de archivo de las rutas de expo-router **se quedan en español** (son direcciones, como las rutas del contrato; decisión del 10/11/2026). Es la única excepción a la regla del inglés.

## Seguridad

- Nunca escribas, pidas ni copies claves, tokens, contraseñas ni cadenas de conexión. Solo van en `.env` (ignorado por git) y en los paneles de Render, Supabase y EAS. El repositorio es **público**.
- No subas la fuente Satoshi (licencia ITF): va en `app/assets/fonts/satoshi/`, ignorada por git.
- No expongas excepciones internas en las respuestas de la API.

## Cómo trabajar

1. **Planifica antes de codificar.** Lee las fuentes de la tarea y propón un plan corto (archivos, reglas RN y endpoints). Espera el visto bueno si la tarea cambia más de una carpeta.
2. Ramas cortas `<tipo>/<descripcion>` desde `main` (`feat`, `fix`, `docs`, `refactor`, `build`, `ci`, `test`; **sin `chore`**). Las ramas personales del equipo siguen con `<Persona>/feat-<Tema>`. Commits `tipo(alcance): descripción` (tipo en inglés, descripción en español). Un PR por historia o por fase. Nunca hagas commit directo a `main`; los PR hacia `main` los aprueba otra persona.
3. Cada cambio trae sus pruebas. CI (`ruff`, `pytest` y lint de la app) debe quedar en verde.
4. En la descripción del PR: reglas RN, endpoints y decisiones DC que cubre; qué se probó; qué no se probó (por ejemplo, «no probado en iOS»).
5. Si falta un dato, no lo inventes. Deja `TODO(pendiente: …)` y pregúntalo en el PR.
6. **Sin atribución a Claude en GitHub:** ningún commit, PR ni comentario lleva `Co-Authored-By: Claude…` ni «Generated with Claude Code».

## Hecho significa

Código + pruebas en verde en CI + reglas citadas + revisión de una persona del equipo. Si tiene interfaz, además: probado en Android y en iOS, o declarado como no probado.
