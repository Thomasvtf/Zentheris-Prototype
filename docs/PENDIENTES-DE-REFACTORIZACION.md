# Pendientes de la refactorización · tareas que se hacen durante los PR

Versión 1 · 11/11/2026. Esta lista es corta y se marca a medida que se avanza. Lo que se configura en GitHub (revisión de PR, protección de `main`, aviso de secretos) va en `PENDIENTES-DE-CONFIGURACION.md`, no aquí.

| # | Cuándo | Tarea | Por qué | Hecho |
|---|---|---|---|---|
| 1 | PR 1 `docs/contexto-del-proyecto` | Instalar el paquete de contexto (`CLAUDE.md` y `docs/`) y revisar que los enlaces relativos funcionen. | Que Claude Code y el equipo lean lo mismo. | [ ] |
| 2 | PR 2 `refactor/mover-estructura` | Mover `supabase/migrations/LEEME.md` a `supabase/LEEME.md` y ajustar las rutas relativas de su texto. | La carpeta de migraciones queda solo con archivos SQL. | [ ] |
| 3 | PR 2 y 3 | Mover y adaptar la estructura en inglés (rutas de expo-router en español). Un commit solo de movimientos y otro solo de imports. | Menos conflictos con las ramas del equipo. | [ ] |
| 4 | PR 3 | Crear `api/app/config_files/` con copias exactas de `umbrales-estado.v1.json` y `textos-backend.es-CO.json`. | Decisión confirmada el 11/11/2026. | [ ] |
| 5 | PR 3 (copias) y PR 5 (integración) | Añadir a `scripts/check_integration.py` la comparación SHA-256 de cada copia contra su original en `docs/`, y ejecutarla en el CI. | Evitar que un umbral cambie en un sitio y en el otro no. | [ ] |
| 6 | PR 4 `build/plantillas-de-entorno` | Plantillas `.env.example` solo con nombres. `RUTA_UMBRALES` y `RUTA_TEXTOS_BACKEND` apuntan a `config_files/`. | Guía de claves v3. | [ ] |
| 7 | PR 5 `feat/esqueleto-api` | Agregar `tzdata` como dependencia directa en `pyproject.toml` y regenerar `requirements.txt`. | Aprobado el 11/11/2026. `zoneinfo` necesita la base de zonas horarias en Windows para America/Bogota. | [ ] |
| 8 | PR 6 `feat/esqueleto-app` | Cambiar `scheme` de `app` a `zentheris` en `app.json`. | DC-64. | [ ] |
| 9 | PR 6 | Instalar y configurar librerías (gráficos, íconos, `expo-linear-gradient`, `openapi-typescript`); quitar `@react-navigation/*` solo si `npm ls` y el typecheck confirman que nada las usa. | DC-63. Se aplican a las pantallas después, una por una. | [ ] |
| 10 | PR 6 | Copiar las fuentes abiertas a `app/assets/fonts/` con su `OFL.txt`, todas en el mismo formato. Satoshi no se sube. | DC-66 y DC-06. | [ ] |
| 11 | Antes de adoptar `gifted-charts` | Prueba mínima en `ComponentCatalogScreen`: barras, línea y anillo de zonas con `gifted-charts`; el arco base del Gauge con `react-native-svg`. | DC-12 y DC-63. | [ ] |
| 12 | Aplicar librerías | Construir Gauge y anillo de consumo a mano con `react-native-svg` (componente base de arco compartido), según `ConsumptionGauge.md` y `ConsumptionRing.md`. | Decisión del 11/11/2026; `gifted-charts` no trae medidor. | [ ] |
| 13 | Cada PR | Revisar el historial antes de subir: sin `Co-Authored-By` ni «Generated with Claude Code». | DC-60. | [ ] |
| 14 | PR de alineación | Proponer borrar `requirements-txt` y `test_tabs.png` (lo acepta quien lleva cada rama). | Archivos sobrantes. | [ ] |
| 15 | Al final | Limpiar la plantilla de Expo; hablar con el equipo y con Thomas; ramas `setup` con etiqueta de respaldo y aprobación por rama. | DC-65. | [ ] |
| 16 | Al aplicar las librerías a Historial | Decidir si el gráfico de área de la pila se quita o se deja (no es obligatorio). | Decisión del 11/11/2026. | [ ] |
| 17 | Al aplicar los componentes | Las props siguen los nombres de `index.d.ts` aunque estén en español. | DC-67. | [ ] |
| 18 | PR 3 y 4 | Borrar `.kilo/` y `app/.kilo/` (22 archivos) y el `requirements.txt` vacío de la raíz; agregar `.kilo/` al `.gitignore`. | Archivos sobrantes. | [ ] |
| 19 | PR 3 | Regenerar `api/requirements.txt` en UTF-8 y dejar el CI del backend en verde (hoy falla en `ruff`). | Que el CI sirva como comprobante. | [ ] |
| 20 | PR 3 | Crear `.python-version` en `api/`. | Render la lee. | [ ] |
| 21 | PR 4 | Crear `app/.easignore` para incluir la fuente Satoshi en las builds. | DC-06. | [ ] |
| 22 | PR 5 | Crear los 35 archivos de prueba vacíos, uno por ID de la matriz, con `pytest.skip("TODO(<ID>)")`. | Cada pendiente se ve y `pytest` queda en verde. | [ ] |
| 23 | PR 5 y 6 | Crear `docs/MAPA-DE-INTEGRACION.md` (40 filas). | Puerta de entrada de la integración. | [ ] |
| 24 | PR 6 | Ruta `catalogo-componentes` (solo `__DEV__`) y 1 línea en `_layout.tsx` para ocultarla. | Decisión del 10/11/2026. | [ ] |
| 25 | PR 1, 3, 5 y 6 | Un `README.md` por carpeta principal. | Estructura documentada (prompt §5.5). | [ ] |
| 26 | Antes de la conversación final | Dejar el borrador del mensaje para el equipo, sin enviarlo. | Prompt §4, Fase 3. | [ ] |
| 27 | PR 3 | Agregar `.gitattributes` para fijar saltos de línea LF en `*.json`, `*.sql`, `*.md`, `*.py` y `*.yaml`. | Windows copia con CRLF (`core.autocrlf=true`) y rompería la comparación SHA-256 de `config_files/` en local. Propuesto por Claude Code el 11/11/2026. | [ ] |
