# TipList

Lista de Consejos que aplica el orden y el estado vacío de la v4.5: «¡Todo bajo control!» solo aparece cuando no hay consejos pendientes.

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `consejos` | `TipCardProps[]` | Los consejos visibles para la persona (pendientes vigentes y completados de menos de 7 días). El filtrado por vigencia lo hace el backend o la capa de datos. |

## Comportamiento (RN-XV-02, RN-XV-04, decisión D1)
- **Con consejos pendientes:** no se muestra «¡Todo bajo control!». Se ven los pendientes de mayor a menor prioridad (alta → media → baja) y, al final, los completados atenuados.
- **Sin consejos pendientes:** se muestra la card «¡Todo bajo control!» (`StateMessage` tipo `todo_bajo_control`) y debajo los completados aún visibles, atenuados.
- Vigencia de un pendiente: 7 días desde su creación (RN-XV-05). Un completado se oculta a los 7 días (RN-XV-03).

## Tokens
Los de `TipCard` y `StateMessage`; separación `z-space-12`.

## Textos *(propuestos)*
«¡Todo bajo control!» (ejemplo de la v4.5 §6.8; el texto definitivo sale del catálogo).
