Zentheris es una app móvil (Android e iOS, React Native + Expo) para ver y reducir el consumo de energía de un hogar. El MVP usa **datos simulados**. La identidad es oscura, limpia y con acento verde: el número va primero, el estado nunca se dice solo con color y rojo y amarillo solo significan severidad.

Este sistema es la base reutilizable (tokens, tipografía, componentes, íconos, gráficos y estados). **No es un catálogo de pantallas aprobadas.**

## Principios

1. **Una pregunta por pantalla.** Panel: «¿cómo voy ahora y hoy?» · Historial: «¿cómo he consumido y cómo me comparo?» · Zonas: «¿qué pasa en cada zona?» · Consejos: «¿qué puedo hacer para ahorrar?» · Alertas: «¿qué ha pasado?» · Configuración: «¿cómo ajusto mi cuenta, hogar y preferencias?».
2. **El número primero.** Valor grande en JetBrains Mono, unidad pequeña al lado en `z-color-text-muted` y referencia temporal explícita.
3. **Estado = color + ícono + palabra.** Nunca solo color.
4. **Verde para avanzar; amarillo y rojo solo para severidad.** Nunca como categoría, zona ni prioridad.
5. **Ausencia no es cero.** Sin datos se muestra «—»; cero se muestra «0,00 kW».

## Contenido

- Español de Colombia, tuteo, frases cortas e imperativas en los mensajes de estado («Revisa qué equipos están encendidos.»).
- **Formato es-CO (RN-XII-08):** coma decimal y punto de miles. Decimales por unidad: **kW con 2** («2,40 kW», «0,62 kW»), **kWh con 1** («145,3 kWh»), **COP sin decimales** («$14.400»). En cards y ejes, los miles se abrevian con «k» minúscula («$6,5k»). Porcentajes con espacio: «34 %». Es presentación: no altera cálculos.
- **kW** = promedio de la última hora completa. **kWh** = energía de un periodo. Nunca se mezclan en la misma cifra ni se cambian por color.
- Cada cifra con su periodo: «Última hora completa (14:00–15:00)», «Hoy hasta las 15:00», «Semana: lun–hoy». Horas «14:00» u «00h»; fechas «DD/MM».
- **COP solo con tarifa vigente.** Sin tarifa: se oculta el selector COP y se muestra «Configura tu tarifa»; los kWh siguen visibles.
- «Costo estimado» y «Proyección al cierre» son estimaciones; avisar que pueden no incluir subsidios ni otros cobros.
- «Crítico», nunca «sobreconsumo».
- Zonas (orden alfabético): Baño, Cocina, Cuarto de servicio, Dormitorio, Garaje, Lavandería, Oficina, Sala, Terraza.
- Los textos por estado están **fijados por variante** del componente; no se escriben a mano en cada pantalla. Todo el microcopy de este sistema es **propuesto** (microcopy de trabajo): el catálogo definitivo de textos está pendiente.

## Color

Un solo tema: oscuro. No hay tema claro en el alcance.

| Rol | Token | Valor |
|---|---|---|
| Fondo de pantalla | `z-color-background-default` | #0D1F1A |
| Card, input, navegación | `z-color-background-surface` | #162B25 |
| Superficie alternativa (campo de texto, hoja inferior, diálogo de confirmación) | `z-color-background-surfaceAlt` | #1A312A |
| Elevada (tooltip de gráfico, esqueleto de carga) | `z-color-background-elevated` | #1F3B32 |
| Texto principal / secundario | `z-color-text-primary` / `z-color-text-muted` | #FFFFFF / #C4D4CF |
| Acento (CTA, dato, activo) | `z-color-accent-primary` | #5DD39E (presionado #2F8A68) |
| Fondo de acento (chip activo, pestaña activa) | `z-color-accent-soft` | #163B30 |
| Normal / informativa | `z-color-status-success-*`, `z-color-status-info-*` | verde |
| Elevado / advertencia | `z-color-status-warning-*` | amarillo |
| Crítico / error | `z-color-status-error-*`, `z-color-text-error` | rojo |

