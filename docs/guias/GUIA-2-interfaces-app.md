# Guía 2 · Construir las interfaces de la app (Expo + React Native)

Versión 2 · 03/11/2026 (actualizada el 10/11/2026: carpetas en inglés, nombres de ramas y orden de las librerías). Para el equipo que programa las pantallas **y para Claude Code**, que escribirá la mayor parte del código. Fuentes: reglas v4.9, contrato 0.2.5, catálogo de textos v1, sistema de diseño (kit v3.2 y artifact «Zentheris»), Figma (copia `RD1IQ5L1OmUeMxteRimvMe`, flujos Administrador y Miembro) y el prototipo `Thomasvtf/Zentheris-Prototype` (lectura estática del zip de `main`, 03/11/2026; **no se ejecutó**).

## 0. Cómo usar esta guía

| Si eres… | Usa la guía así |
|---|---|
| Persona del equipo | Lee los puntos 1 a 3 para entender qué se construye y por qué. Usa los puntos 8 y 9 para revisar lo que entregue Claude Code. |
| Claude Code | Sigue `app/CLAUDE.md` (reglas permanentes) y esta guía como especificación. Las rutas `docs/…` son las del repositorio después de instalar el paquete (`11_guias-de-desarrollo/paquete-repo/`). |

Equivalencia de rutas: `Archivos_Zentheris/01_reglas-y-modelo/reglas-de-negocio-v4.9.md` = `docs/reglas/…`; contrato = `docs/api/…`; catálogo = `docs/textos/…`; tokens y fichas = `docs/diseno/…` (leer primero `docs/diseno/CORRECCIONES-LEER-PRIMERO.md`).

## Arquitectura de la app (DC-56)

- **Organización por funcionalidad** (una carpeta por pantalla) con cuatro capas: **rutas** (expo-router, solo navegan) → **pantallas** (vista) → **hooks de datos** (React Query: caché, reintentos y estados) → **cliente API tipado**, generado desde el contrato 0.2.5.
- **Componentes del sistema de diseño** solo de presentación: reciben datos ya calculados (estado, valor y textos) y no llaman a la API.
- **Estado:** datos del servidor en React Query; sesión en Supabase Auth (`expo-secure-store`). Sin Redux.
- **Textos y formato:** capas transversales (`texts/`, `format/`). El backend nunca envía textos de estado formateados.
- **Navegación:** tres grupos, `(auth)`, `(onboarding)` y `(tabs)` (se crean en la sesión 10, no en la refactorización inicial). El usuario entra a uno u otro según RN-X-01 (con hogar → tabs; con invitación → Invitación recibida; sin hogar → onboarding).

## 1. Antes de escribir código (15 minutos)

Lee solo esto:

1. `01_reglas-y-modelo/reglas-de-negocio-v4.9.md`, sección 6 (pantallas) y las reglas de la pantalla que vas a hacer.
2. `03_api/zentheris-api-v0.2.5.yaml`: el endpoint de tu pantalla (ver la tabla del punto 3).
3. `06_catalogo-de-textos/catalogo-textos-v1/app/catalogo.es-CO.json`: **todos** los textos salen de aquí.
4. El sistema de diseño: tokens (`05_sistema-de-diseno/tokens.zip`) y la ficha del componente que vas a usar.
5. La pantalla en Figma, en el flujo Administrador o Miembro, solo como referencia visual.

**Regla de oro:** si Figma y el catálogo dicen cosas distintas, **gana el catálogo** (DC-21). Si el catálogo y las reglas dicen cosas distintas, gana la regla: avisa a Nicolás.

## 2. Diez reglas que no se rompen

