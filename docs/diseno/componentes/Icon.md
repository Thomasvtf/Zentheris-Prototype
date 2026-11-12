# Icon

Glifo de interfaz estilo Lucide (trazo 2, extremos redondeados) con tamaño de la escala 16 · 20 · 24 · 32.

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `name` | nombre Lucide | house, clock, layout-grid, lightbulb, settings, bell, chevrons-left, circle-check, triangle-alert, circle-alert, circle-x, info, zap, loader, user, shield, coins, trending-up, trending-down, chart-pie. |
| `size` | 16 \| 20 \| 24 \| 32 | 16 en línea con Body XS y severidad; 20 chips, filas y zonas en cards; 24 navegación, cabecera, botones de ícono; 32 estados vacíos. |
| `color` | token CSS | Por defecto hereda `currentColor`. |
| `label` | texto | Íconos interactivos con etiqueta en español; decorativos ocultos al lector. |

## Color por estado (íconos táctiles)
Default `z-color-text-muted` · Active `z-color-accent-primary` · Disabled `z-color-text-disabled`. Severidad: `z-color-status-*-default`.

## Aviso
Los trazos de este componente son una **reconstrucción aproximada** para las vistas previas: los íconos del proyecto están aplanados en Figma y lucide.dev no estuvo accesible en esta sesión. En la app usar `lucide-react-native` con el nombre verificado.
