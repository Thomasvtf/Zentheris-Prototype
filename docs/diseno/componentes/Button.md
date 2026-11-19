# Button

Acción del usuario; el primario (relleno verde con texto oscuro) va como máximo una vez por vista. Figma: `Control/Boton` (493:32).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `variante` | `'primario' \| 'secundario' \| 'fantasma' \| 'destructivo'` | Primario = Fill; secundario = contorno verde; destructivo = contorno rojo. |
| `estado` | `'normal' \| 'presionado' \| 'deshabilitado' \| 'cargando'` | Cargando: ícono `loader` girando y el texto se conserva. |
| `icono` | nombre de ícono | Opcional, 20 px. |
| `bloque` | `boolean` | Ancho completo (formularios). |
| `children` | texto | Verbo en infinitivo o imperativo breve. |

## Tokens
Alto `z-size-button-height` (48) · radio `z-radius-md` (10) · padding `z-space-16` · tipografía `ui-m-semibold`.
- Primario: `z-color-accent-primary` + `z-color-text-inverse` (9,18:1); presionado `z-color-accent-primaryActive`.
- Secundario: borde `z-color-border-accent`, texto `z-color-text-accent`; presionado `z-color-state-active-bg`.
- Destructivo: borde `z-color-border-error`, texto `z-color-text-error`.
- Deshabilitado: `z-color-state-disabled-bg`, `-text`, `-border`.
- Foco: anillo 2 px `z-color-state-focus-ring`.

## Pendiente
- Fantasma: los tokens (sin borde, texto `z-color-text-accent`) son una lectura de la propuesta del catálogo; confirmar.
- Figma también tiene «Default» (contorno neutro) y «Destructive-compacto»; no están en la propuesta de props.
