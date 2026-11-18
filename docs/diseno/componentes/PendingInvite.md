# PendingInvite

Invitación pendiente en Miembros del hogar; **solo la ve el administrador** (RN-X-08, N6). Figma: `Configuracion/Invitacion-pendiente` (4113:520). **Propuesto v4.5**.

| Prop | Tipo | Notas |
|---|---|---|
| `correo` | texto | Correo invitado. |
| `vence` | texto | «Vence en N días», calculado con `expira_en`; las vencidas no se muestran (D7). |
| `onMenu` | función \| false | Abre la hoja con «Cancelar invitación». |

Insignia «Pendiente» neutra: el amarillo solo comunica severidad. No cuenta en «miembros activos», pero sí en el límite de 5 al invitar.
