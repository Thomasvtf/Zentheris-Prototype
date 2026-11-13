# Guía del equipo · cómo hacer tu próxima tarea

Esta guía explica, paso a paso, cómo trabajar en Zentheris con la estructura nueva del repositorio: dónde poner cada archivo, qué comandos correr y cómo comprobar que tu trabajo quedó bien. Si algo de aquí choca con los `CLAUDE.md`, ganan ellos.

## 0. ¿Qué quieres hacer?

| Quiero… | Ve a |
|---|---|
| Saber dónde va cada archivo | [1. Mapa del repo](#1-mapa-del-repo) |
| Preparar mi computador la primera vez | [2.1](#21-preparar-el-equipo-la-primera-vez) |
| Levantar la API o la app y ver mi pantalla en vivo | [2.2](#22-levantar-la-api) y [2.3](#23-levantar-la-app-y-ver-tu-pantalla-en-vivo) |
| Correr las pruebas | [2.4](#24-correr-las-pruebas) y [2.5](#25-correr-check_integration) |
| Hacer una pantalla de la app | [3.1](#31-hacer-una-pantalla-de-la-app-ejemplo-consejos) |
| Programar el simulador de consumo | [3.2](#32-back-el-simulador-de-consumo) |
| Programar los estados, las alertas y los consejos | [3.3](#33-back-el-motor-de-estados-alertas-y-consejos) |
| Agregar una librería | [3.4](#34-agregar-una-librería) |
| Agregar o cambiar un endpoint | [3.5](#35-agregar-o-cambiar-un-endpoint) |
| Pedirle el trabajo a una IA | [4. Trabajar con una IA](#4-trabajar-con-una-ia) |
| Subir mi trabajo | [5. Antes de subir tu trabajo](#5-antes-de-subir-tu-trabajo) |
| Arreglar algo que no arranca | [6. Problemas comunes](#6-problemas-comunes-y-su-solución) |

**Las tareas y sus responsables están en Notion, y el diseño de cada pantalla está en Figma** (pide los enlaces al equipo).

**Tres palabras que se repiten:**
- **API** o **back:** el servidor en Python que guarda y calcula los datos. Vive en `api/`.
- **App** o **front:** la aplicación del celular. Vive en `app/`.
- **Contrato:** el archivo `docs/api/zentheris-api-v0.2.5.yaml`. Dice qué direcciones (endpoints) tiene la API, qué recibe y qué devuelve cada una. La API y la app lo siguen al pie de la letra.

---

## 1. Mapa del repo

La app le pide los datos a la API, y la API los guarda en Supabase (la base de datos). La app solo habla directo con Supabase para iniciar sesión y subir la foto de perfil.

```
app (celular)  →  API (Python)  →  Supabase (base de datos)
```

### Árbol comentado

```
Zentheris-Prototype/
├── CLAUDE.md                  reglas del proyecto (léelo primero)
├── README.md                  presentación corta
├── .github/workflows/tests.yml  pruebas automáticas que corren en GitHub
│
├── docs/                      LA FUENTE DE VERDAD: no se edita sin acuerdo del equipo
│   ├── reglas/                qué hace la app, pantalla por pantalla y tabla por tabla
│   ├── api/                   el contrato de la API
│   ├── datos/                 umbrales de estado, motor de referencia y perfiles de consumo
│   ├── textos/                todos los textos que ve el usuario
│   ├── diseno/                colores, tipografías, espaciados y fichas de componentes
│   ├── pruebas/               lista de pruebas que debe pasar la API
│   ├── guias/                 guías para personas (esta incluida)
│   └── MAPA-DE-INTEGRACION.md una fila por endpoint: qué archivo lo atiende en la API y en la app
│
├── api/                       BACK (Python)
│   ├── app/
│   │   ├── main.py            arranca la API
│   │   ├── routers/           reciben la petición, revisan los datos y llaman al servicio
│   │   ├── services/          hacen el trabajo de cada endpoint
│   │   ├── domain/            cálculos puros: simulador, estados, alertas, consejos
│   │   ├── data/              leen y escriben en la base de datos
│   │   ├── schemas/           forma exacta de lo que entra y sale (igual al contrato)
│   │   ├── security/          quién es el usuario y qué puede hacer
│   │   └── config_files/      copias de los umbrales y los textos del back
│   ├── tests/                 pruebas, una carpeta por grupo
│   └── .env.example           plantilla de variables de entorno
│
├── app/                       FRONT (celular)
│   ├── src/
│   │   ├── app/               rutas: un archivo por dirección (consejos.tsx → /consejos)
│   │   ├── screens/           pantallas y sus hooks de datos
│   │   ├── components/        piezas visuales reutilizables
│   │   ├── theme/             colores, espaciados, tipografías y fuentes (tokens)
│   │   ├── texts/             catálogo de textos y la función t()
│   │   ├── format/            números, kW, kWh, pesos, % y fechas en formato colombiano
│   │   ├── api/               funciones para llamar a cada endpoint
│   │   └── state/             caché de datos (React Query) y sesión
│   ├── assets/fonts/          fuentes (Satoshi va aquí, pero no se sube a git)
│   └── .env.example           plantilla de variables de entorno
│
├── supabase/migrations/       cambios de la base de datos, numerados
└── scripts/check_integration.py  revisa que contrato, API, app y mapa coincidan
```

### ¿Dónde va cada cosa?

| Quiero… | Va en… | Ojo |
|---|---|---|
| Una pantalla | `app/src/screens/<Pantalla>/<Pantalla>.tsx` y su ruta en `app/src/app/` | La ruta solo muestra la pantalla |
| Los datos de una pantalla | `app/src/screens/<Pantalla>/use<Pantalla>Data.ts` | Un hook por pantalla |
| Una pieza visual reutilizable | `app/src/components/` | Nombre y propiedades de `docs/diseno/componentes/index.d.ts` |
| Un color, espacio o tipografía | Se usa desde `app/src/theme/` | Nunca escribas `#05110E` ni `16` a mano |
| Un texto que ve el usuario | `docs/textos/catalogo.es-CO.json` y su copia `app/src/texts/catalogo.es-CO.json` | Nunca texto escrito a mano en la pantalla |
| Llamar a un endpoint desde la app | Ya existe en `app/src/api/` | Una función por endpoint |
| La lógica de un endpoint | `api/app/services/<grupo>.py` | Revisa siempre que el usuario pertenezca al hogar y tenga permiso |
| Un cálculo (simulador, estados…) | `api/app/domain/` | Sin base de datos ni FastAPI |
| Una consulta a la base | `api/app/data/<grupo>.py` | — |
| Una prueba del back | `api/tests/<grupo>/` | Muchas ya existen vacías: se activan |
| Una tabla o columna nueva | Una migración nueva en `supabase/migrations/` | Nunca se edita una migración vieja |
| Una clave o contraseña | Solo en tu `api/.env` o `app/.env` | **Nunca en git:** el repositorio es público |

---

## 2. Comandos del día a día

Los comandos van para **Git Bash** o la terminal de VS Code. En PowerShell, cambia `cp` por `Copy-Item` y `mkdir -p` por `New-Item -ItemType Directory -Force`.

### 2.1 Preparar el equipo la primera vez

Necesitas Git, Node 24 y [uv](https://docs.astral.sh/uv/getting-started/installation/) (el instalador de Python del proyecto; instala Python solo).

1. Trae el repositorio (si ya lo tienes, salta al paso 2):
   ```bash
   git clone https://github.com/Thomasvtf/Zentheris-Prototype.git
   cd Zentheris-Prototype
   ```
2. Ponte en tu rama y trae lo último:
   ```bash
   git switch <tu-rama>
   git pull
   ```
3. Crea tus archivos de variables de entorno desde las plantillas. Para trabajar en local no necesitas llenarlos; las claves reales te las pasa el equipo por privado.
   ```bash
   cp api/.env.example api/.env
   cp app/.env.example app/.env
   ```
   En `app/.env`, todo lo que empieza por `EXPO_PUBLIC_` lo puede leer cualquiera: ahí nunca va una clave secreta.
4. Instala Satoshi, la fuente de los títulos. Git no la sube, así que cada uno la pone en su equipo:
   1. Descárgala gratis de [fontshare.com/fonts/satoshi](https://www.fontshare.com/fonts/satoshi).
   2. Crea la carpeta, que no viene en el repositorio:
      ```bash
      mkdir -p app/assets/fonts/satoshi
      ```
   3. Copia `Fonts/OTF/Satoshi-Bold.otf` del archivo descargado en `app/assets/fonts/satoshi/Satoshi-Bold.otf`, con ese nombre exacto.
5. Instala las dependencias de la API y de la app:
   ```bash
   cd api && uv sync && cd ..
   cd app && npm ci && cd ..
   ```
   `npm ci` tarda unos 4 minutos. Los avisos `npm warn ERESOLVE` son normales.

### 2.2 Levantar la API

```bash
cd api
uv run uvicorn app.main:app --reload
```

- Abre `http://localhost:8000/docs`: ahí ves y pruebas todos los endpoints.
- `http://localhost:8000/api/v1/salud` debe responder `{"estado":"ok"}`.
- **Hoy casi todos los endpoints responden 501** («todavía no implementado»): existe la dirección, pero falta su lógica. Se van llenando con las recetas 3.2, 3.3 y 3.5.
- `--reload` reinicia la API sola cada vez que guardas un archivo.

### 2.3 Levantar la app y ver tu pantalla en vivo

```bash
cd app
npx expo start --clear
```

**En el navegador (lo más rápido):**
1. Con la terminal abierta, presiona `w`, o abre `http://localhost:8081`.
2. Para ir directo a tu pantalla, escribe su ruta: `http://localhost:8081/consejos`.
3. **La primera vez, la compilación web tarda 1 a 2 minutos.** Si abres la ruta antes, la app cae en la pantalla principal con un círculo de carga: espera y recarga.
4. La ruta `http://localhost:8081/catalogo-componentes` (solo en desarrollo) muestra colores, tipografías, íconos y gráficos. Si arriba dice «Satoshi sí», la fuente quedó bien instalada.

**En el celular:**
1. Instala la app **Expo Go** desde la tienda de tu celular.
2. Conecta el celular y el computador a la misma red Wi-Fi.
3. Escanea con Expo Go el código QR que aparece en la terminal.
4. Si tu pantalla pide datos a la API, el celular no entiende `localhost`:
   - en `app/.env`, cambia `EXPO_PUBLIC_API_URL` por la IP de tu computador, por ejemplo `http://192.168.1.20:8000` (la ves con `ipconfig`);
   - levanta la API con `uv run uvicorn app.main:app --reload --host 0.0.0.0`;
   - reinicia Expo con `npx expo start --clear`.

Cada vez que guardas un archivo, la pantalla se actualiza sola.

### 2.4 Correr las pruebas

**Back** (desde `api/`):
```bash
uv run ruff check .
uv run pytest
```
- `ruff` revisa el estilo del código: debe decir `All checks passed!`.
- `pytest` corre las pruebas. Hoy da **99 que pasan y 35 omitidas** (`skipped`). Las omitidas son pruebas vacías que esperan su tarea (recetas 3.2 y 3.3).

**App** (desde `app/`):
```bash
npm run typecheck
npm test
```
- `typecheck` revisa los tipos de TypeScript: no debe mostrar errores. Si falla con `"/explore"` después de haber corrido Expo, mira la [sección 6](#6-problemas-comunes-y-su-solución).
- `npm test` corre las pruebas de formatos y textos: hoy son 24.

### 2.5 Correr `check_integration`

Desde `api/`:
```bash
uv run python ../scripts/check_integration.py
```

Revisa dos cosas:
- **Copias:** que `api/app/config_files/` y `app/src/texts/catalogo.es-CO.json` sean idénticos a sus originales en `docs/`.
- **Integración:** que cada endpoint del contrato tenga su función en el router, en el servicio y en la app, y su fila en `docs/MAPA-DE-INTEGRACION.md`, todos con el mismo nombre.

Debe terminar en `Contrato 40 · routers 40 · app 40 · mapa 40 · OK`.

### 2.6 Cuando algo no arranca

1. Lee el último mensaje de error de la terminal: casi siempre dice qué falta.
2. Busca el mensaje en [6. Problemas comunes](#6-problemas-comunes-y-su-solución).
3. Si cambiaste de rama o hiciste `git pull`, reinstala: `uv sync` en `api/` y `npm ci` en `app/`.
4. Reinicia limpiando la caché: `npx expo start --clear`.

---

## 3. Recetas

Cada receta tiene las mismas partes: qué vas a construir, de qué te guías, dónde va cada archivo, el paso a paso, cómo se conecta con lo demás, cómo saber que quedó bien y qué decirle a una IA.

### 3.1 Hacer una pantalla de la app (ejemplo: Consejos)

**Qué vas a construir.** La pantalla Consejos: un título, la lista de consejos de ahorro (título, descripción y prioridad; los completados al final y opacos) y, si no hay pendientes, la tarjeta «¡Todo bajo control!».

**De qué te guías.**

| Qué | Dónde |
|---|---|
| Qué muestra la pantalla | `docs/reglas/reglas-de-negocio-v4.9.md`, sección «6.8 Consejos» (cada pantalla tiene su sección 6.x) |
| Cómo se ve | El Figma del equipo, página «Pantallas» (pide el enlace) |
| Las piezas visuales | Las fichas de `docs/diseno/componentes/`: para Consejos, `TipCard.md`, `TipList.md`, `PriorityTag.md` y `StateMessage.md`. Sus propiedades están en `index.d.ts` |
| Colores, espaciados y tipografías | `app/src/theme/` (se ven en `/catalogo-componentes`) |
| Textos | `app/src/texts/catalogo.es-CO.json`: para Consejos, las claves `consejos.*` |
| Qué endpoint usa | `docs/MAPA-DE-INTEGRACION.md`, fila de la pantalla: Consejos usa `listarConsejos` (`listTips`) y `actualizarEstadoConsejo` (`updateTipStatus`), con el hook `useTipsData` |

Si tu rama ya tiene una maqueta de la pantalla, úsala como punto de partida y pásala a esta estructura.

**Dónde va cada archivo.**
```
app/src/app/consejos.tsx                  la ruta: solo muestra la pantalla
app/src/screens/Tips/TipsScreen.tsx       la pantalla
app/src/screens/Tips/useTipsData.ts       el hook que pide los datos
app/src/components/<Componente>.tsx       las piezas visuales que falten
```

**Antes de empezar, lo que todavía no existe en `main`:**
- **Los componentes del sistema de diseño** (`TipCard`, `StateMessage`, `Skeleton`…): solo están sus fichas. Mientras tanto, arma la vista con `View` y `Text` y los tokens, como en el ejemplo de abajo. Si vas a crear uno de verdad, hazlo en `app/src/components/` con el nombre y las propiedades de `index.d.ts`, y avisa al equipo para que nadie lo haga dos veces.
- **El proveedor de React Query** (la caché que usan los hooks) no está montado. La primera persona que haga un hook lo agrega en `app/src/app/_layout.tsx`, en un PR pequeño y avisando al equipo (ese archivo lo tocan todos):
  ```tsx
  import { QueryClientProvider } from '@tanstack/react-query';
  import { queryClient } from '@/state/queryClient';
  // …y dentro de Layout(), envuelve todo lo que devuelve:
  <QueryClientProvider client={queryClient}>
    {/* StatusBar y Tabs, como están */}
  </QueryClientProvider>
  ```
- **El inicio de sesión y los endpoints de la API** todavía no están hechos: hoy la pantalla recibe un 501 y muestra su estado de error. Eso es lo esperado. Para ver la lista con datos mientras tanto, mira el paso 6.
- **La carga de las fuentes al arrancar la app** tampoco existe (hoy solo las carga el catálogo). Mientras no exista, no uses los estilos de título `display-*`: usa `ui-*` y `body-*`, como en el ejemplo, y cámbialos cuando esté lista.

**Paso a paso.**

1. **Crea el hook** `app/src/screens/Tips/useTipsData.ts`. Pide primero el hogar actual (para saber su `id`) y después sus consejos. La clave de cada consulta empieza por el nombre del endpoint en el contrato (`operationId`):
   ```ts
   import { useQuery } from '@tanstack/react-query';

   import { listTips } from '@/api/alertsTips';
   import { getCurrentHousehold } from '@/api/households';
   import { queryKey } from '@/state/queryKeys';

   /** Datos de la pantalla Consejos: primero el hogar actual y después sus consejos. */
   export function useTipsData() {
     const hogar = useQuery({
       queryKey: queryKey('obtenerHogarActual'),
       queryFn: getCurrentHousehold,
     });
     const hogarId = hogar.data?.id;

     const consejos = useQuery({
       queryKey: queryKey('listarConsejos', hogarId),
       queryFn: () => listTips(hogarId as string),
       enabled: hogarId !== undefined,
     });

     return {
       consejos: consejos.data?.consejos ?? [],
       cargando: hogar.isPending || (hogarId !== undefined && consejos.isPending),
       error: hogar.error ?? consejos.error,
       reintentar: () => (hogar.error ? hogar.refetch() : consejos.refetch()),
     };
   }
   ```
   Los tipos de `consejos` (`titulo`, `descripcion`, `prioridad`, `estado`…) salen solos del contrato: TypeScript te avisa si escribes un campo que no existe.

2. **Crea la pantalla** `app/src/screens/Tips/TipsScreen.tsx` con sus tres estados (**cargando**, **error** y **datos o vacío**):
   ```tsx
   import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
   import { Lightbulb } from 'lucide-react-native';

   import { toErrorTextKey } from '@/api/errors';
   import { t } from '@/texts';
   import { colors, fontFamilyFor, radius, spacing, typography } from '@/theme';

   import { useTipsData } from './useTipsData';

   /** Convierte un estilo de texto de los tokens en estilo de React Native. */
   function textStyle(name: 'ui-m-semibold' | 'body-s-regular' | 'ui-s-etiqueta-12') {
     const s = typography[name];
     return { fontFamily: fontFamilyFor(s.family, s.fontWeight), fontSize: s.fontSize, lineHeight: s.lineHeight };
   }

   export function TipsScreen() {
     const { consejos, cargando, error, reintentar } = useTipsData();

     if (cargando) {
       return (
         <View style={styles.centro}>
           <ActivityIndicator color={colors['accent-primary']} accessibilityLabel={t('comun.cargando')} />
         </View>
       );
     }

     if (error) {
       const clave = toErrorTextKey(error);
       return (
         <View style={styles.centro}>
           <Text style={styles.titulo}>{t(`${clave}.titulo`)}</Text>
           <Text style={styles.cuerpo}>{t(`${clave}.cuerpo`)}</Text>
           <Pressable onPress={reintentar} accessibilityRole="button">
             <Text style={styles.accion}>{t('comun.reintentar')}</Text>
           </Pressable>
         </View>
       );
     }

     return (
       <View style={styles.pantalla}>
         <Text style={styles.encabezado}>{t('consejos.encabezado')}</Text>
         <FlatList
           data={consejos}
           keyExtractor={(c) => c.id}
           ListEmptyComponent={
             <View style={styles.card}>
               <Lightbulb color={colors['accent-primary']} size={24} />
               <Text style={styles.titulo}>{t('consejos.vacio_titulo')}</Text>
               <Text style={styles.cuerpo}>{t('consejos.vacio_cuerpo')}</Text>
             </View>
           }
           renderItem={({ item }) => (
             <View style={[styles.card, item.estado === 'completada' && styles.completado]}>
               <Text style={styles.titulo}>{item.titulo}</Text>
               <Text style={styles.cuerpo}>{item.descripcion}</Text>
               <Text style={styles.etiqueta}>{t(`consejos.prioridad_${item.prioridad}`)}</Text>
             </View>
           )}
         />
       </View>
     );
   }

   const styles = StyleSheet.create({
     pantalla: { flex: 1, backgroundColor: colors['background-default'], padding: spacing['20'], gap: spacing['16'] },
     centro: { flex: 1, backgroundColor: colors['background-default'], alignItems: 'center', justifyContent: 'center', gap: spacing['8'], padding: spacing['20'] },
     encabezado: { ...textStyle('ui-m-semibold'), color: colors['text-primary'] }, // display-l cuando exista la carga de fuentes
     card: { backgroundColor: colors['background-surface'], borderRadius: radius.lg, padding: spacing['16'], gap: spacing['8'], marginBottom: spacing['12'] },
     completado: { opacity: 0.5 },
     titulo: { ...textStyle('ui-m-semibold'), color: colors['text-primary'] },
     cuerpo: { ...textStyle('body-s-regular'), color: colors['text-muted'] },
     etiqueta: { ...textStyle('ui-s-etiqueta-12'), color: colors['text-accent'] },
     accion: { ...textStyle('ui-m-semibold'), color: colors['accent-primary'] },
   });
   ```
   Qué hace cada parte:
   - **Colores:** `colors['background-default']`, `colors['text-primary']`… Los nombres están en `app/src/theme/tokens.ts`. Los colores rojo y amarillo solo se usan para avisar un problema (crítico o elevado).
   - **Espaciados y bordes:** `spacing['16']`, `radius.lg`.
   - **Tipografías:** `typography['ui-m-semibold']` y similares, con `fontFamilyFor` para la fuente.
   - **Íconos:** de `lucide-react-native` (por ejemplo, `Lightbulb`), con color de los tokens. Busca los nombres en [lucide.dev](https://lucide.dev).
   - **Textos:** `t('consejos.encabezado')`. Si el texto lleva un valor, `t('clave', { nombre })`; para plurales, `plural('clave', n)`.
   - **Números:** si la pantalla muestra consumo o dinero, usa `formatNumber(v, 2)` para kW, `formatNumber(v, 1)` para kWh, `formatCOP(v)` y `formatPercent(v)` de `@/format`. Un valor `null` significa «sin dato»: nunca lo muestres como 0.
   - **Errores:** `toErrorTextKey(error)` convierte cualquier error en una clave del catálogo, y tú le agregas `.titulo` o `.cuerpo`.

3. **Conecta la ruta.** Reemplaza todo el contenido de `app/src/app/consejos.tsx` por:
   ```tsx
   import { TipsScreen } from '@/screens/Tips/TipsScreen';

   export default TipsScreen;
   ```

4. **Si falta un texto**, agrégalo primero en `docs/textos/catalogo.es-CO.json` y después copia el archivo completo a `app/src/texts/catalogo.es-CO.json`. `check_integration` falla si las dos copias no son iguales. Cambiar textos se acuerda con el equipo.

5. **Míralo en vivo** con la API y la app levantadas (2.2 y 2.3), en `http://localhost:8081/consejos`. Hoy verás unos segundos de carga (la app reintenta 3 veces) y después «Algo salió mal de nuestro lado» con «Reintentar», porque la API responde 501. Eso confirma que la pantalla sí llama a la API.

6. **Para ver la lista con datos mientras la API no está lista**, cambia en tu equipo la función `queryFn` de los consejos por datos de ejemplo, con la misma forma que el contrato. **No subas ese cambio.**
   ```ts
   queryFn: async () => ({ consejos: [/* objetos con id, titulo, descripcion, prioridad, estado… */] }),
   ```

**Cómo conectarlo con lo demás.**
- **Endpoint correcto:** la función que llamas (`listTips`) lleva en su comentario `@operationId listarConsejos`. Debe coincidir con la fila de la pantalla en `docs/MAPA-DE-INTEGRACION.md`.
- **Tipos:** si el contrato cambia, `npm run generate:api-types` actualiza `app/src/api/schema.d.ts` y `npm run typecheck` te muestra qué romper.
- **Back:** el endpoint lo hace quien tome su tarea en la API (receta 3.5). Cuando responda de verdad, tu pantalla mostrará los datos sin cambios.

**Cómo saber que quedó bien.**
- [ ] `npm run typecheck` y `npm test` sin errores.
- [ ] Se ve en el navegador y en el celular; se probaron los tres estados (cargando, error, datos o vacío).
- [ ] Ningún color, tamaño ni texto escrito a mano: todo sale de `@/theme` y de `t()`.
- [ ] Los números usan `@/format` y `null` se muestra como «sin dato».
- [ ] La ruta en `app/src/app/` solo muestra la pantalla.
- [ ] El endpoint que usas coincide con la fila del mapa.
- [ ] Comparado con el Figma y con la sección 6.x de las reglas.
- [ ] En el PR dices en qué lo probaste (web, Android, iOS) y en qué no.

**Qué decirle a una IA.** Usa la [plantilla 4.1](#41-hacer-una-pantalla).

### 3.2 Back: el simulador de consumo

**Qué vas a construir.** El simulador genera, hora por hora, el consumo de cada zona de una casa. Se usa en tres momentos:
1. al crear el hogar, para llenar los 30 días anteriores de una vez;
2. antes de cada consulta, para completar las horas que falten;
3. cada hora, para generar la hora nueva.

Cada casa tiene una **personalidad de consumo** (compacto, eficiente, intermedio, familiar o amplio). Se elige según el tipo de vivienda y sus zonas, y define cuánto gasta cada zona y a qué horas.

**De qué te guías.**

| Qué | Dónde |
|---|---|
| El simulador de referencia, que ya funciona | `docs/datos/referencia/Zentheris_v4.3_Avance_03_Conjuntos_Calibrados.zip` → `codigo/zentheris_sim/` (`simulador.py`, `asignacion.py`, `semillas.py`, `constantes.py`) |
| Sus 59 pruebas | Mismo zip → `pruebas/` |
| Los parámetros de las 5 personalidades | `docs/datos/perfiles/` (en la base, tabla `perfiles_simulacion`, cargada por `supabase/migrations/…_0006_semilla_perfiles_simulacion.sql`) |
| Las reglas | `docs/reglas/reglas-de-negocio-v4.9.md` (busca «simul» y «backfill») |
| Las pruebas que debe pasar la API | `docs/pruebas/matriz-pruebas-backend-v1.md`, grupos Z y B |

Para ver el simulador de referencia funcionando (sirve igual en PowerShell y en Git Bash), desde `api/`:
1. Descomprime el paquete en una carpeta temporal `_referencia`:
   ```bash
   uv run python -m zipfile -e ../docs/datos/referencia/Zentheris_v4.3_Avance_03_Conjuntos_Calibrados.zip _referencia
   ```
2. Corre sus 59 pruebas y vuelve a `api/`:
   ```bash
   cd _referencia/Zentheris_v4.3_Avance_03_Conjuntos_Calibrados
   uv run python -I -m unittest discover -s pruebas
   cd ../..
   ```
   Debe decir `Ran 59 tests … OK`.
3. Cuando termines (también la receta 3.3), borra la carpeta. Git no la ignora: **nunca la subas.**
   ```bash
   uv run python -c "import shutil; shutil.rmtree('_referencia')"
   ```

**Dónde va cada archivo.** Los archivos ya existen como esqueleto, con un `NotImplementedError` o un 501 que hay que reemplazar.

| Parte | Archivo | Qué hace |
|---|---|---|
| Dominio | `api/app/domain/simulator/` (hoy solo `__init__.py`) | El simulador, copiado del de referencia. Recibe el perfil como dato; no lee la base |
| Dominio | `api/app/domain/zone_rules.py` → `validate_zones` | Valida las zonas de la vivienda y elige la personalidad (como `asignacion.py`) |
| Datos | `api/app/data/households.py` y `api/app/data/readings.py` → `insert_readings_batch` | Leen el perfil del hogar y guardan las lecturas en lote |
| Servicio | `api/app/services/onboarding.py` → `create_household_onboarding` | Crea el hogar y genera los 30 días, todo junto |
| Servicio | `api/app/services/hour_recovery.py` → `fill_missing_hours` | Completa las horas que falten antes de responder |
| Servicio | `api/app/services/scheduler.py` → `start_scheduler` | Genera la hora nueva cada hora |
| Router | `api/app/routers/onboarding.py` | Ya está hecho: recibe `POST /onboarding` y llama al servicio |

**Lo que todavía no existe:** toda la lógica de la tabla anterior, y la conexión a la base desde las pruebas. Las 59 pruebas de referencia todavía no están en `api/tests/`.

**Paso a paso.**
1. Corre las 59 pruebas de referencia (arriba) para ver el comportamiento esperado.
2. Copia `codigo/zentheris_sim/` dentro de `api/app/domain/simulator/`. Cambia solo lo necesario para que el perfil llegue como dato (desde la tabla `perfiles_simulacion`) en vez de leerlo de un archivo. Pon los nombres de funciones y variables nuevas en inglés.
3. Copia sus 59 pruebas a una carpeta nueva, `api/tests/simulator/`, y ajusta los imports hasta que pasen con `uv run pytest tests/simulator`.
4. Implementa `validate_zones` en `zone_rules.py` y activa las pruebas Z: en `api/tests/zones/`, borra la línea `pytest.skip(...)` de cada archivo y escribe la prueba que describe su comentario.
5. Implementa `insert_readings_batch` (en lote, no fila por fila) y `create_household_onboarding`, y activa las pruebas B de `api/tests/backfill/`.
6. Implementa `fill_missing_hours` y `start_scheduler`.

**Cómo conectarlo con lo demás.** El router llama al servicio; el servicio pide el perfil a `data/`, se lo pasa al simulador de `domain/` y guarda el resultado con `data/readings.py`. El dominio nunca importa nada de `data/` ni de FastAPI (una prueba lo revisa).

**Cómo saber que quedó bien.**
- [ ] `uv run pytest tests/simulator` pasa las 59.
- [ ] Las pruebas Z y B ya no están omitidas y pasan (por ejemplo, un dúplex de 9 zonas genera exactamente 6.480 lecturas sin duplicados).
- [ ] `uv run pytest` completo y `uv run ruff check .` en verde; el número de omitidas bajó.
- [ ] `check_integration` en verde.
- [ ] Con la misma casa y la misma fecha, el simulador da siempre el mismo resultado.

**Qué decirle a una IA.** Usa la [plantilla 4.2](#42-back-simulador-o-motor).

### 3.3 Back: el motor de estados, alertas y consejos

**Qué vas a construir.** El motor toma las lecturas de consumo, las compara con su referencia (el promedio histórico o la meta del hogar) y decide el **estado** de cada valor: normal, elevado o crítico. Con eso genera las **alertas** (por ejemplo, «una zona entró en crítico») y los **consejos** de ahorro.

**De qué te guías.**

| Qué | Dónde |
|---|---|
| Los umbrales de cada estado | `docs/datos/umbrales-estado.v1.json` (copia en `api/app/config_files/`) |
| El motor de referencia, que ya funciona | `docs/datos/motor_estados_ref.py` (funciones `estado_relativo`, `estado_acumulado_meta`, `comparacion_periodo`, `es_pico`, `proyeccion_cierre`…) |
| Los 13 escenarios que debe reproducir | `docs/datos/test_escenarios_umbrales.py` |
| Los textos de alertas y consejos | `docs/textos/textos-backend.es-CO.json` (copia en `api/app/config_files/`) |
| Las reglas | `docs/reglas/reglas-de-negocio-v4.9.md`, secciones XI (estados), XIV (alertas) y XV (consejos) |
| Las pruebas que debe pasar la API | `docs/pruebas/matriz-pruebas-backend-v1.md`, grupos U y A |

Para ver los 13 escenarios pasar con el motor de referencia, descomprime el paquete en `api/_referencia` (paso 1 de la receta 3.2) y, desde `api/`:
```bash
uv run python -I ../docs/datos/test_escenarios_umbrales.py _referencia/Zentheris_v4.3_Avance_03_Conjuntos_Calibrados
```
Debe decir `Ran 13 tests … OK`. Al terminar, borra `_referencia` (paso 3 de la receta 3.2).

**Dónde va cada archivo** (todos existen como esqueleto):

| Parte | Archivo | Qué hace |
|---|---|---|
| Dominio | `api/app/domain/states.py` → `calculate_state` | Estado de un valor frente a su referencia |
| Dominio | `api/app/domain/history.py` → `compare_periods`, `detect_peak`, `project_period` | Comparar periodos, marcar el pico y proyectar el cierre |
| Dominio | `api/app/domain/alert_rules.py` → `evaluate_alert_rules`, `build_tips` | Qué alertas y qué consejos tocan |
| Dominio | `api/app/domain/formats.py` → `build_event_key`, `render_backend_text` | Clave única de cada alerta (para no repetirla) y texto de la plantilla con sus valores |
| Datos | `api/app/data/alerts.py`, `api/app/data/tips.py` | Guardan alertas y consejos |
| Servicio | `api/app/services/hour_recovery.py`, `api/app/services/alerts_tips.py`, `api/app/services/consumption.py` | Evalúan las alertas al generar horas nuevas y responden los endpoints |

**Lo que todavía no existe:** la lógica de todos estos archivos. Dependen del simulador (3.2) para tener lecturas.

**Paso a paso.**
1. Corre los 13 escenarios de referencia (arriba).
2. Implementa `calculate_state` y el resto de `states.py` y `history.py` siguiendo `motor_estados_ref.py`. Lee los umbrales del archivo de `config_files/`, nunca escritos a mano.
3. Activa las pruebas U de `api/tests/thresholds/` (borra el `pytest.skip(...)`). La U-01 debe reproducir los 13 escenarios con tu código.
4. Implementa `alert_rules.py` y `formats.py`. Las alertas se evalúan **solo sobre horas nuevas**, nunca sobre los 30 días que se generan al crear el hogar.
5. Conéctalas en `hour_recovery.py` y en los servicios, y activa las pruebas A de `api/tests/alerts/`.

**Cómo conectarlo con lo demás.** Cuando se genera una hora nueva (simulador), el servicio calcula su estado (dominio), evalúa las alertas y los consejos (dominio), arma el texto desde la plantilla (dominio) y los guarda (datos). Los endpoints de consumo, alertas y consejos solo leen lo guardado y le agregan el estado.

**Cómo saber que quedó bien.**
- [ ] Las pruebas U y A ya no están omitidas y pasan; la U-01 reproduce los 13 escenarios.
- [ ] Al crear un hogar con horas que serían críticas, se generan 0 alertas.
- [ ] Una misma alerta no se repite en la misma zona el mismo día.
- [ ] `uv run pytest`, `ruff` y `check_integration` en verde.

**Qué decirle a una IA.** Usa la [plantilla 4.2](#42-back-simulador-o-motor).

### 3.4 Agregar una librería

**Qué vas a construir.** Sumar una librería nueva a la app o a la API.

**De qué te guías.** Antes de instalar, revisa si alguna de las que ya están lo hace. Una librería nueva se acuerda con el equipo.

**Librerías de la app que ya están instaladas y cómo usarlas:**

| Librería | Para qué sirve | Ejemplo | Uso en una línea |
|---|---|---|---|
| `react-native-gifted-charts` | Gráficos de barras, línea y anillo | `app/src/screens/ComponentCatalog/chartSamples.tsx` | `import { BarChart } from 'react-native-gifted-charts';` |
| `lucide-react-native` | Íconos (nombres en [lucide.dev](https://lucide.dev)) | `app/src/screens/ComponentCatalog/ComponentCatalogScreen.tsx` | `<Lightbulb color={colors['accent-primary']} size={24} />` |
| `expo-linear-gradient` | Degradados de color | Todavía no hay uno en el código; la necesita `gifted-charts` | `<LinearGradient colors={[colors['accent-primary'], colors['accent-soft']]} />` |
| `@tanstack/react-query` (React Query) | Pedir datos a la API y guardarlos en caché | `app/src/state/queryClient.ts`, `app/src/state/queryKeys.ts` y el hook de la receta 3.1 | `useQuery({ queryKey: queryKey('listarConsejos', hogarId), queryFn: … })` |
| `@supabase/supabase-js` | **Solo** iniciar sesión y subir la foto de perfil; **nunca** para pedir datos (eso va por la API) | `app/src/state/supabase.ts` y `app/src/state/session.ts` | `getSupabase()` |
| `openapi-typescript` | Crear los tipos de TypeScript a partir del contrato | `app/src/api/schema.d.ts` (se genera solo) | `npm run generate:api-types` |

**En la app** (desde `app/`):
1. Instala con Expo, que elige la versión compatible:
   ```bash
   npx expo install <paquete>
   ```
2. Se actualizan solos `app/package.json` y `app/package-lock.json`: los dos van en tu commit.
3. Si la librería pide configuración, normalmente va en `app/app.json` (sección `plugins`) o en `app/metro.config.js`. Sigue su documentación.
4. Úsala en una pantalla o en el catálogo y míralo en vivo (2.3).

**En la API** (desde `api/`):
1. Instala con uv:
   ```bash
   uv add <paquete>
   ```
   Si solo se usa en pruebas: `uv add --dev <paquete>`.
2. Se actualizan solos `api/pyproject.toml` y `api/uv.lock`. Regenera también `requirements.txt` (lo usa el servidor):
   ```bash
   uv export --no-dev --no-hashes --format requirements-txt --output-file requirements.txt
   ```
3. Los tres archivos van en tu commit.

**Cómo saber que quedó bien.**
- [ ] `npm ci` (app) o `uv sync` (API) desde cero funciona.
- [ ] Las pruebas de 2.4 en verde.
- [ ] En la app, `npx expo export --platform android` termina sin errores (es lo que hace el CI).
- [ ] No cambiaste las versiones de Expo ni de React Native de paso.

**Qué decirle a una IA.** Usa la [plantilla 4.3](#43-librería-o-endpoint).

### 3.5 Agregar o cambiar un endpoint

**Qué vas a construir.** Un endpoint nuevo, o un cambio en uno que existe, de punta a punta: contrato, API, app y mapa.

**De qué te guías.** El contrato manda. **Cambiar el contrato se acuerda antes con el equipo.** Para implementar un endpoint que ya está en el contrato, salta al paso 3.

**Dónde va cada archivo** (ejemplo: `listarConsejos`):
```
docs/api/zentheris-api-v0.2.5.yaml        el contrato
api/app/schemas/alerts_tips.py            forma de la respuesta (ConsejosLista, Consejo)
api/app/routers/alerts_tips.py            la dirección GET /hogares/{hogar_id}/consejos
api/app/services/alerts_tips.py           list_tips: la lógica
api/app/data/tips.py                      la consulta a la base
api/tests/alerts/test_a05_…py             su prueba
app/src/api/alertsTips.ts                 listTips, con @operationId listarConsejos
docs/MAPA-DE-INTEGRACION.md               su fila
```

**Paso a paso.**
1. **Contrato** (solo si cambia): edita `docs/api/zentheris-api-v0.2.5.yaml` y valídalo. Desde `api/`:
   ```bash
   uv run python -I ../docs/api/validar_contrato.py ../docs/api/zentheris-api-v0.2.5.yaml ../docs/textos/mensaje_codigos.es-CO.json ../docs/textos/catalogo.es-CO.json
   ```
   Debe terminar con `"errores": []`.
2. **Schemas:** ajusta `api/app/schemas/<grupo>.py` con los mismos nombres, tipos y valores nulos que el contrato.
3. **Router:** en `api/app/routers/<grupo>.py`, la ruta lleva el mismo `operation_id` que el contrato y solo llama al servicio.
4. **Servicio:** en `api/app/services/<grupo>.py`, la función tiene el mismo nombre que la del router. Reemplaza el `raise NotImplementedOperation(...)` por la lógica. Primero comprueba que el usuario pertenezca al hogar (si no, 404) y tenga el permiso (si no, 403). Los errores siempre devuelven `{codigo, mensaje, detalles}`, nunca el texto de una excepción.
5. **Datos:** las consultas van en `api/app/data/<grupo>.py`.
6. **Prueba:** activa la prueba que corresponde en `api/tests/` (busca en el mapa la columna «Prueba»).
7. **App:** si el contrato cambió, regenera los tipos desde `app/` con `npm run generate:api-types`. La función del endpoint en `app/src/api/<grupo>.ts` lleva el comentario `@operationId <nombre>`.
8. **Mapa:** revisa que la fila en `docs/MAPA-DE-INTEGRACION.md` diga los nombres reales (router, servicio, función de la app).

**Qué revisa `check_integration`.** Que cada operación del contrato tenga, con el mismo nombre, su ruta y método en el router, su función en el servicio, su función con `@operationId` en la app y su fila en el mapa. Si falta una pieza o un nombre no coincide, falla y te dice cuál.

**Cómo saber que quedó bien.**
- [ ] `uv run pytest` en verde, incluida la prueba de paridad, que compara el contrato con lo que publica la API (`tests/contract/test_skeleton_matches_contract.py`).
- [ ] `check_integration` en verde.
- [ ] En `http://localhost:8000/docs` el endpoint responde lo que dice el contrato.
- [ ] Si tocaste la app: `npm run typecheck` en verde.

**Qué decirle a una IA.** Usa la [plantilla 4.3](#43-librería-o-endpoint).

---

## 4. Trabajar con una IA

Puedes pedirle una tarea a Claude Code o a otra IA. Funciona bien si le das el contexto correcto y revisas lo que entrega con las mismas pruebas que harías tú.

**Qué darle como referencia (siempre):**
- `CLAUDE.md` de la raíz y el de la carpeta donde trabaja (`app/CLAUDE.md` o `api/CLAUDE.md`). Claude Code los lee solo.
- Esta guía y la receta de tu tarea.
- Los archivos de «De qué te guías» de esa receta.

**Cómo verificar lo que entrega:**
1. Lee el resumen de qué archivos cambió. Si tocó archivos que no tenían que ver, pídele que lo deshaga.
2. Corre las pruebas de 2.4 y `check_integration` (2.5).
3. Repasa el checklist de la receta, punto por punto.
4. Si tiene interfaz, míralo tú en vivo (2.3).
5. Revisa que no haya escrito claves, `.env` ni textos a mano, ni haya inventado endpoints o campos que no están en el contrato.

### 4.1 Hacer una pantalla

```
Lee CLAUDE.md, app/CLAUDE.md y docs/guias/GUIA-DEL-EQUIPO.md (receta 3.1).
Tarea: hacer la pantalla <NOMBRE> en app/src/screens/<Carpeta>/<Pantalla>.tsx
con su hook use<Pantalla>Data.ts, y conectar su ruta app/src/app/<ruta>.tsx.
Guíate por: la sección 6.x «<NOMBRE>» de docs/reglas/reglas-de-negocio-v4.9.md,
las fichas <Componentes> de docs/diseno/componentes/ y la fila de la pantalla
en docs/MAPA-DE-INTEGRACION.md (endpoints y hook).
Reglas: colores, espaciados y tipografías solo desde @/theme; textos solo con t()
del catálogo; números con @/format; estados de carga, error y vacío; no inventes
endpoints ni campos. No toques otros archivos sin preguntarme.
Al final corre npm run typecheck y npm test, y dime qué probaste y qué no.
```

### 4.2 Back: simulador o motor

```
Lee CLAUDE.md, api/CLAUDE.md y docs/guias/GUIA-DEL-EQUIPO.md (receta 3.2 o 3.3).
Tarea: implementar <simulador | estados | alertas y consejos> en los archivos
de la receta (domain/, services/, data/).
Guíate por: <el zip de referencia en docs/datos/referencia/ | docs/datos/motor_estados_ref.py,
docs/datos/umbrales-estado.v1.json y docs/datos/test_escenarios_umbrales.py>.
Activa las pruebas <Z y B | U y A> de api/tests/ quitando su pytest.skip y escribiendo
lo que describe cada comentario. domain/ no importa FastAPI ni la base.
Al final corre uv run ruff check ., uv run pytest y
uv run python ../scripts/check_integration.py, y dime cuántas pruebas pasan y cuántas
siguen omitidas.
```

### 4.3 Librería o endpoint

```
Lee CLAUDE.md, el CLAUDE.md de <app | api> y docs/guias/GUIA-DEL-EQUIPO.md (receta 3.4 o 3.5).
Tarea: <agregar la librería X para Y | implementar el endpoint operationId Z>.
Sigue el paso a paso de la receta en orden. Para un endpoint: mismo operation_id en
router, servicio, app y mapa; comprueba membresía y permiso; errores {codigo, mensaje, detalles}.
No cambies el contrato ni las versiones de Expo sin preguntarme.
Al final corre las pruebas de la sección 2.4 y check_integration, y dime el resultado.
```

---

## 5. Antes de subir tu trabajo

**Checklist:**
- [ ] Pruebas en verde: `ruff`, `pytest` y `check_integration` (si tocaste `api/` o `docs/`); `typecheck` y `npm test` (si tocaste `app/`).
- [ ] Colores, espaciados y tipografías desde los tokens; textos desde el catálogo.
- [ ] Sin claves, contraseñas ni archivos `.env` (`git status` no debe mostrar `.env`).
- [ ] Sin archivos de Satoshi (`git status` no debe mostrar `satoshi`).
- [ ] Solo los archivos de tu tarea.

**Nombre de la rama:** `<tipo>/<descripcion-corta>` desde `main`, por ejemplo `feat/pantalla-consejos`. Tipos: `feat` (algo nuevo), `fix` (arreglo), `docs`, `refactor`, `build`, `ci` y `test`. Si trabajas en tu rama personal (`<Persona>/feat-<Tema>`), sigue en ella.

**Commit:** `tipo(alcance): descripción en español`, por ejemplo:
```bash
git add app/src/screens/Tips app/src/app/consejos.tsx
git commit -m "feat(app): pantalla de consejos con sus estados"
git push -u origin <tu-rama>
```

**Abrir el PR:**
1. En GitHub, botón «Compare & pull request», hacia `main` (o hacia la rama que te indiquen).
2. En la descripción: qué hiciste, qué pantallas o endpoints toca, qué probaste y qué no (por ejemplo, «no probado en iOS»).
3. **Todo PR hacia `main` necesita la aprobación de otra persona del equipo.** No te apruebes a ti mismo.
4. Al fusionar, usa siempre **«Create a merge commit»**, nunca «Squash» ni «Rebase», y borra la rama después.

**Si tu PR depende de otro (cadena):** fusiona el primero, cambia la base del siguiente a `main` y solo después borra la rama del primero. Si la borras antes, GitHub cierra el PR siguiente.

---

## 6. Problemas comunes y su solución

| Ves esto | Qué pasa | Qué hacer |
|---|---|---|
| `Port 8081 is being used by another process` | Ya hay otro Expo abierto | Cierra la otra terminal de Expo, o usa `npx expo start --clear --port 8082` |
| `address already in use` al levantar la API | Ya hay otra API abierta en el puerto 8000 | Ciérrala, o usa `--port 8001` y cambia `EXPO_PUBLIC_API_URL` en `app/.env` |
| La ruta abre la pantalla principal con un círculo de carga | La primera compilación web no había terminado | Espera 1 a 2 minutos y recarga |
| Tus cambios no aparecen | Expo guardó una versión vieja | Detén Expo (`Ctrl+C`) y corre `npx expo start --clear` |
| `[fonts] Falta app/assets/fonts/satoshi/Satoshi-Bold.otf` en la consola | No instalaste Satoshi | Paso 4 de 2.1, con el nombre exacto |
| `npm run typecheck` falla con `Type '"/explore"' is not assignable…` en `app-tabs.web.tsx` | Expo generó tipos de rutas que chocan con un archivo viejo de la plantilla | Borra la carpeta `app/.expo/types` y vuelve a correr `npm run typecheck` (se corregirá al limpiar la plantilla) |
| La pantalla dice «Sin conexión» | La API no está levantada o la app no la encuentra | Levanta la API (2.2). En el celular, usa la IP del computador (2.3) |
| La pantalla dice «Algo salió mal de nuestro lado» | El endpoint responde 501: todavía no está implementado | Es lo esperado mientras no se haga en la API. Para diseñar, usa datos de ejemplo (receta 3.1, paso 6) |
| `pytest` dice `35 skipped` | Pruebas vacías que esperan su tarea | Es normal. Bajan a medida que se activan (recetas 3.2 y 3.3) |
| `check_integration` dice que una copia no es igual | Cambiaste un archivo de `docs/` y no su copia, o al revés | Copia el original de `docs/` encima de la copia (`api/app/config_files/` o `app/src/texts/`) |
| `check_integration` dice que falta una operación o un nombre | Router, servicio, app o mapa no coinciden | Revisa los nombres con la receta 3.5 |
| `uv: command not found` | No tienes uv | Instálalo ([docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/)) y abre otra terminal |
| `npm warn ERESOLVE overriding peer dependency` | Aviso de versiones de una librería interna | Es normal: no hagas nada |
| Expo dice «An update for expo is available» o `expo-doctor` marca 1 falla | Hay versiones de Expo más nuevas | No actualices por tu cuenta: se hará en una tarea aparte |

---

## 7. Para profundizar

| Archivo | Para qué sirve |
|---|---|
| [`CLAUDE.md`](../../CLAUDE.md), [`app/CLAUDE.md`](../../app/CLAUDE.md), [`api/CLAUDE.md`](../../api/CLAUDE.md) | Reglas completas del proyecto y de cada carpeta |
| [`docs/reglas/reglas-de-negocio-v4.9.md`](../reglas/reglas-de-negocio-v4.9.md) | Qué hace la app: reglas (RN-*), tablas y pantallas |
| [`docs/api/zentheris-api-v0.2.5.yaml`](../api/zentheris-api-v0.2.5.yaml) | El contrato de la API |
| [`docs/MAPA-DE-INTEGRACION.md`](../MAPA-DE-INTEGRACION.md) | Qué archivo atiende cada endpoint en la API y en la app |
| [`docs/decisiones/registro-decisiones-cierre-2026-11-03.md`](../decisiones/registro-decisiones-cierre-2026-11-03.md) | Por qué se decidió cada cosa (DC-*) |
| [`docs/diseno/CORRECCIONES-LEER-PRIMERO.md`](../diseno/CORRECCIONES-LEER-PRIMERO.md) y [`docs/diseno/componentes/`](../diseno/componentes/) | Correcciones del sistema de diseño y fichas de los componentes |
| [`docs/pruebas/matriz-pruebas-backend-v1.md`](../pruebas/matriz-pruebas-backend-v1.md) | Lista de pruebas que debe pasar la API |
| [`docs/historias/historias-usuario-v5-mvp.md`](../historias/historias-usuario-v5-mvp.md) | Las historias de usuario del MVP |
| [`docs/guias/GUIA-2-interfaces-app.md`](GUIA-2-interfaces-app.md) y [`docs/guias/GUIA-3-backend-y-arquitectura.md`](GUIA-3-backend-y-arquitectura.md) | Explicación más larga de la app y del back |
| [`docs/PENDIENTES-DE-REFACTORIZACION.md`](../PENDIENTES-DE-REFACTORIZACION.md) y [`docs/PENDIENTES-DE-CONFIGURACION.md`](../PENDIENTES-DE-CONFIGURACION.md) | Tareas pendientes del repositorio y de la configuración |
| [`app/assets/fonts/README.md`](../../app/assets/fonts/README.md) | Detalle de las fuentes y de cómo instalar Satoshi |
