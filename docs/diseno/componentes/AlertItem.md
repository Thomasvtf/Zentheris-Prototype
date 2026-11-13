# AlertItem

Fila de la lista de Alertas: ícono por categoría, título, tiempo relativo y punto de lectura. Figma: `Alerta/Item` (2060:5864).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `categoria` | `'consumo_elevado' \| 'consumo_critico' \| 'informacion' \| 'miembro' \| 'consejo'` | Elige el ícono. |
| `severidad` | `'informativa' \| 'advertencia' \| 'critica'` | Color del ícono y del punto. |
| `leida` | `boolean` | Punto relleno = no leída; círculo vacío = leída. |
| `titulo`, `tiempo` | texto | «Hace 10 min», «Ayer». |

## Catálogo inicial
| Alerta | Severidad | Ícono |
|---|---|---|
| Consumo elevado | advertencia | triangle-alert |
| Consumo crítico | crítica | circle-alert |
| Cierre de mes | informativa o advertencia | info |
| «[Nombre] se unió al hogar» | informativa | user |
| Nuevo consejo | informativa | lightbulb |

## Tokens
Ícono 20 en contenedor 40 `z-color-background-surfaceAlt`; severidad `z-color-status-info-default`, `-warning-default`, `-error-default`; título `body-s-medium`; tiempo `body-xs` muted; divisor `z-color-border-subtle`.

## Reglas
- Más reciente primero, con tiempo relativo (RN-XIV-04).
- Las alertas visibles se marcan como leídas al entrar a la pantalla; tocar una alerta no hace nada: sin aspecto de botón (RN-XIV-03).
- **Las no leídas nunca se ocultan.** Una leída se oculta de la lista de esa persona 7 días después de leerse; el registro no se borra (RN-XIV-05, D8).
- Una misma regla no genera más de una alerta por zona al día (RN-XIV-08): el componente no deduplica, lo hace el backend.
- Vacío: StateMessage `vacio` («No tienes alertas»). Figma tiene la errata «Sucess» y textos fuera de catálogo («Sobreconsumo…», «Nuevo dispositivo…»): no usarlos.