1. **No escribas textos a mano.** Usa la clave del catálogo (`t('panel.saludo')`). Los estados llegan como `mensaje_codigo` y se leen así: `estado.<mensaje_codigo>.titulo / .cuerpo / .leyenda`.
2. **No escribas colores ni tamaños a mano.** Solo tokens `z-*` (por ejemplo, el verde de acento es `#5DD39E`, no `#00E676`).
3. **El número va primero:** valor en JetBrains Mono y unidad pequeña en `text-muted`. kW con 2 decimales, kWh con 1, COP sin decimales, coma decimal, «34 %» con espacio sin ruptura (RN-XII-08). La API manda números; la app los formatea.
4. **Sin dato no es cero:** `null` se muestra «—»; `0` se muestra «0,00 kW».
5. **Estado = color + ícono + palabra.** Nunca solo color. Rojo y amarillo solo para severidad.
6. **El pico** se marca con la etiqueta «Pico» y el rojo claro `chart/peak`. Nunca con la píldora de estado ni con la palabra «Crítico» (D17).
7. **COP solo con tarifa vigente.** Si `tarifa_vigente` es `false`, oculta el selector COP y muestra «Configura tu tarifa».
8. **Permisos:** si la API responde `403` con `SIN_PERMISO_*`, cambia **solo las cards de datos** por `StateMessage tipo="sin_permiso"`. Cabecera y saludo siguen visibles (RN-XVII-05).
9. **Sin IA, sin push, sin descargas, sin chatbot** (alcance del MVP).
10. **Accesibilidad:** áreas táctiles de 44 × 44 pt o más, etiquetas en español en los íconos que se tocan y un resumen en texto de cada gráfico. No digas que la app «es accesible»: no está verificado.

## 3. Mapa pantalla → endpoint → componentes

| Pantalla (reglas §6) | Endpoint (contrato 0.2.5) | Componentes del sistema de diseño | Reglas clave |
|---|---|---|---|
| Inicio neutral, Inicio de sesión, Registro | Supabase Auth (sin API) + `POST /usuarios/me` en el primer acceso | Button, TextField, Requirement | RN-IX-01 a IX-04 |
| Recuperar y Restablecer contraseña; Revisa tu correo | Supabase Auth | TextField, Requirement, InlineNotice | RN-IX-03, IX-04 |
| Invitación recibida | `GET /invitaciones/recibidas`, `POST /invitaciones/{id}/aceptar` y `/rechazar` | InvitationCard, ConfirmDialog | RN-X-01, X-06, IX-08 |
| Onboarding (2 pasos) | `POST /onboarding` (espera hasta 60 s) | StepIndicator, Select, ZoneTile, Button | RN-X-02, X-09, IX-08 |
| Carga del backfill | Misma llamada; si falla, `BACKFILL_FALLIDO` → Reintentar | Skeleton, InlineNotice | RN-IV-02, X-03 |
| Panel principal | `GET /hogares/{hogar_id}/consumo/actual`, `/consumo/zonas`, `/alertas/no-leidas` | ScreenHeader, ConsumptionCard, StatusBadge, ProgressBar, Chip (kW/COP), BottomNav | RN-XI, RN-XII |
| Historial | `GET /hogares/{hogar_id}/historial?periodo=dia\|semana\|mes&zona_id=` | Chip, BarChart, PeakMarker, ZoneDonutChart, Metric, StatusBadge | RN-XIII |
| Zonas y Zona individual | `GET /consumo/zonas`, `GET /consumo/zonas/{zona_id}` | Card de zona, Icon, ProgressBar, StatusBadge | RN-XI-05, XI-06, XII-06, XII-07 |
| Consejos | `GET /consejos`, `PUT /consejos/{id}/estado` | TipList, TipCard, PriorityTag, StateMessage | RN-XV |
| Alertas | `GET /alertas`, `POST /alertas/marcar-leidas` | AlertItem, Chip (filtros), StateMessage tipo «vacío» | RN-XIV |
| Configuración | `GET /usuarios/me`, `PATCH /usuarios/me/preferencias` | Filas de ajustes, interruptores, BottomNav | RN-XVI-01 a XVI-03 |
| Editar perfil y Selector de foto | `PATCH /usuarios/me`, `PUT` y `DELETE /usuarios/me/avatar` (la foto se sube directo a Storage) | TextField, BottomSheet, ActionItem | RN-I-02, IX-07 |
| Cambiar contraseña | `POST /usuarios/me/contrasena/verificar` y `/contrasena` | TextField, Requirement | RN-IX-05 |
| Gestionar correo | Supabase Auth (`updateUser`) | TextField, InlineNotice | RN-IX-06 |
| Establecer meta | `GET /meta`, `POST /metas` | Metric, Chip (tipo), Button | RN-XVI-04 |
| Configurar tarifa | `GET /tarifa`, `POST /tarifas` | Select + BottomSheet + OptionItem (operador; mes y año) | RN-XVI-05 |
| Fuentes de datos | `GET /fuentes-datos` | DataSourceRow | RN-XVI-06 |
| Miembros e Invitar | `GET /miembros`, `PATCH /permisos`, `POST` y `DELETE /invitaciones`, expulsar, transferir, salir | PendingInvite, ActionItem, ConfirmDialog | RN-X-05 a X-08, XVI-07 |
| Eliminar cuenta | `DELETE /usuarios/me` | ConfirmDialog | RN-IX-09 |

