# ConsumptionCard

Responde «¿cómo va el consumo ahora?» (kW de la última hora completa) o «¿cómo va el día?» (kWh hasta la última hora completa). Figma: `Card/Consumo/Actual` (2045:547) y `Card/Consumo/Acumulado-hoy` (2045:1281).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `tipo` | `'actual' \| 'hoy'` | actual → kW; hoy → kWh. |
| `estado` | `'normal' \| 'elevado' \| 'critico' \| 'sin_datos' \| 'sin_referencia' \| 'sin_permiso' \| 'cargando'` | |
| `valor` | `number \| null` | `null` o `sin_datos` → «—». |
| `periodo` | texto | Referencia temporal obligatoria: «Última hora completa (14:00–15:00)», «Hoy hasta las 15:00». |
| `comparacion` | texto | Declara su referencia: «que la hora anterior», «que el promedio de esta hora». Se oculta sin referencia o sin datos. |
| `tendencia` | `'sube' \| 'baja'` | Ícono trending-up/down 16. |
| `progreso`, `limite` | `number` | Solo `tipo="hoy"`. `limite` (y el texto «Límite») solo si la persona compara contra meta (`base_comparacion = meta`) y hay meta activa; en otro caso no se pasa y la barra va contra el promedio de lo acumulado a esa hora (RN-XI-04, D6). |
| `decimales` | `number` | No pasarlo: kW 2 y kWh 1 por defecto (RN-XII-08). |

## Anatomía y tokens
Contenedor: `z-color-background-surface`, borde `z-color-border-subtle`, radio `z-radius-lg`, padding `z-size-card-padding`, ancho FILL (335 a 375 px).
1. Encabezado: ícono zap 24 en contenedor 40 `z-color-accent-soft` + `z-color-accent-primary`; título `body-s-medium`; periodo `body-xs-regular` muted; StatusBadge (sin ícono).
2. Valor: Metric `xl` (`data-xl-32`), unidad `body-s` muted, con los decimales de su unidad («2,40 kW», «3,1 kWh»). Si no cabe en 320 px, bajar a `data-l`.
3. Comparación `body-xs` muted.
4. Divisor `z-color-border-subtle`.
5. Bloque de estado: fondo/borde `z-color-status-*-bg|border`, ícono 16 de severidad, título `ui-s-semibold` en color de estado, mensaje `body-xs` muted.

## Textos por estado *(propuestos, microcopy de trabajo)*
| Estado | Cápsula | Título | Mensaje |
|---|---|---|---|
| normal | Normal | Dentro de lo habitual | Vas bien, sigue así. |
| elevado | Elevado | Consumo elevado | Revisa qué equipos están encendidos. |
| critico | Crítico | Consumo crítico | Apaga los equipos que no estés usando. |
| sin_datos | — | Sin datos | La lectura de la última hora aún no llega. Se actualizará en la próxima hora. |
| sin_referencia | — | Sin referencia | Aún no tenemos suficiente historial para comparar. |
| sin_permiso | (la card se reemplaza) | No tienes permiso para ver el consumo actual | Pídele acceso al administrador del hogar |

Los umbrales de normal/elevado/crítico no están definidos (RN-XI-07): la card recibe el estado, no lo calcula. COP solo con tarifa vigente. Las etiquetas de la barra («Frente a tu límite diario», «Frente a tu promedio diario») son propuestas.
