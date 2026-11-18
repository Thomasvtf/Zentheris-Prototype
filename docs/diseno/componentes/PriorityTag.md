# PriorityTag

Etiqueta de prioridad de un consejo, solo con acento y neutros. Figma: `Estado/Prioridad` (4086:366).

## Propiedades
`prioridad`: `'alta' | 'media' | 'baja'`. Texto: «Alta prioridad», «Media prioridad», «Baja prioridad» *(propuesto; sigue el ejemplo «Alta prioridad» de la v4.5 §6.8)*.

## Tokens
| Prioridad | Fondo | Borde | Texto |
|---|---|---|---|
| alta | `z-color-accent-soft` | `z-color-border-accent` | `z-color-text-accent` |
| media | — | `z-color-border-medium` | `z-color-text-muted` |
| baja | — | `z-color-border-subtle` | `z-color-text-muted` |

`body-xs-medium`, `z-radius-full`. **Pendiente:** el kit lista estos tokens para el componente pero no dice cuál va con cada prioridad; este reparto es una lectura y debe confirmarse. Media y baja se distinguen por la palabra, no por el borde (ambos bordes son decorativos).
