# ActionItem

Fila de acción dentro de una `BottomSheet`: selector de foto y menú de acciones del miembro. Figma: `Menu/Accion` (4111:401). **Propuesto v4.5**.

| Prop | Tipo | Notas |
|---|---|---|
| `texto`, `icono` | texto, IconName | |
| `tono` | `'normal' \| 'destructivo' \| 'deshabilitado'` | Destructivo = `z-color-text-error` + ícono `z-color-status-error-default`: acción irreversible, no severidad de consumo. |

## Usos (v4.5 §7.1)
- Selector de foto: «Elegir de la galería», «Eliminar foto» (destructiva, solo si hay foto). Solo galería: decisión tomada con autonomía delegada (sin cámara).
- Menú del miembro (solo administrador): «Transferir administración», «Expulsar del hogar»; en una invitación pendiente, «Cancelar invitación». Toda acción pide `ConfirmDialog`.
