# components/

Los 34 componentes del sistema de diseño (31 + `ConsumptionGauge`, `ConsumptionRing` y `LineChart`), con el mismo nombre y props que [`docs/diseno/componentes/index.d.ts`](../../../docs/diseno/componentes/index.d.ts) (props en español, DC-67).

- **Va:** componentes solo de presentación, con tokens y textos del catálogo.
- **No va:** llamadas a la API ni lógica de negocio.

Estado: todavía no se implementa ninguno (prompt §12.11). Los archivos actuales (`themed-text`, `app-tabs`…) son de la plantilla de Expo y se quitan después de la Fase 4.
