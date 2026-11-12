# theme/

- `tokens.ts`: **generado** desde `docs/diseno/tokens.json` con `npm run generate:tokens`. No se edita a mano; el CI falla si no está al día.
- `fonts.ts`: `loadFonts()`, `fontFiles` y `fontFamilyFor(rol, peso)`. Satoshi es opcional (`require` en `try/catch`); si falta, el rol `display` usa Inter Bold (DC-06).
- **Ejemplo:** `{ color: colors['text-primary'], fontFamily: fontFamilyFor('body', '400') }`.
- **No va:** colores o medidas escritos a mano.
