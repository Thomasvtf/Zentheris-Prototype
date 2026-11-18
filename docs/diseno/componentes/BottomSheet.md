# BottomSheet

Hoja inferior común a Android e iOS sobre `z-color-background-overlay`: selector de foto, menú de acciones del miembro, selector de operador y de mes y año. Figma: `Navegacion/Hoja-inferior` (4111:446; Tipo = Acciones | Encabezado). **Propuesto v4.5**.

| Prop | Tipo | Notas |
|---|---|---|
| `titulo` | texto | `display-m` 20. |
| `descripcion` | texto | Opcional, `body-s` muted. |
| `onCerrar` | función | Botón cerrar con área 48 y etiqueta «Cerrar». |
| `children` | nodos | `ActionItem`, `OptionItem` o una cuadrícula de `Chip`. |

## Tokens
Fondo `z-color-background-surfaceAlt` (antes elevated; cambio aprobado por Nicolás el 2026-11-02 por mejor visibilidad), radio superior `z-radius-xl`, tirador 40 × 4 `z-color-text-muted`, padding 8/16/32 (32 incluye un área segura aproximada: **verificar en Android e iOS**). Sin sombras.
