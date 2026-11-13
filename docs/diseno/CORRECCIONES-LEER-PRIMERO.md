# Correcciones vigentes sobre las fichas del sistema de diseño (leer antes de usar `componentes/`)

Las fichas de `componentes/*.md` y `README-sistema-de-diseno.md` son copia del artifact «Zentheris» (versión `1793682992-9b87`, 02/11/2026). Algunas frases quedaron atrás de las decisiones del 03/11/2026. **Cuando una ficha contradiga esta lista, gana esta lista** (registro DC, `docs/decisiones/`).

| Ficha o sección | Dice | Lo vigente |
|---|---|---|
| README › Color; BarChart; PeakMarker; `index.d.ts` | Pico «amarillo», «D12», «pendiente de ratificar» y marcador con `accent` | Pico en **rojo claro `z-color-chart-peak` (#F59099), D17**. Etiqueta «Pico» de la opción A de PeakMarker. Sin componentes ni palabras de estado en el pico (RN-XIII-03) |
| README › Iconografía; ZoneTile | Íconos de Lavandería, Terraza, Garaje y Cuarto de servicio «sin aprobar» | Aprobados: `washing-machine`, `fence`, `car`, `door-closed` (D15, DC-14) |
| README › Iconografía; BottomNav | Historial «por confirmar» | `clock` (DC-13) |
| Icon; StatusBadge; AlertItem | `triangle-alert` | Usar el export que traiga `lucide-react-native` instalado. El nombre canónico actual es `triangle-exclamation-point` (DC-14) |
| README › Contenido; ConsumptionCard; StateMessage; TipList; ConfirmDialog | «Microcopy propuesto» y «catálogo pendiente» | **Todos los textos salen de `docs/textos/catalogo.es-CO.json`** (catálogo v1 aprobado). Ejemplo: el crítico es «Apaga los equipos que no necesites.» |
| ConsumptionCard | «Umbrales no definidos» | Definidos en `docs/datos/umbrales-estado.v1.json`. El componente **recibe** el estado; no lo calcula |
| BarChart › Pendiente | Librería de gráficos sin elegir | `react-native-gifted-charts`, con prueba mínima previa (DC-12) |
| Gráficos de consumo | Solo `ZoneDonutChart`, `BarChart` y `PeakMarker` tenían ficha | Desde el 11/11/2026 también `ConsumptionGauge`, `ConsumptionRing` y `LineChart`, escritas desde Figma. Gauge y anillo de consumo, a mano con `react-native-svg`; relleno del arco aprobado el 11/11/2026 (DC-63) |
| README › Componentes v4.5 | «Propuestos, no aprobados» | Aprobados en general por Nicolás (02/11/2026) junto con las pantallas v4.5 |
| Chip › Pendiente | Radio `sm` o `full` | `z-radius-full` (píldora), como en Figma |
| Button › Pendiente | Variante fantasma por confirmar | Sin borde y con texto `z-color-text-accent`. Solo para acciones terciarias |
| README › Tipografía | Satoshi no se incluye | Igual. Cargar desde `app/assets/fonts/satoshi/` (fuera de git) con respaldo en Inter (DC-06) |

**Tokens:** usa `tokens.json` y `tokens.css` de esta carpeta. Los del kit v3.2 (`tokens.ts` del 30/10) **no traen `chart-peak`** y están desactualizados (DC-58).

**Formato y helpers:** `formatNumber`, `formatCOP`, `formatPercent` y `DECIMALES` de `index.d.ts` son la firma que debe reproducir `app/src/format/`.
