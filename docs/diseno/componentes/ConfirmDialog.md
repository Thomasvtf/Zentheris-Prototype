# ConfirmDialog

Confirmación de acciones irreversibles (RN-IX-09, RN-X-06, RN-X-07). Figma: `Dialogo/Confirmacion` (4111:463). **Propuesto v4.5**.

| Prop | Tipo | Notas |
|---|---|---|
| `titulo`, `descripcion` | texto | Pregunta concreta y consecuencia. |
| `tono` | `'destructivo' \| 'normal'` | Destructivo: botón `destructivo`; normal: `primario`. |
| `confirmar`, `cancelar` | texto | Botón principal arriba y «Cancelar» abajo, a todo el ancho (mismo orden en Android e iOS). |

## Tokens
Fondo `z-color-background-surfaceAlt` (antes elevated; cambio aprobado por Nicolás el 2026-11-02 por mejor visibilidad), borde `z-color-border-subtle`, radio `z-radius-lg`, padding 24.

## Casos (textos propuestos)
| Caso | Tono | Botón |
|---|---|---|
| Eliminar cuenta | destructivo | Eliminar cuenta |
| Eliminar cuenta siendo el único miembro (se elimina el hogar) | destructivo | Eliminar cuenta y hogar |
| Administrador con otros miembros (`ADMIN_DEBE_TRANSFERIR`) | normal | Ir a Miembros del hogar |
| Expulsar miembro | destructivo | Expulsar |
| Transferir administración | normal | Transferir administración |
| Cancelar invitación | destructivo | Cancelar invitación / Volver |
| Salir del hogar | destructivo | Salir del hogar |