## 4. Estructura de carpetas de `app/`

```
app/
  src/
    app/                 # rutas de expo-router (una carpeta por flujo: (auth), (onboarding), (tabs))
    screens/             # una carpeta por pantalla: <ScreenName>.tsx + use<ScreenName>Data.ts
    components/          # los 31 del sistema de diseño, con los mismos nombres (Metric, StatusBadge…)
    theme/               # tokens.ts generado desde tokens.json (no a mano), fonts.ts
    texts/               # catalogo.es-CO.json + t() + plurales
    api/                 # cliente HTTP con el JWT, tipos generados desde el contrato 0.2.5
    format/              # formatNumber, formatCOP, formatPercent, relativeTime (es-CO)
    state/               # React Query (servidor) y sesión (Supabase)
  assets/fonts/          # Inter y JetBrains Mono; satoshi/ va en .gitignore (DC-06)
```

**Nombres en el código (decisión del 10/11/2026):** carpetas, archivos, variables y funciones en inglés, con la convención de cada lenguaje (`camelCase` para variables y funciones, `PascalCase` para componentes y tipos). No se renombran el contrato, las tablas, la documentación ni el catálogo es-CO. Los nombres de archivo de `src/app/` definen las rutas y **se quedan en español** (decisión del 10/11/2026: son direcciones, como las rutas del contrato; `BottomNav` y el enlace `zentheris://invitacion` ya las usan). La ruta `catalogo-componentes` es interna: solo existe en desarrollo.

### ¿Dónde va cada cosa?

| Quiero… | Va en… |
|---|---|
| Una pantalla nueva | `src/screens/<ScreenName>/`: la vista y su hook de datos |
| Que esa pantalla tenga dirección | un archivo en `src/app/` (solo enruta; el nombre queda en español) |
| Un componente del sistema de diseño | `src/components/<Name>/` |
| Un color, un tamaño o una tipografía | No se escribe a mano: se usa un token de `src/theme/` |
| Un texto que ve la persona | El catálogo, con `t('clave')` (`src/texts/`). Si falta la clave, se pide al equipo |
| Mostrar un número, un porcentaje o pesos | `src/format/` |
| Llamar a la API | `src/api/`: una función por operación del contrato |
| Datos del servidor o la sesión | `src/state/` |
| Un ícono | Lucide, aplicado pantalla por pantalla |
| Un gráfico | `react-native-gifted-charts`; si no sirve, Victory Native; si tampoco, a mano con `react-native-svg` |

## 5. Receta para construir una pantalla

1. Abre la fila de la pantalla en el punto 3.
2. Genera o actualiza los tipos desde el contrato (no los escribas a mano).
3. Crea el hook de datos (`use<ScreenName>Data`) con React Query. Debe manejar 4 estados: **cargando** (`Skeleton`), **error** (`InlineNotice` con Reintentar y la clave `error.app.*`), **sin permiso** y **con datos**.
4. Arma la vista solo con componentes del sistema de diseño.
5. Textos: todos con `t('clave')`. Si falta una clave, **no la inventes**: pídela al equipo y regístrala en el catálogo.
6. Revisa los estados de la sección 7.3 de las reglas que aplican a tu pantalla (sin datos, sin tarifa, sin meta, sin referencia, solo lectura).
7. Compara con la pantalla de Figma (A y M) y con el checklist del punto 8.

## 6. Errores y estados de red (DC-16)

| Situación | Clave del catálogo |
|---|---|
| Sin internet | `error.app.sin_conexion` |
| 401 | `error.app.sesion_vencida` → volver a Iniciar sesión |
| 403 `SIN_PERMISO_*` | `StateMessage` sin permiso (no es un error rojo) |
| 404 | `error.app.no_encontrado` |
| 409 o 422 con `codigo` | `error.<codigo en minúsculas>` |
| 5xx | `error.app.error_servidor` |
| Más de 15 s (60 s en onboarding) | `error.app.tiempo_agotado` |

