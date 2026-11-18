# StatusBadge

Comunica el estado de consumo (normal, elevado, crítico) con color + ícono + palabra; une `Estado/Capsula` (2048:2219) y `Estado/Texto` (514:1168).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `estado` | `'normal' \| 'elevado' \| 'critico'` | Otros estados (sin datos, sin referencia) no usan cápsula de severidad. |
| `variante` | `'capsula' \| 'texto'` | Por defecto cápsula. |
| `icono` | `boolean` | Por defecto `true`. Solo se apaga cuando el ícono ya está al lado (bloque de estado de la card). |

## Variantes y tokens
| Estado | Palabra | Ícono (Lucide probable) | Fondo / borde (cápsula) | Texto | Ícono |
|---|---|---|---|---|---|
| normal | Normal | circle-check | `z-color-status-success-bg` / `-border` | `z-color-status-success-text` | `z-color-status-success-default` |
| elevado | Elevado | triangle-alert | `z-color-status-warning-bg` / `-border` | `z-color-status-warning-text` | `z-color-status-warning-default` |
| critico | Crítico | circle-alert | `z-color-status-error-bg` / `-border` | `z-color-text-error` | `z-color-status-error-default` |

Tipografía `ui-s-semibold-12`; radio `z-radius-full`; padding `z-space-4` × `z-space-8`; ícono 16.

## Reglas
- «Crítico», nunca «sobreconsumo».
- El texto crítico usa `z-color-text-error` (#F59099), no `z-color-status-error-default` (3,97:1, no apto para texto pequeño).
- Rojo y amarillo solo aquí y en otros indicadores de severidad.
- Figma: la propiedad de estado de la cápsula se llama «Size» y usa #F87171 fuera de paleta; aquí se corrige en código, no en Figma.
