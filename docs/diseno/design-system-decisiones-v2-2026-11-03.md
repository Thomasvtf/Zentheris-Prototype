# Sistema de diseño · decisiones v2 (03/11/2026)

Reemplaza en lo que contradiga a `design-system-decisiones-2026-11-02.md`, que queda como antecedente en esta misma carpeta. Fuentes: artifact «Zentheris» (Design System, versión `1793682992-9b87`, leído el 03/11/2026), reglas v4.9 y registro DC.

## 1. Pendientes del sistema de diseño y cómo quedaron

| # | Pendiente (artifact, README o fichas) | Decisión | ID |
|---|---|---|---|
| 1 | Color del pico «amarillo #F59099, pendiente de ratificar» (README, BarChart, `index.d.ts`) | **Rojo claro `#F59099` (D17)**, ratificado. El texto «amarillo» y «pendiente» es un error de redacción heredado. BarChart usa `chart/peak` y la etiqueta «Pico» de PeakMarker (opción A). | DC-15 |
| 2 | Íconos de Lavandería, Terraza, Garaje y Cuarto de servicio «sin aprobar» (README, ZoneTile) | Aprobados (D15): `washing-machine`, `fence`, `car`, `door-closed`. Verificados en lucide.dev. | DC-14 |
| 3 | Ícono de Historial «por confirmar» (`clock` o `history`) | `clock` (opción 3). Además, `history` hoy se llama `rotate-ccw-clock` en Lucide. | DC-13 |
| 4 | Nombres Lucide «probables» | 40/40 existen en lucide.dev (03/11/2026). `triangle-alert` tiene hoy el nombre canónico `triangle-exclamation-point`: en código se usa el export del paquete instalado. | DC-14 |
| 5 | «Todo el microcopy es propuesto; el catálogo definitivo está pendiente» | El catálogo v1 está aprobado (02/11). Las fichas deben citar claves del catálogo, no textos. Diferencias detectadas: ConsumptionCard crítico «…que no estés usando» → catálogo «…que no necesites»; StateMessage sin_referencia → `estado.*.sin_referencia.*`. | DC-21 |
| 6 | «Los umbrales no están definidos (RN-XI-07)» (ConsumptionCard) | Definidos en v1 (`umbrales-estado.v1.json`). La card sigue recibiendo el estado, no lo calcula. | DC-27 |
| 7 | Librería de gráficos sin elegir | `react-native-gifted-charts`, con prueba mínima previa; alternativa: Victory Native. | DC-12 |
| 8 | Cómo cargar Satoshi sin versionarla | `.gitignore` + `.easignore` con `!app/assets/fonts/satoshi/**` y respaldo en Inter. | DC-06 |
| 9 | Estado «todo completado» de Consejos | Existe (A4.4/M4.4). Se corrigió A4.3/M4.3, que mostraba la card con pendientes. | DC-23 |
| 10 | Consejos y Configuración con `Barra-inferior` | Verificado: ya usan `Navegacion/Barra-inferior` con la pestaña activa correcta. | — |
| 11 | Card «Pico» con texto por defecto erróneo | Corregido en el componente y en 8 instancias. | DC-19 |
| 12 | ZoneDonutChart «en laboratorio y sin uso» | Vigente en Historial (D16); su lista debe ordenarse por participación. Corregido en A5.4/M5.4. | DC-22 |
| 13 | StatusBadge en Figma usa #F87171 (fuera de la paleta) | Se mantiene la decisión del 02/11: se corrige en código con los tokens, no en Figma. | — |
| 14 | Body 10, accesibilidad, Android e iOS | Sin cambio: requiere prueba en dispositivo (acción del equipo). | Externo |

## 2. Cambios preparados para el artifact «Zentheris» (no aplicados)

Solo se autorizó tocar Figma. Para aplicar estos cambios al artifact basta con que Nicolás lo pida.

- `project/README.md`, sección Color: cambiar «amarillo #F59099, D12, pendiente de ratificar frente a RN-XIII-03» por «rojo claro #F59099 (D17), con reglas de separación de RN-XIII-03».
- `project/README.md`, Iconografía: quitar «Zonas sin ícono aprobado…» y «Siguen sin aprobar»; poner «Aprobados (D15) y verificados en lucide.dev el 03/11/2026». Quitar «Por confirmar» de Historial (`clock`).
- `project/README.md`, Contenido: cambiar «el catálogo definitivo de textos está pendiente» por «los textos salen del catálogo v1 (aprobado el 02/11/2026)».
- `components/BarChart/README.md`: quitar el párrafo «Pendiente: RN-XIII-03 dice que el pico no usa rojo…» y la propuesta de marcador con `accent`; remitir a PeakMarker (opción A, D17).
- `components/PeakMarker/README.md`: «D12» → «D17».
- `components/ZoneTile/README.md`: «candidatos…, sin aprobar» → «aprobados (D15)».
- `components/BottomNav/README.md`: Historial `clock` sin «por confirmar».
- `components/ConsumptionCard/README.md` y `StateMessage/README.md`: tabla de textos → claves del catálogo; quitar «umbrales no definidos».
- `components/index.d.ts`: comentario de BarChart sin «pendiente de ratificar».
