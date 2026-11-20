# Requirement

Requisito de contraseña con ícono + texto (RN-IX-02): registro, restablecer y cambiar contraseña. Figma: `Control/Requisito` (4110:416). **Aprobado v4.5** (D-SD-04, 07/11/2026).

| Prop | Tipo | Notas |
|---|---|---|
| `texto` | texto | «Mínimo 8 caracteres», «Una mayúscula», «Un número», «Diferente a la actual» (solo en el cambio). |
| `cumple` | booleano | Cumple: check `z-color-accent-primary` + texto primario. Pendiente: check `z-color-text-disabled` + texto muted. |

Pendiente fuera de diseño: verificar si Supabase puede imponer la regla o solo la valida la app (§10).
