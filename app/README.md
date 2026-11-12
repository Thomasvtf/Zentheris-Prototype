# app/

App móvil de Zentheris: Expo (SDK 57), React Native y TypeScript, con expo-router. Reglas para Claude Code en [`CLAUDE.md`](CLAUDE.md); guía humana en [`docs/guias/GUIA-2-interfaces-app.md`](../docs/guias/GUIA-2-interfaces-app.md).

## Comandos (desde `app/`)

| Para qué | Comando |
|---|---|
| Instalar dependencias | `npm ci` (para agregar una librería: `npx expo install <paquete>`) |
| Levantar la app | `npx expo start` |
| Typecheck | `npm run typecheck` |
| Pruebas | `npm test` |
| Regenerar los tokens | `npm run generate:tokens` (desde `docs/diseno/tokens.json`) |
| Regenerar los tipos de la API | `npm run generate:api-types` (desde el contrato) |

Variables de entorno: copia [`.env.example`](.env.example) como `app/.env` y rellénalo (guía de claves v3). `app/.env` nunca se sube. Satoshi: ver [`assets/fonts/README.md`](assets/fonts/README.md).

En desarrollo, la ruta `/catalogo-componentes` muestra tokens, fuentes, íconos, formatos y la prueba mínima de gráficos.

## Qué va aquí y qué no

- **Va:** el código de la app (`src/`), sus recursos (`assets/`) y su configuración (`app.json`, `package.json`, `tsconfig.json`, `metro.config.js`).
- **No va:** claves ni `.env`, archivos de Satoshi (licencia ITF FFL), copias de `docs/` fuera de `src/texts/catalogo.es-CO.json`, ni carpetas `ios/` o `android/` (se generan).
