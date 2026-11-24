# routers/

Un archivo por etiqueta del contrato: `system`, `users`, `households`, `onboarding`, `members_invitations`, `consumption`, `goals_tariff` y `alerts_tips` (40 operaciones).

- **Va:** el decorador con la ruta exacta y el `operation_id` del contrato, la validación de la entrada (Pydantic) y la llamada al servicio.
- **No va:** reglas de negocio, transacciones ni SQL.
- **Ejemplo:** `@router.get("/hogares/{hogar_id}", operation_id="obtenerHogar", response_model=Hogar)`.

Estado: las rutas sin implementar responden 501 `{"detail": "TODO(<operationId>)"}` (temporal; no aparece en el OpenAPI).
