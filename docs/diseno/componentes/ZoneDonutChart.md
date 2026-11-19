# ZoneDonutChart

Anillo que responde «¿qué zonas pesaron más en el periodo?», solo con el filtro General (RN-XIII-04). Figma: `Grafico/Historial/Anillo-zonas` (544:148), en laboratorio y sin uso en Pantallas.

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `zonas` | `{nombre, porcentaje}[]` | Todas las zonas del hogar; porcentajes que suman 100. Nombres: Cocina, Sala, Dormitorio, Baño, Lavandería, Oficina, Terraza, Garaje, Cuarto de servicio. |
| `total` | `number` | kWh del periodo en el centro (opcional, 1 decimal). |
| `periodo` | texto | Para el resumen accesible. |

## Regla de agrupación (RN-XIII-04, decisión D2 de la v4.5)
- Hasta 4 zonas: un segmento por zona.
- **Más de 4 zonas:** el anillo muestra las **4 de mayor participación** y agrupa el resto en un segmento **«Otras zonas»** con la participación sumada. Es fijo: no hay propiedad para cambiarlo.
- **La lista junto al anillo muestra todas las zonas** con nombre y porcentaje: las 4 primeras con su color, luego la fila «Otras zonas» con su suma y, debajo y con sangría, cada zona agrupada con su porcentaje.
- Los colores solo identifican zonas; no comunican estado.

## Color (opción A)
Por orden de participación: `z-color-green-400`, `z-color-green-200`, `z-color-neutral-300`, `z-color-green-600`; «Otras zonas» `z-color-neutral-500`. **Nunca rojo ni amarillo.** `z-color-neutral-500` queda bajo 3:1 (2,66) y solo se usa para «Otras zonas», siempre con su etiqueta.

## Etiquetas y tokens
Nombre en `body-s` (`z-color-text-primary`; las zonas agrupadas en `z-color-text-muted`), porcentaje en `data-s-16` con espacio («34 %»). Separación de 2 px entre segmentos. Resumen accesible con todas las zonas y la composición de «Otras zonas».
