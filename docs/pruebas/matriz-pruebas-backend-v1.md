# Matriz de pruebas del backend v1 · 03/11/2026

Complementa el plan v3.0 con lo que faltaba según las reglas §10: permisos, RLS, contrato, zonas por vivienda, umbrales, backfill y alertas (DC-49). Cada prueba registra escenario, datos, resultado y evidencia. Las que dicen **[ref]** ya tienen una implementación de referencia ejecutada en la carpeta.

| ID | Área | Caso | Esperado | Regla |
|---|---|---|---|---|
| P-01 | Permisos | Usuario sin membresía consulta un hogar ajeno | 404 | RN-I-03 |
| P-02 | Permisos | Miembro sin `ver_consumo_actual` pide `consumo/actual` | 403 `SIN_PERMISO_VER_CONSUMO` | RN-XVII-01 |
| P-03 | Permisos | Miembro sin `ver_historial` pide `historial` | 403 `SIN_PERMISO_VER_HISTORIAL` | RN-XVII-02 |
| P-04 | Permisos | Miembro sin permiso de metas crea una meta | 403 `SIN_PERMISO_MODIFICAR_METAS` | RN-XVII-04 |
| P-05 | Permisos | Miembro crea una tarifa, invita o mueve permisos | 403 `NO_ES_ADMINISTRADOR` | RN-X-08, XVI-05 |
| P-06 | Permisos | El administrador sin permisos activados ve todo | 200 | RN-XVII-05 |
| P-07 | Permisos | Fuentes de datos sin permiso | 200, `valores_ocultos=true`, kW `null` | RN-XVI-06 |
| R-01 | RLS | Cliente con JWT de A lee lecturas del hogar B directo en Supabase | 0 filas | DC-40 |
| R-02 | RLS | Cliente intenta escribir cualquier tabla | Rechazado | DC-40 |
| R-03 | RLS | Cliente lee `perfiles_simulacion` | 0 filas | DC-40 |
| R-04 | Storage | A lee la foto de B, de otro hogar | Denegado; del mismo hogar, permitido | DC-43 |
| Z-01 | Zonas | Apartaestudio con terraza | 422 `ZONAS_NO_PERMITIDAS` | RN-X-02 |
| Z-02 | Zonas | Apartamento sin baño | 422 `ZONAS_BASICAS_FALTANTES` | RN-X-02 |
| Z-03 | Zonas | Apartaestudio con 6 zonas o con 2 básicas | 422 `CANTIDAD_ZONAS_INVALIDA` | RN-X-02 |
| Z-04 | Zonas | Las 13 combinaciones de ejemplo de la tabla 12 | Personalidad esperada **[ref]** (147 combinaciones en el Avance 03) | RN-X-04 |
| B-01 | Backfill | Onboarding de un dúplex con 9 zonas | 6.480 lecturas, sin duplicados, `calidad=simulada` **[ref local]** | RN-IV-01 |
| B-02 | Backfill | Falla forzada a mitad de la transacción | 500 `BACKFILL_FALLIDO` y 0 filas del hogar | RN-X-03 |
| B-03 | Backfill | Tiempo en Render + Supabase (10 repeticiones) | p95 ≤ 10 s | DC-33 |
| B-04 | Recuperación | Servidor apagado 5 h y luego una consulta | 5 h × zonas nuevas, idénticas a las de una generación continua **[ref]** | RN-IV-05, DC-34 |
| U-01 | Umbrales | 13 escenarios de `test_escenarios_umbrales.py` | Mismos resultados que la referencia **[ref: 13/13]** | RN-XI-07 |
| U-02 | Umbrales | Pico: 9,9 % no es pico, 10 % sí | Según DC-31 **[ref]** | RN-XIII-03 |
| U-03 | Proyección | Fórmula de RN-XIII-05 con cargo fijo solo en Mes | Igual a la referencia **[ref]** | RN-XIII-05 |
| A-01 | Alertas | Zona en crítico dos veces el mismo día | 1 alerta | RN-XIV-08 |
| A-02 | Alertas | Backfill con horas que serían críticas | 0 alertas | DC-35 |
| A-03 | Alertas | Miembro con el interruptor apagado al disparar | Sin fila en `alertas_usuario` para él | RN-VI-02, XIV-06 |
| A-04 | Alertas | Cierre de mes por encima de la referencia | Alerta de advertencia + consejo general de prioridad baja | RN-XIV-07, XV-07 |
| A-05 | Consejos | Consejo creado con 3 miembros activos | 3 filas `pendiente` | RN-XV-06 |
| C-01 | Contrato | Cada respuesta coincide con su esquema 0.2.5 | Sin errores (validación automática) | DC-47 |
| C-02 | Contrato | Lint oficial | 0 errores con Redocly | DC-46 |
| I-01 | Integridad | Sensor y zona de hogares distintos | 0 casos (consulta de integridad) | DC-38 |
| I-02 | Integridad | Tarifas solapadas del mismo hogar | Rechazado | DC-39 |
| I-03 | Integridad | Eliminar la cuenta del único miembro | Hogar y datos eliminados; nada huérfano | RN-IX-09, DC-36 |
| I-04 | Integridad | Eliminar la cuenta de un miembro (no único) | Membresía inactiva con usuario nulo; datos del hogar intactos | DC-36 |
| S-01 | Seguridad | Error interno en cualquier endpoint | La respuesta no expone la excepción | Guía 3 §7 |
| S-02 | Seguridad | Token de invitación | Solo se guarda su hash | RN-X-05 |

La referencia ejecutada está en `04_datos-simulados/calibracion-umbrales-v1/` (13/13 OK) y en el Avance 03 (59/59 OK). Nada de lo demás está ejecutado: el backend no existe todavía.