- Texto informativo: `z-color-text-primary` o `z-color-text-muted` (cumplen 4,5:1 sobre todos los fondos). `z-color-text-disabled` solo en controles deshabilitados. Placeholders en `z-color-text-muted`.
- Texto de error y la palabra «Crítico» en `z-color-text-error` (#F59099). `z-color-status-error-default` (#EF4444) es para íconos, bordes y barras: como texto pequeño no cumple.
- `z-color-border-subtle` y `z-color-border-medium` son decorativos (< 3:1): un control también se reconoce por su fondo y su etiqueta. `z-color-border-strong`, `-accent`, `-error`, `-warning` y el anillo de foco cumplen 3:1.
- Los traslúcidos llevan el alfa en el valor (#RRGGBBAA). No aplicar además opacidad de capa.
- Sin sombras: la elevación se expresa con el nivel de superficie y los bordes.
- Gráficos: serie principal `z-color-chart-series1`; comparación `z-color-chart-series5` o `-series2`; `-series3` (amarillo) y `-series4` (rojo) **solo para estado** (elevado y crítico). El pico más alto del periodo usa color propio (rojo claro, D17, RN-XIII-03 de la v4.9): su barra o punto va en `z-color-chart-peak` (#F59099) y lleva la etiqueta «Pico» en `z-color-accent-soft` con texto y borde `z-color-chart-peak` (RN-XIII-03; ver `BarChart` y `PeakMarker`). La etiqueta opción A está en uso; la opción B (contorno punteado) queda como alternativa. Rejilla `z-color-chart-grid`, etiquetas `z-color-chart-label`.

Los contrastes citados son indicadores calculados con la fórmula WCAG; no certifican accesibilidad.

## Tipografía

| Rol | Familia | Estilos |
|---|---|---|
| Display (títulos) | Satoshi Bold | `display-xl` 32 · `display-l` 28 · `display-l-24` 24 · `display-m` 20 · `display-s-16` 16 |
| Body (texto) | Inter Regular / Medium | `body-m-*` 16 · `body-s-*` 14 · `body-xs-*` 12 · `body-xs-*-10` 10 |
| UI (controles) | Inter Semi Bold | `ui-m-semibold` 16 · `ui-s-semibold` 14 · `ui-s-semibold-12` 12 · `ui-s-etiqueta-12` |
| Data (cifras) | JetBrains Mono Bold | `data-xl-32` 32 (KPI) · `data-l` 24 · `data-m` 20 · `data-s-16` 16 · `data-s` 12 · `data-s-mono-regular-12` (ejes) |

- Toda métrica usa Data aunque sea pequeña; un título nunca usa Data.
- Valor + unidad: valor en Data, unidad en Body más pequeña y `z-color-text-muted`.
- Ejes y horas en `data-s-mono-regular-12` con `z-color-chart-label`; leyendas en Body XS.
- Body 10 (`body-xs-*-10`): solo etiquetas secundarias ya existentes (barra inferior). Evitarlo en textos nuevos; validar legibilidad en dispositivo. Nunca 8 px.
- El token primitivo `z-font-size-data-xl` vale 36 pero el KPI ratificado es 32 (`data-xl-32`). Usar el estilo, no la primitiva.
- **Satoshi no se incluye en este sistema** (licencia ITF FFL: no se sube a servidores públicos). Cada persona la descarga de fontshare.com. En estas vistas previas los títulos caen a Inter si Satoshi no está instalada en el equipo. Inter y JetBrains Mono se cargan de Google Fonts (SIL OFL 1.1).
- En React Native, `lineHeight` va en px (tamaño × interlineado) y las fuentes se cargan con `expo-font`; límite de escalado ≈ 1,3 en cifras grandes *(propuesto)*.

## Espacio, radios y medidas

- Escala de espacio `z-space-4` … `z-space-64`. Padding de card `z-size-card-padding` (16); margen lateral de pantalla `z-size-grid-margin` (20); grilla de 4 columnas con medianil `z-size-grid-gutter` (16).
- Radios: `z-radius-xs` 4 (insignias, esqueleto) · `z-radius-sm` 8 (contenedor de pestaña activa) · `z-radius-md` 10 (botón, campo, bloque de estado, card de consejo) · `z-radius-lg` 16 (cards de datos) · `z-radius-xl` 20 · `z-radius-full` (píldoras).
- Ancho mínimo **375** y diseño adaptable (`z-size-screen-minWidth`); `z-size-screen-width` = 402 está en desuso. Cards a todo el ancho disponible, no a anchos fijos. En anchos > 430, ancho máximo de contenido 560 centrado *(propuesto)*.
- Barra superior `z-size-topBar-height` (56) y barra inferior `z-size-bottomNav-height` (64), más las áreas seguras de cada sistema. El contenido desplazable deja abajo el alto de la barra + el área segura.
- Botón y campo: alto `z-size-button-height` (48).

## Interacción y accesibilidad

- **Áreas táctiles ≥ 44 × 44 pt (iOS) y 48 × 48 dp (Android)**, con padding o `hitSlop`, no agrandando el glifo. Separación mínima de 8 entre objetivos. El botón de ícono mide 36 visual (`z-size-iconButton-size`) y necesita área ampliada.
- Presionado: `z-color-accent-primaryActive` (rellenos) o `z-color-state-active-bg`. Seleccionado: `z-color-accent-soft` + `z-color-border-accent` + `z-color-text-accent`. Foco: anillo de 2 px `z-color-state-focus-ring`. Deshabilitado: `z-color-state-disabled-*`.
- Íconos interactivos con etiqueta accesible en español («Abrir alertas, 3 sin leer»); íconos decorativos ocultos al lector.
- Cada gráfico expone un resumen textual.
- Respetar «reducir movimiento» y el tamaño de fuente del sistema; evitar alturas fijas en cards.
- Verificado: solo en diseño (contrastes de tokens y tamaños). **No hay pruebas en Android, iOS, TalkBack, VoiceOver ni con texto grande.**

## Iconografía

- Biblioteca: **Lucide** (ISC), trazo 2 px, extremos y uniones redondeados. Escala 16 · 20 · 24 · 32 ligada al contenedor (ver el componente `Icon`). En código, `lucide-react-native`.
- Los nombres Lucide del proyecto son **«probables»**: en Figma los glifos están aplanados. Verificar cada nombre en lucide.dev antes de codificarlo. Los trazos de las vistas previas de este sistema son una reconstrucción aproximada.
- Estados Default · Active · Disabled solo en íconos que se tocan: `z-color-text-muted` · `z-color-accent-primary` · `z-color-text-disabled`.
- Navegación inferior canónica: Principal = casa (opción 1), Historial = opción 3, Zonas = cuadrícula (opción 2), Consejos = bombilla (opción 1), Configuración = engranaje. **Por confirmar:** en la hoja de Figma la opción 3 de Historial es un reloj (`clock`); el glifo `history` (reloj con flecha) es la opción 1. Se usa la opción 3 tal como dice la regla.
- Zonas sin ícono aprobado: Lavandería, Terraza, Garaje, Cuarto de servicio (candidatos sin aprobar: washing-machine, fence o sun, car, door-closed o house).
- v4.5 (02/11/2026): las pantallas para revisión usan los candidatos washing-machine, fence, car y door-closed (Figma `Icono/Zona-boton/*` 4086:470–524 e `Icono/Zona/*` 4045:303–323). Siguen **sin aprobar**.
- Íconos nuevos propuestos (Figma `Icono/Sistema/*` 4109:372–407): chevron-down (Desplegar), lock (Candado), mail (Correo), image (Imagen), log-out (Salir), arrow-right-left (Transferir), circle-pause (Pausa), user-plus (Usuario-agregar). La campana suma la variante «Con no leídas» (punto acento, no rojo).

## Logo

`zentheris-logo-hoja.png` (grupo Logos): hoja verde con rayo amarillo. Usar el archivo original; no redibujarlo, recolorearlo ni usarlo como ícono. El amarillo del rayo es de la marca y no habilita el amarillo en la interfaz fuera de severidad.

## Componentes v4.5 (propuestos, 02/11/2026)

Doce componentes nuevos para las pantallas de la v4.5 §7.1, en Figma (página Components, en su sección) y aquí: `Select`, `OptionItem`, `Requirement`, `ZoneTile`, `StepIndicator`, `ActionItem`, `BottomSheet`, `ConfirmDialog`, `DataSourceRow`, `PendingInvite`, `InvitationCard` y `PeakMarker`. Todos usan solo tokens existentes y son **propuestos**: no están aprobados ni implementados en la app.

- Las hojas inferiores y los selectores son propios y comunes a Android e iOS (no se usan menús ni ruedas nativas).
- Las pantallas nuevas, las actualizadas y los estados están en la copia de trabajo de Figma, página Pantallas, secciones «v4.5 · 7.1 / 7.2 / 7.3 … (para revisión)». Son propuesta de diseño: no demuestran funcionamiento.
- Todo el microcopy de esas pantallas es de trabajo; el catálogo definitivo de textos sigue pendiente (v4.5 §10).


---

## Consuming this system (generated — do not edit)

Every path named below is under `project/` in this design system: read `project/api/tokens.md`, not `api/tokens.md`.

`components/bundle.js` defines `window.Zentheris` (31 components); `components/bundle.css` is its stylesheet; `tokens.css` is every token as a CSS variable plus `@font-face` for the fonts. `components/bundle.css` reads its variables from `tokens.css`. The bundle needs react 18.3.1 (not packed in this system: bring your own copy) (`window.React`), react-dom 18.3.1 (not packed in this system: bring your own copy) (`window.ReactDOM`), loaded before it. Build any UI by mounting these components; never hand-build a control or draw an icon the system provides.

- **Standalone page:** inline `tokens.css` and `components/bundle.css` in a `<style>`, then the library files and `components/bundle.js` as classic scripts (a file containing `</style`, `</script` or `<!--` breaks an inline element: write the sequence `<\/style`, `<\/script` or `\x3C!--` in your copy, or load that file by URL).
- **Design canvas:** bring `tokens.css`, `components/bundle.css`, `components/bundle.js` and `components/index.d.ts` (for the editor’s props panel) onto the canvas in full, as the canvas type’s design-system components reference says (a server-side copy first where it offers one); in each artboard that uses this system, right after the `support.js` line, load `tokens.css` first, then the stylesheet, then the script; skip the library files (the artboard supplies React); mount with `<x-import component-from-global-scope="Zentheris.<Comp>" …>`.
- **Slides deck, or any surface that cannot run the bundle:** tokens only — the values are on `api/tokens.md`; the deck takes `tokens.json` by file path for its colour pickers.

**Read, per thing:** a component’s props, parts and examples: `api/components/<Comp>.md`; token values: `api/tokens.md`; stored assets and their paths: `api/assets/<Group>.md`. After this README, fetch the cards and fonts you need in ONE message as parallel calls — none depends on another.

**Two rules.** Before you use a thing — a component, a token group, an icon, an asset — read its card from the index below; a value you did not read from a card is a guess. `tokens.json`, `manifest.json`, `components/index.d.ts` and `design-system.json` are sources for tools: hand them over. `components/<Comp>/README.md` and `assets/<Group>/README.md` are the long-form second read a card links to; `SKILL.md` and `artifact-type/` beside them are authoring guidance, not needed to consume the system.

## Index (generated — do not edit)

**Tokens**

- `api/tokens.md` — Every token: surface, text, fill, border, chart, palette, type, spacing, radius, size, font-size, font-weight, line-height. (22.1k)

**Icons and assets**

- `api/assets/Logos.md` — 1 file, by asset id. (1.1k)

**Components** (`api/components/<Comp>.md`, 31)

- **Datos**: `Metric` — Muestra una cifra energética o monetaria con su unidad, en formato es-CO: valor en JetBrains Mono y unidad más pequeña en z-color-text-muted · `DataSourceRow` — Fila de la pantalla Fuentes de datos (antes Medidores), solo lectura (RN-XVI-06) · `PendingInvite` — Invitación pendiente en Miembros del hogar; solo la ve el administrador (RN-X-08, N6) · `InvitationCard` — Invitación recibida por un usuario sin hogar (RN-X-01, RN-X-05, RN-X-06)
- **Estado**: `StatusBadge` — Comunica el estado de consumo (normal, elevado, crítico) con color + ícono + palabra; une Estado/Capsula (2048:2219) y Estado/Texto (514:1168) · `ProgressBar` — Barra de progreso o participación con etiqueta y porcentaje · `StateMessage` — Reemplaza una card de datos o una lista vacía cuando no hay nada que mostrar; saludo, cabecera y selectores siguen visibles · `InlineNotice` — Aviso dentro de una pantalla (no es la campana de alertas): error con reintentar, advertencia, información o éxito · `Skeleton` — Esqueleto de carga con la forma final de la card, sin números ni ejes falsos · `PriorityTag` — Etiqueta de prioridad de un consejo, solo con acento y neutros · `ConfirmDialog` — Confirmación de acciones irreversibles (RN-IX-09, RN-X-06, RN-X-07)
- **Controles**: `Button` — Acción del usuario; el primario (relleno verde con texto oscuro) va como máximo una vez por vista · `Chip` — Selector compacto de opción única: kW/COP, Día/Semana/Mes, filtro de zona · `TextField` — Campo de formulario con etiqueta siempre visible, para registro, contraseña, meta y tarifa · `Select` — Campo desplegable para el operador y la vigencia de la tarifa; abre una BottomSheet con OptionItem o con la cuadrícula de mes y año · `OptionItem` — Opción de una lista dentro de una hoja inferior (operador de la tarifa) · `Requirement` — Requisito de contraseña con ícono + texto (RN-IX-02): registro, restablecer y cambiar contraseña · `ZoneTile` — Zona del catálogo de 9 para el paso 2 del onboarding (RN-X-02, RN-X-09)
- **Cards**: `ConsumptionCard` — Responde «¿cómo va el consumo ahora?» (kW de la última hora completa) o «¿cómo va el día?» (kWh hasta la última hora completa) · `TipCard` — Consejo accionable de la lista de Consejos, con prioridad o marca de completado
- **Listas**: `AlertItem` — Fila de la lista de Alertas: ícono por categoría, título, tiempo relativo y punto de lectura · `TipList` — Lista de Consejos que aplica el orden y el estado vacío de la v4.5: «¡Todo bajo control!» solo aparece cuando no hay consejos pendientes
- **Navegación**: `ScreenHeader` — Cabecera de pantalla con título centrado, botón atrás y campana de alertas · `BottomNav` — Barra inferior de cinco secciones con una única pestaña activa por pantalla · `StepIndicator` — Progreso del onboarding: paso 1 = nombre del hogar y tipo de vivienda; paso 2 = zonas · `ActionItem` — Fila de acción dentro de una BottomSheet: selector de foto y menú de acciones del miembro · `BottomSheet` — Hoja inferior común a Android e iOS sobre z-color-background-overlay: selector de foto, menú de acciones del miembro, selector de operador y de mes y año
- **Gráficos**: `ZoneDonutChart` — Anillo que responde «¿qué zonas pesaron más en el periodo?», solo con el filtro General (RN-XIII-04) · `BarChart` — Barras de consumo del periodo con el pico más alto marcado con la etiqueta «Pico» y color propio (rojo claro #F59099) · `PeakMarker` — Marcador del pico más alto del periodo en barras y línea (RN-XIII-03, D5) · `ConsumptionGauge` — Medidor semicircular del consumo actual (ficha añadida el 11/11/2026 desde Figma; a mano con react-native-svg) · `ConsumptionRing` — Anillo de un solo valor con el número en el centro, segunda vista del consumo actual (ficha añadida el 11/11/2026; a mano con react-native-svg) · `LineChart` — Línea de consumo del periodo con pico marcado (ficha añadida el 11/11/2026; gifted-charts). Estas tres fichas no están en el `bundle.js` de 31 componentes
- **Íconos**: `Icon` — Glifo de interfaz estilo Lucide (trazo 2, extremos redondeados) con tamaño de la escala 16 · 20 · 24 · 32
