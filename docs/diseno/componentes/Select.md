# Select

Campo desplegable para el operador y la vigencia de la tarifa; abre una `BottomSheet` con `OptionItem` o con la cuadrícula de mes y año. Figma: `Control/Selector` (4110:394). **Propuesto v4.5 (02/11/2026)**.

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `etiqueta` | texto | Siempre visible; «(opcional)» en la etiqueta cuando aplica (operador, RN-XVI-05). |
| `valor`, `placeholder` | texto | Sin valor: «Selecciona una opción» en `z-color-text-muted`. |
| `estado` | `'default' \| 'abierto' \| 'deshabilitado' \| 'solo_lectura'` | Solo lectura sin chevron: miembros que no son administrador (tarifa) o sin `permiso_modificar_metas`. |
| `onAbrir` | función | Abre la hoja inferior. |

## Decisiones
- Mismo componente en Android e iOS: **no** se usan selectores nativos (rueda iOS / diálogo Android) para que el diseño y las pruebas sean uno solo. Decisión tomada con autonomía delegada; revisable.
- La lista de operadores es un **catálogo propuesto** pendiente (§10 de la v4.5); el texto elegido se guarda en `operador`.
- Vigente desde: mes y año; debe ser posterior a la tarifa vigente (`VIGENCIA_NO_POSTERIOR`); no se eligen meses futuros (propuesto).

## Tokens
Caja 48 (`z-size-button-height`), `z-radius-md`, fondo `z-color-background-surfaceAlt`, borde `z-color-border-medium`; abierto `z-color-border-accent` 2 px; deshabilitado `z-color-state-disabled-*`; solo lectura `z-color-background-surface` + `z-color-border-subtle`. Chevron Lucide `chevron-down` 20.
