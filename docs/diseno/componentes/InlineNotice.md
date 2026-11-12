# InlineNotice

Aviso dentro de una pantalla (no es la campana de alertas): error con reintentar, advertencia, información o éxito. Figma: `Aviso/En-linea` (4086:451).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `tono` | `'error' \| 'advertencia' \| 'informacion' \| 'exito'` | |
| `titulo` | texto | Obligatorio. |
| `descripcion` | texto | Opcional. |
| `onReintentar` | función \| `false` | Solo error: muestra «Reintentar». |

## Tokens
`z-color-status-{error|warning|info|success}-bg`, `-border`, `-text`, `-default` (ícono 16: circle-x, triangle-alert, info, circle-check). Radio `z-radius-md`, padding `z-space-12`. Título `ui-s-semibold`, descripción `body-xs` muted.

## Textos *(propuestos)*
Error de gráfico: «No pudimos cargar el historial» + «Reintentar». Costo: «Puede no incluir subsidios ni otros cobros» (RN-XVI-05). Datos parciales: «Faltan lecturas de n horas».