## 7. Refactorizar el prototipo (`Thomasvtf/Zentheris-Prototype`, `app/`)

Lectura estática del zip de `main` del 03/11/2026. **No se ejecutó.** Antes de empezar, confirma la rama y el último commit. **Se refactoriza en el mismo repositorio** (DC-55), en ramas `<tipo>/<descripcion>` que salen de `main` (decisión del 10/11/2026: sin `chore`; las ramas personales del equipo siguen con `<Persona>/feat-<Tema>`). No se crea un repositorio nuevo: se conservan el historial, el CI y la configuración de Expo, y se reescriben las pantallas.

| Qué hay hoy | Qué hacer | Por qué |
|---|---|---|
| Expo ~57, React Native 0.86.3, React 19.2.3, expo-router, supabase-js, React Query y react-native-svg | **Conservar.** Verificar que `expo install --check` no reporte conflictos | Base correcta |
| `@react-navigation/*` en dependencias | Revisar si siguen haciendo falta: desde el SDK 56, expo-router ya no depende de React Navigation (hay codemod) | Evitar imports rotos |
| Colores fijos en `_layout.tsx` (`#00E676`, `#64748B`, `#162B25`) | Cambiarlos por tokens (`accent-primary` #5DD39E, `text-muted`, `background-surface`) | Regla 2 |
| Íconos de la barra exportados de Figma como SVG, activos de 50 px e inactivos de 20 px | Usar `BottomNav` con Lucide (`house`, `clock`, `layout-grid`, `lightbulb`, `settings`) a 24 px. **Se instala en el esqueleto y se aplica después**, con aprobación del cambio visual | DC-13, DC-14 |
| Gráficos dibujados a mano con `react-native-svg` en las ramas de pantallas | Instalar `react-native-gifted-charts`; si no sirve para un gráfico, Victory Native; si tampoco, hecho a mano con `react-native-svg`. Se conservan los actuales como referencia visual hasta migrarlos | DC-12 (orden de respaldo ampliado el 10/11/2026) |
| `constants/theme.ts` y `components/` de la plantilla de Expo (`themed-*`, `hint-row`, `web-badge`) | Borrar después de migrar; no hay tema claro (un solo tema oscuro) | Ruido de plantilla |
| Pantallas `historial`, `zonas`, `consejos`, `configuracion` de 21 líneas y `DashboardScreen` | Reescribirlas con la receta del punto 5 | Son marcadores |
| Carpetas `.kilo/worktrees/` (en la raíz y en `app/`) | Borrarlas del repositorio y añadirlas a `.gitignore` | Copias duplicadas de `api/` |
| Sin Satoshi | Aplicar DC-06 (`.gitignore` + `.easignore` + respaldo en Inter) | Licencia |

**Decisión del 10/11/2026:** el esqueleto instala y configura las librerías, los tokens y el catálogo, pero **no cambia las pantallas existentes**; eso se hace después, pantalla por pantalla.

**Orden sugerido:** (1) tokens, fuentes y textos; (2) los 31 componentes; (3) autenticación y onboarding; (4) Panel; (5) Historial; (6) Zonas; (7) Consejos y Alertas; (8) Configuración y subpantallas.

## 8. Checklist de cada PR de pantalla (para revisar lo que haga Claude Code)

- [ ] Ningún texto ni color escrito a mano.
- [ ] Los 4 estados: cargando, error, sin permiso y datos. Además, los de la sección 7.3 que apliquen.
- [ ] Números con el formato es-CO y la unidad correcta; `null` → «—».
- [ ] El estado nunca se comunica solo con color.
- [ ] Áreas táctiles de 44 pt o más y etiquetas accesibles.
- [ ] Probado en Expo Go en Android **y** en iOS. Si no, decirlo en el PR.
- [ ] El PR cita las reglas (RN-…) y el endpoint que usa.

## 9. Cómo pedirle una pantalla a Claude Code

> «Lee `CLAUDE.md`, `app/CLAUDE.md` y, en `docs/`: reglas v4.9 §6.X y las RN de la pantalla, el endpoint `<operationId>` del contrato, las fichas de `<Componentes>` y las claves `<prefijo>.*` del catálogo. Propón un plan con archivos y estados. Después, implementa la pantalla con sus 4 estados y su prueba. No inventes textos ni colores.»

Revisa el resultado con el checklist del punto 8 y en Expo Go, en Android y en iOS.
