@AGENTS.md

# CLAUDE.md · app/ (Expo + React Native + TypeScript)

Complementa al `CLAUDE.md` de la raíz. Guía humana: `docs/guias/GUIA-2-interfaces-app.md`.

## Estructura obligatoria

```
src/app/          rutas de expo-router: (auth)/, (onboarding)/, (tabs)/ — solo enrutan
src/screens/      <ScreenName>/<ScreenName>.tsx + use<ScreenName>Data.ts
src/components/   los 34 del sistema de diseño (31 + `ConsumptionGauge`, `ConsumptionRing` y `LineChart`), con el mismo nombre y props que docs/diseno/componentes/index.d.ts
src/theme/        tokens.ts GENERADO desde docs/diseno/tokens.json (script, no a mano) + fonts.ts
src/texts/        catalogo.es-CO.json (copia de docs/textos, conserva su nombre) + t(clave, vars) + plurales zero/one/other
src/api/          cliente HTTP con el JWT de Supabase + tipos GENERADOS desde docs/api/zentheris-api-v0.2.5.yaml
src/format/       formatNumber, formatCOP, formatPercent, relativeTime (es-CO, RN-XII-08)
src/state/        React Query (datos del servidor) y sesión de Supabase
```

Nombres de carpetas, archivos, variables y funciones en inglés (decisión del 10/11/2026). Los nombres de archivo de `src/app/` definen las rutas y **se quedan en español** (decisión del 10/11/2026: son direcciones, como las del contrato; `BottomNav` y el enlace `zentheris://invitacion` ya las usan). Los grupos `(auth)`, `(onboarding)` y `(tabs)` se crean en la sesión 10, no en la refactorización inicial. La ruta `catalogo-componentes` es interna y solo existe en desarrollo (`__DEV__`).

## Reglas

- **Una pantalla** = vista con componentes del sistema de diseño + un hook de datos con 4 estados (cargando con `Skeleton`, error con `InlineNotice` y `error.app.*`, sin permiso con `StateMessage` y datos). Además, los estados de la sección 7.3 de las reglas.
- Textos: `t('clave')`. Los estados se leen como `estado.<mensaje_codigo>.titulo|cuerpo|leyenda`. Los errores, como `error.<codigo en minúsculas>`. Si falta una clave, **no la inventes**: déjalo marcado en el PR.
- Colores, espacios, radios y tipografía: solo con tokens. Nada de hexadecimales en los componentes.
- Íconos: `lucide-react-native`. Antes de usar un nombre, confirma que el paquete lo exporta. Se instala y configura en el esqueleto; se aplica a las pantallas después, una por una, con aprobación del cambio visual.
- Gráficos, en este orden de respaldo: (1) `react-native-gifted-charts`, con una prueba mínima de barras, línea y anillo como primera tarea (DC-12); (2) Victory Native; (3) un gráfico hecho a mano con `react-native-svg`. Se usa el siguiente solo para el gráfico que lo necesite y se explica el motivo. Los gráficos hechos a mano que ya existen se conservan como referencia visual hasta migrarlos.
- COP solo si `tarifa_vigente`. Sin permiso, solo se reemplazan las cards de datos.
- Tiempos de espera: 15 s; 60 s en `POST /onboarding`.
- Accesibilidad: áreas táctiles de 44 pt o más (`hitSlop`), `accessibilityLabel` en español y un resumen en texto por cada gráfico. Nunca declares que la app «es accesible».

## Refactor del prototipo (hacer primero)

Primero se reorganiza y se instala (esqueleto); después se aplica pantalla por pantalla. Sigue la tabla de `docs/guias/GUIA-2-interfaces-app.md` §7: tokens en lugar de colores fijos; `BottomNav` con Lucide; borrar la plantilla de Expo y `.kilo/`; revisar `@react-navigation/*` con el SDK actual; Satoshi según DC-06.

## Comandos (confirma con package.json)

`npx expo start` · `npx expo install --check` · `npm run lint` · pruebas con `jest-expo`.
