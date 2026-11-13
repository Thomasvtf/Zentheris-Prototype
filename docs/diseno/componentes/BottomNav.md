# BottomNav

Barra inferior de cinco secciones con una única pestaña activa por pantalla. Figma: `Navegacion/Barra-inferior` (4083:3427).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `activa` | `'principal' \| 'historial' \| 'zonas' \| 'consejos' \| 'configuracion'` | Exactamente una. |
| `onCambiar` | `(id) => void` | |

## Secciones e íconos canónicos
| Sección | Opción en Figma | Glifo (Lucide probable) |
|---|---|---|
| Principal | `Icono/Nav/Principal` opción 1 (casa) | house |
| Historial | `Icono/Nav/Historial` opción 3 | clock — **por confirmar** (ver README, Iconografía) |
| Zonas | `Icono/Nav/Zonas` opción 2 (cuadrícula) | layout-grid |
| Consejos | `Icono/Nav/Consejos` opción 1 (bombilla) | lightbulb |
| Configuración | `Icono/Nav/Configuracion` (engranaje) | settings |

## Tokens
Alto `z-size-bottomNav-height` (64) + área segura inferior; fondo `z-color-background-surface`; borde superior `z-color-border-subtle`. Inactiva: ícono 24 y etiqueta en `z-color-text-muted`. Activa: contenedor 48 × 28 `z-color-accent-soft` con `z-radius-sm`, ícono `z-color-accent-primary`, etiqueta `z-color-text-accent`, `aria-current="page"`. Etiquetas `body-xs-medium-10` (rol Body 10 observado; validar legibilidad en dispositivo). Cada pestaña mide ≥ 75 × 64 a 375 px (área táctil cumplida).
