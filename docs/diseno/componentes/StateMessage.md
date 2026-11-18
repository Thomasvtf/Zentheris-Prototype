# StateMessage

Reemplaza una card de datos o una lista vacía cuando no hay nada que mostrar; saludo, cabecera y selectores siguen visibles. Figma: `Estado/Mensaje` (4086:416).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `tipo` | `'sin_datos' \| 'sin_permiso' \| 'sin_tarifa' \| 'sin_referencia' \| 'vacio' \| 'todo_bajo_control'` | `todo_bajo_control` solo a través de `TipList`. |
| `recurso` | texto | Solo sin permiso: completa «No tienes permiso para ver…». |
| `titulo`, `descripcion` | texto | Sobrescriben el texto por defecto (p. ej. vacío de Consejos). |
| `accion`, `onAccion` | texto, función | Enlace de acción (`ui-s-semibold-12`, `z-color-text-accent`, área 48). |

## Textos por estado *(propuestos)*
| Tipo | Ícono | Título | Descripción |
|---|---|---|---|
| sin_datos | clock | Sin datos | La lectura de la última hora aún no llega. Se actualizará en la próxima hora. |
| sin_permiso | shield | No tienes permiso para ver… | Pídele acceso al administrador del hogar |
| sin_tarifa | coins | Configura tu tarifa | — (con acceso a Configurar tarifa; los kWh siguen visibles) |
| sin_referencia | info | Sin referencia | Aún no tenemos suficiente historial para comparar. |
| vacio | bell | No tienes alertas | — (RN-XIV-09) |
| todo_bajo_control | circle-check | ¡Todo bajo control! | — |

«¡Todo bajo control!» **solo aparece cuando no hay consejos pendientes**; debajo se ven los completados aún visibles, atenuados. Con pendientes no se muestra (RN-XV-02, D1). Usar `TipList`, que aplica la regla, en vez de colocar este mensaje a mano.

## Tokens
`z-color-background-surface`, `z-color-border-subtle`, `z-radius-lg`, padding `z-size-card-padding`; ícono 32 en `z-color-text-muted`; título `body-s-medium` primary; descripción `body-xs` muted.
