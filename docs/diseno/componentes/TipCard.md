# TipCard

Consejo accionable de la lista de Consejos, con prioridad o marca de completado. Figma: `Card/Consejo` (4086:383).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `estado` | `'pendiente' \| 'completado'` | Completado = estado individual, no prioridad. Se muestra atenuado (sin fondo, título en `z-color-text-muted`) y al final de la lista. |
| `prioridad` | `'alta' \| 'media' \| 'baja'` | Alta = zona en crítico; media = zona en elevado; baja = cierre de mes sobre la referencia. |
| `titulo`, `descripcion` | texto | |

## Tokens
`z-color-background-surface`, `z-color-border-subtle`, `z-radius-md`, padding `z-space-16`; título `body-m-medium`; descripción `body-s-regular` muted; completado: circle-check 16 + «Completado» en `z-color-text-success`.

## Reglas
- La prioridad nunca usa rojo ni amarillo.
- Un consejo **pendiente** se muestra durante su vigencia: 7 días desde su creación (RN-XV-05, D10). Vencida, deja de mostrarse.
- Un consejo **completado** se oculta 7 días después de completarse; si la persona lo desmarca antes, vuelve a pendiente (RN-XV-03). No se borra el registro.
- El orden y la card «¡Todo bajo control!» los resuelve `TipList` (RN-XV-02, RN-XV-04); no armar la lista a mano.
- La casilla para marcar completado aún no está diseñada.
