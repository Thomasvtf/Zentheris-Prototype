# InvitationCard

Invitación recibida por un usuario sin hogar (RN-X-01, RN-X-05, RN-X-06). Figma: `Card/Invitacion` (4113:408). **Propuesto v4.5**.

| Prop | Tipo | Notas |
|---|---|---|
| `hogar`, `invita`, `vence` | texto | Del contrato: `hogar_nombre`, `invitado_por_nombre`, `expira_en` (DD/MM/AAAA). |
| `onAceptar`, `onRechazar` | función | `aceptarInvitacion` / `rechazarInvitacion`. |

Con varias invitaciones pendientes se apilan varias cards (decisión con autonomía delegada). Errores: `INVITACION_EXPIRADA`, `INVITACION_NO_PENDIENTE`, `LIMITE_MIEMBROS`, `MEMBRESIA_ACTIVA_EXISTENTE` → pantalla «Esta invitación ya no está disponible».
