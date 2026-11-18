# ConsumptionGauge

Medidor semicircular que responde «¿cómo va el consumo ahora?» con una forma de medidor. Es la vista por defecto de la card de consumo actual del Panel y de «Estado actual» de la zona (RN-XII-07). **Obligatorio** (decisión de Nicolás, 11/11/2026).

Figma (copia de trabajo `RD1IQ5L1OmUeMxteRimvMe`): `Grafico/Consumo/Gauge` (588:109), dentro de `Card/Consumo/Grafico` (2051:730). **Ficha escrita el 11/11/2026 a partir de lo que ya está dibujado en Figma; el diseño no cambió.** Falta aprobación visual en dispositivo.

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `valor` | `number \| null` | `null` → «—», arco vacío, nunca 0 (regla de ausencia de datos). |
| `unidad` | `'kW' \| 'COP'` | El selector kW/COP cambia el número, **no el arco** (en Figma ambas variantes tienen el mismo arco). COP solo con tarifa vigente. |
| `estado` | `'normal' \| 'elevado' \| 'critico' \| 'sin_datos' \| 'sin_referencia'` | Llega calculado por el backend (RN-XI-02); el componente no lo calcula. |
| `proporcion` | número 0–1 | Parte del arco que se rellena. Ver «Cómo se llena el arco». |
| `decimales` | `number` | No pasarlo: kW 2 y COP 0 (RN-XII-08). |

## Diseño (según Figma)
- Semicírculo abierto hacia abajo, con grosor de unos 18 % del ancho. Se rellena de izquierda a derecha. Pista (la parte sin rellenar): `z-color-neutral-700` (#244039).
- Relleno por estado: normal `z-color-chart-series1` (#5DD39E), elevado `z-color-chart-series3` (#FDE047), crítico `z-color-chart-series4` (#EF4444).
- Valor y unidad debajo del arco, centrados, en `Typography/Data/XL/XL-Mono-32` (JetBrains Mono Bold 32), color `z-color-text-primary`. Si no cabe en 320 px baja a `data-l`.
- Palabra del estado debajo del valor, en Inter: normal `z-color-text-accentSoft` (#86EFAC), elevado `z-color-text-warning` (#FDE047), crítico `z-color-text-error` (#F59099). **El estado se dice con palabra y color**, nunca solo con color.
- Fondo de la card: `z-color-background-surface` (#162B25).

## Cómo se llena el arco (aprobada por Nicolás el 11/11/2026)
La regla no estaba escrita en las reglas v4.9 (solo el ejemplo «Gauge al 40 %»). Se usan datos que el contrato 0.2.5 ya entrega en `consumo_actual` (`potencia_kw` y `referencia_kw`) y los umbrales v1 (`consumo_actual`: elevado desde +20 %, crítico desde +40 % sobre la referencia):

`proporcion = min( potencia_kw ÷ (referencia_kw × 1,6) , 1 )`

Así el arco completo equivale al 160 % de la referencia; el estado elevado empieza al 75 % del arco y el crítico al 87,5 %. Los porcentajes del ejemplo de Figma (20 %, 55 %, 90 %) son ilustrativos. Con `sin_datos` o `sin_referencia`, el arco queda solo con la pista.

## Cómo se construye
**A mano con `react-native-svg`**, porque `react-native-gifted-charts` no trae un medidor semicircular (decisión de Nicolás, 11/11/2026, DC-63). Es un arco de trazo grueso: una pista y un arco relleno que se dibuja con `strokeDasharray`. Comparte código con `ConsumptionRing` mediante un componente base de arco.

## Accesibilidad
`role="progressbar"` con `aria-valuenow`, valor mínimo y máximo, y etiqueta que dice el valor con su unidad y la palabra del estado («2,40 kW, Normal»). Sin certificación; falta probar con lectores de pantalla.

## Estados
Sin datos: «—» y la card de `StateMessage`/aviso del catálogo. Sin permiso: la card se reemplaza (`StateMessage`). Cargando: `Skeleton` con la forma del semicírculo.
