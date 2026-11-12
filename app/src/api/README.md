# api/

Cliente de la API, tipado desde el contrato.

- `schema.d.ts`: **generado** con `npm run generate:api-types` (openapi-typescript). El CI falla si no está al día.
- `client.ts`: `apiRequest` (base `EXPO_PUBLIC_API_URL` + `/api/v1`, token de la sesión, 15 s; 60 s en el onboarding) y `ApiRequestError`.
- `errors.ts`: `toErrorTextKey(error)` → `error.<codigo>` o `error.app.*`.
- Un módulo por etiqueta (`system`, `users`, `households`, `onboarding`, `members`, `consumption`, `goalsTariff`, `alertsTips`) con **las 40 operaciones**. Cada función lleva su etiqueta `@operationId`, que `scripts/check_integration.py` compara con el contrato y el mapa.
- **Ejemplo:** `getHousehold(hogarId)` → `GET /hogares/{hogar_id}` (`obtenerHogar`).
- **No va:** lógica de pantalla ni estado (eso va en `screens/` y `state/`).
