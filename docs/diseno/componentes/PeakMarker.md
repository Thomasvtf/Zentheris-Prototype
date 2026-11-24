# PeakMarker

Marcador del pico más alto del periodo en barras y línea (RN-XIII-03, D5). Figma: `Grafico/Marcador-pico` (4113:432). **Propuesto, pendiente de aprobación visual**.

| Opción | Diseño | Estado |
|---|---|---|
| A | Píldora `z-color-accent-soft` + borde y texto `z-color-chart-peak` (rojo claro) | En uso en las pantallas v4.5 y en los tooltips de `Grafico/Historial/Barras` y `Linea` |
| B | Etiqueta `z-color-text-primary` y contorno punteado `z-color-border-accent` | Alternativa |

**Color del pico (D17, 02/11/2026; reemplaza a D12):** la barra o el punto del pico usan `z-color-chart-peak` (rojo claro #F59099; la primera versión era blanco y se descartó por revisión de Nicolás) y el resto de la serie conserva `z-color-chart-series1`. Además lleva la palabra «Pico», para no depender solo del color. El pico tiene color propio (rojo claro), distinto de los estados; el rojo queda para crítico (RN-XIII-03, D5). El valor va también en el resumen accesible. En Figma: `color/chart/peak`, aplicado en `Grafico/Historial/Barras` y `Grafico/Historial/Linea`.

*Contraste:* el rojo claro frente al fondo de la card es de 6,97:1 y frente a `accent/soft` de 5,76:1; frente a las barras vecinas (verde menta) cambia el tono pero no la luminosidad (1,15:1), así que alguien con daltonismo podría confundirlos: por eso el pico se refuerza con la etiqueta (texto y borde en el mismo color) y la posición. Alternativa si se quiere más diferencia de luminosidad: violeta #A78BFA (a decidir). No se declara accesibilidad certificada: falta comprobarla en dispositivo.

## Regla anti-choque con «Crítico» (02/11/2026, pedido de Nicolás: pico en rojo)

El pico usa `z-color-chart-peak` = rojo claro #F59099, que es el mismo valor que `z-color-red-400`, el texto de error en oscuro. No es el rojo de estado `z-color-status-error-default` (#EF4444) ni `z-color-chart-series4`. Como el tono es parecido, el color no basta para separarlo de «Crítico»; la separación la hace la forma y el texto:

1. **Sin componentes de estado:** el pico nunca usa píldora de estado, ícono de estado, fondo de estado ni la palabra «Crítico», «Elevado» o «Normal».
2. **Etiqueta neutra:** «Pico» va en `text/primary`, con borde o relleno en rojo claro. El rojo claro solo marca la barra o el punto del pico.
3. **Rojo de estado solo para estado:** `status/error` y `chart/series4` aparecen únicamente en píldoras, arcos o anillos con la palabra «Crítico» y su ícono. Nunca rellenan una barra de serie ni una etiqueta de pico.
4. **Posición antes que color:** el pico se identifica por su posición (única barra o punto con etiqueta encima), no solo por el color.
5. **Card de Pico:** el estado se muestra en texto y con su propio componente, nunca con el color del pico.
6. **Pantallas con pico y estado crítico juntos:** cada elemento conserva su forma y su texto; no se combinan.

**Verificación pendiente (no hecha):** contraste del rojo claro sobre `surface` 6,64:1 y sobre `accent/soft` 5,48:1; frente a las barras menta solo cambia el tono (1,17:1 de luminosidad). Falta probar en dispositivo y con simulación de daltonismo, porque rojo claro y rojo de estado pueden confundirse.
