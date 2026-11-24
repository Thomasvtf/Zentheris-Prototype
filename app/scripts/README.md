# app/scripts/

| Script | Qué hace |
|---|---|
| `generate-tokens.mjs` | Genera `src/theme/tokens.ts` desde `docs/diseno/tokens.json`. Con `--check`, falla si `tokens.ts` no está al día (lo usa el CI). |
| `reset-project.js` | De la plantilla de Expo; se quita en la limpieza final (PENDIENTES #15). |
