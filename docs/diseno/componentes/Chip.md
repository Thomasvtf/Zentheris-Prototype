# Chip

Selector compacto de opción única: kW/COP, Día/Semana/Mes, filtro de zona. Figma: `Control/Chip` (483:33).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `activo` | `boolean` | Seleccionado (`aria-checked`). |
| `deshabilitado` | `boolean` | |
| `icono` | nombre de ícono | 20 px. |
| `children` | texto | Etiqueta corta. |

En grupo se comporta como radio (`role="radio"` dentro de un `radiogroup`). El chip COP se oculta sin tarifa vigente.

## Tokens
- Inactivo: borde `z-color-border-medium`, texto `z-color-text-muted` (cambio E2-04: hoy Figma usa `border-strong` como texto).
- Activo: `z-color-accent-soft` + borde `z-color-border-accent` + texto `z-color-text-accent`.
- Deshabilitado: `z-color-state-disabled-*`.
- Tipografía `ui-s-semibold`; alto visual 34; **área táctil 48** (contenedor con alto mínimo 48 o `hitSlop`).

## Pendiente
Radio: el token `z-radius-sm` dice «chips», pero Figma dibuja píldora; aquí se usa `z-radius-full`. Confirmar cuál manda.
