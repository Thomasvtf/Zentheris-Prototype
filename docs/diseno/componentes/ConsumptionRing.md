# ConsumptionRing

Anillo de **un solo valor** con el número en el centro. Es la segunda vista de la card de consumo actual del Panel (botón de vista arriba a la derecha) y de «Estado actual» de la zona (RN-XII-07). **Obligatorio** (decisión de Nicolás, 11/11/2026). **No es** `ZoneDonutChart`: aquel reparte el consumo entre zonas en Historial; este mide un solo valor frente a su referencia.

Figma: `Grafico/Consumo/Anillo` (561:127), dentro de `Card/Consumo/Grafico` (2051:730). **Ficha escrita el 11/11/2026 a partir de lo que ya está dibujado en Figma; el diseño no cambió.**

## Propiedades
Las mismas que `ConsumptionGauge` (`valor`, `unidad`, `estado`, `proporcion`, `decimales`).

## Diseño (según Figma)
- Anillo completo que empieza arriba (a las 12) y se rellena en sentido horario. Pista `z-color-neutral-700` (#244039); relleno por estado con los mismos tokens del gauge (series1, series3, series4). Grosor de unos 12 % del diámetro.
- En el centro: el valor en `Typography/Data/XL/XL-Mono-32` y debajo la unidad («kW», «COP») en `Typography/UI/M/M-Semi bold`, color `z-color-text-muted` (#C4D4CF). COP en miles abreviados con «k» (RN-XII-08), por ejemplo «45,2k».
- Palabra del estado debajo del anillo, con los mismos colores que el gauge.
- El arco se llena con la misma regla que el gauge (`proporcion`).

## Variante «% del objetivo» del laboratorio (no se usa)
En Figma el laboratorio trae una variante con «72 % del objetivo». Las reglas no tienen «objetivo» en el consumo actual: la comparación contra la meta se llama «Límite» y solo existe en el acumulado de hoy (RN-XI-04). Esa variante **no se implementa** salvo que Nicolás decida otra cosa. Además, en el laboratorio el texto «72 %» se parte en dos líneas y se sobrepone a «del objetivo» (defecto de Figma, para corregir si se usa).

## Cómo se construye
**A mano con `react-native-svg`** (un `Circle` de pista y otro de relleno con `strokeDasharray`), con el mismo componente base que `ConsumptionGauge` (DC-63). No usa `gifted-charts`: un anillo de un solo valor es más simple a mano que con la librería.

## Accesibilidad y estados
Igual que `ConsumptionGauge`.
