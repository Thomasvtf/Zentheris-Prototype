# ScreenHeader

Cabecera de pantalla con título centrado, botón atrás y campana de alertas. Figma: `Navegacion/Cabecera` (483:114).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `titulo` | texto | `display-l-24` (Satoshi Bold 24), `z-color-text-primary` (Figma usa `chart/label`: cambio E2-04). |
| `onAtras` | función \| `false` | `false` oculta el botón. Mismo destino que el gesto o tecla atrás del sistema. |
| `campana` | `boolean` | Solo si el usuario tiene permiso de recibir alertas (RN-XII-02). |
| `noLeidas` | `number` | Indicador + etiqueta «Abrir alertas, 3 sin leer». |

## Tokens
Alto `z-size-topBar-height` (56) + área segura. Botones de ícono 48 × 48 con glifo 24 (chevrons-left, bell) en `z-color-text-muted`; presionado `z-color-state-active-bg`. Indicador de no leídas en `z-color-accent-primary` (color inferido: confirmar).
