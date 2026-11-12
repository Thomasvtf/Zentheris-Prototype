# Calibración de umbrales de estado v1 · 03/11/2026

Estado: **decidido** (autonomía delegada por Nicolás el 03/11/2026; revisable). Reglas: RN-XI-02 a RN-XI-07, RN-XIII-01, RN-XIII-03, RN-XIII-05, RN-XIV-07. Configuración resultante: `umbrales-estado.v1.json` (archivo del backend, no tabla).

**Evidencia: datos simulados.** Simulador de referencia `zentheris-4.3-ref-1` del Avance 03 con los conjuntos v1.0 del acta 04. No son datos reales. Los umbrales se pueden ajustar sin cambiar tablas ni contrato.

## 1. Verificación previa del conjunto calibrado

| Comprobación | Resultado |
|---|---|
| SHA-256 de los 6 JSON frente a reglas §8.1 | 6/6 idénticos |
| `MANIFEST.sha256` del paquete (95 archivos) | 95/95 OK |
| Suite del simulador (59 pruebas) | 59/59 OK (Python 3.13.18) |
| Validador de parámetros (`--cinco`) | 5/5 OK y nombres exactos |
| Reproducibilidad: mismo backfill dos veces (dúplex, 9 zonas) | Idéntico; SHA-256 de las filas `0a0f2779…20871b5` |
| Carga en PostgreSQL 16 local aislado (esquema de prueba del Avance 03) | 5 personalidades cargadas; 6.480 lecturas insertadas sin duplicados |

## 2. Método

- 5 personalidades × 20 hogares de referencia (todas las zonas que contempla cada una) × 61 días (30 de historial + 31 evaluados, sep–oct 2026).
- Referencia: promedio de la misma hora en los 30 días completos anteriores (RN-XI-03). Participación habitual: la de la misma hora en esos 30 días (RN-XI-05).
- Para cada indicador se midió la frecuencia de cada estado con umbrales candidatos y se eligió el juego que: (a) separa lo habitual de lo anómalo, (b) no satura la campana, (c) deja ver «Elevado» y «Crítico» en los datos simulados.
- Scripts: `calibrar_umbrales.py` (genera CSV), `resumir_calibracion.py` (resúmenes), `motor_estados_ref.py` (clasificación de referencia) y `test_escenarios_umbrales.py` (13 pruebas, 13 OK). Los CSV crudos (≈78 MB) no se guardan: se regeneran en ~20 s.

## 3. Umbrales decididos

| Indicador | Normal | Elevado | Crítico | Extra |
|---|---|---|---|---|
| Consumo actual del hogar (hora vs promedio de esa hora) | < +20 % | +20 % a < +40 % | ≥ +40 % | — |
| Acumulado de hoy vs promedio | < +15 % | +15 % a < +30 % | ≥ +30 % | — |
| Acumulado de hoy vs meta (% del límite diario) | < 80 % | 80 % a < 100 % | ≥ 100 % | Textos «Dentro / Cerca / Superaste el límite» |
| Estado de una zona (RN-XI-06) | < +30 % | +30 % a < +60 % | ≥ +60 % | Exceso mínimo 0,05 kWh |
| Participación de una zona (RN-XI-05) | < +25 % | +25 % a < +50 % | ≥ +50 % | Exceso mínimo 0,05 kWh |
| Día completo (pico de Semana y Mes) | < +15 % | +15 % a < +30 % | ≥ +30 % | — |
| Comparación de periodos y costo | menor (< −5 %) o similar (−5 % a < +10 %) | mayor (+10 % a < +25 %) | muy mayor (≥ +25 %) | Variantes del catálogo |
| Pico (RN-XIII-03) | Es pico desde +10 %; su estado usa la fila de la hora (Día) o del día completo (Semana y Mes) | | | |
| Variación frente a la hora anterior | «Igual» si \|var\| < 0,5 % | | | |
| Cierre de mes | Dentro si total ≤ referencia del hogar; encima si es mayor | | | Sin tolerancia |

Mínimo de 7 días con dato para tener referencia; si no, `sin_referencia`. El backfill de 30 días evita ese caso (RN-XI-03).

## 4. Resultados con los umbrales elegidos (datos simulados)

| Personalidad | Consumo actual elevado / crítico (% horas) | Alertas de zona elevado por día | Alertas de zona crítico por semana |
|---|---|---|---|
| Compacto | 0,73 / 0,13 | 0,000 | 0,01 |
| Eficiente | 1,70 / 0,22 | 0,015 | 0,28 |
| Intermedio | 0,72 / 0,28 | 0,002 | 0,47 |
| Familiar | 1,79 / 0,26 | 0,008 | 0,37 |
| Amplio | 5,89 / 0,77 | 0,124 | 0,79 |

Comparación Día vs ayer: 32,5 % menor, 46,2 % similar, 18,4 % mayor, 2,9 % muy mayor. Semana: 17,6 / 76,5 / 5,5 / 0,5 %. Detalle en `resumen_*.csv`.

## 5. Proyección al cierre (RN-XIII-05)

Se compararon dos fórmulas con un mes simulado completo (octubre, 100 hogares):

| Días transcurridos | Error medio lineal | Error medio por perfil |
|---|---|---|
| 1 | 6,34 % (máx. 18,2 %) | 1,44 % (máx. 6,8 %) |
| 3 | 3,39 % | 1,46 % |
| 7 | 1,96 % | 1,18 % |

**Fórmula elegida (por perfil):** proyección kWh = acumulado del periodo + Σ promedios de las horas que faltan hoy + días completos restantes × promedio diario de 30 días. Proyección COP = costo acumulado (tarifa vigente en cada fecha) + (proyección kWh − acumulado) × precio vigente hoy + cargo fijo (solo vista Mes, RN-V-02). Vale para Día, Semana y Mes.

## 6. Escenarios probados (`test_escenarios_umbrales.py`)

| Escenario | Esperado | Resultado |
|---|---|---|
| Normal: cocina de un hogar familiar sin alteración, 24 horas | ≥ 20 h normales | OK |
| Pico moderado: cocina +45 % a las 19:00 | Elevado | OK |
| Crítico: cocina +0,8 kWh a las 19:00 (freidora) | Crítico | OK |
| Ruido de una zona pequeña de madrugada | Normal por el piso de 0,05 kWh | OK |
| Bordes 20 %/40 %, sin datos ≠ 0, sin referencia, meta 80/100 %, comparación, pico, variación, proyección | Según tabla | OK |

## 7. Limitaciones

1. Los eventos simulados pesan poco (acta 04, limitación 1): con *Consumo compacto* casi no hay alertas de zona. Es coherente con el hogar de referencia, no un error.
2. Los umbrales se calibraron con datos simulados; con datos reales habrá que recalibrar (RN-XI-07 permite evaluar personalización por hogar más adelante).
3. Coma flotante: comparar con el porcentaje redondeado a 6 decimales (o con `Decimal`); sin eso, 1,20/1,00 da 19,999… y cae en «Normal».
4. La medición de tiempo del backfill se hizo en local (generación 0,03 s + inserción 0,12–0,14 s para 6.480 filas); falta medir en Render + Supabase.

## 8. Cómo reproducir

```
python -I calibrar_umbrales.py <ruta Avance 03 descomprimido> <carpeta csv>
python -I resumir_calibracion.py <carpeta csv> .
python -I test_escenarios_umbrales.py <ruta Avance 03 descomprimido>
```
