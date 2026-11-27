# Plan de pruebas de Zentheris

Estándar del proyecto para planear, diseñar, ejecutar y registrar las pruebas de software. Sirve igual para una persona del equipo que para una herramienta de IA.

> **Este documento no lleva resultados, fechas ni conteos.** Dice *cómo* se prueba. El estado de cada prueba, sus resultados y sus evidencias viven en el **registro de pruebas** (`09_pruebas/REGISTRO-DE-PRUEBAS.md`). Así este plan casi no cambia con el tiempo.

> **Rutas.** Las rutas de este documento son las de la carpeta de documentación del proyecto. En el repositorio, `09_pruebas/` está en `docs/pruebas/`. Si una ruta no existe en el repositorio, ese archivo está solo en la carpeta de documentación.

---

## Cómo usar este documento

| Si quieres… | Ve a |
|---|---|
| Entender qué es calidad para el proyecto | [1. Marco de calidad](#1-marco-de-calidad) |
| Saber qué se prueba y dónde | [2. Alcance](#2-alcance) y [3. Entornos](#3-entornos-de-prueba) |
| Saber qué tipos de prueba existen y dónde vive cada uno | [4. Niveles y tipos](#4-niveles-y-tipos-de-prueba) |
| Escribir una prueba nueva | [5. Diseño de casos](#5-diseño-de-casos-de-prueba) y [6. Identificadores y plantilla](#6-identificadores-y-plantilla-de-caso) |
| Ejecutar una prueba y anotar el resultado | [8. Ejecución y evidencias](#8-ejecución-y-evidencias) |
| Saber en qué orden se prueba | [9. La ronda de pruebas](#9-la-ronda-de-pruebas-en-3-etapas) |
| Ver qué pruebas faltan o cuáles pasaron | El registro de pruebas (`09_pruebas/REGISTRO-DE-PRUEBAS.md`) |
| Mantener este plan al día | [12. Mantenimiento](#12-mantenimiento-de-este-documento) |
| Trabajar con una IA sobre las pruebas | [13. Reglas para herramientas de IA](#13-reglas-para-herramientas-de-ia) |

---

## 1. Marco de calidad

### 1.1 ISO/IEC 25010: qué es un software de calidad

La norma describe la calidad del producto en características. Cada caso de prueba se marca con la característica que comprueba; así se ve si alguna queda sin cubrir.

| Característica | Qué significa en Zentheris | Grupos de casos que la cubren |
|---|---|---|
| **Adecuación funcional** | Hace lo que dicen las reglas de negocio: consumo, zonas, historial, alertas, metas, tarifa, miembros | Z, B, U, A, I, SR, FA, AC |
| **Eficiencia de desempeño** | Responde a tiempo: crear el hogar, abrir pantallas, primera llamada después de una pausa del servidor | B-03, RD |
| **Compatibilidad** | La app y la API hablan el mismo idioma (contrato); funciona junto a Supabase y al servicio de correo | C, CO |
| **Usabilidad** | Se entiende y se usa fácil; textos claros; accesible con lector de pantalla, texto grande y daltonismo | US, DA, FA |
| **Fiabilidad** | Se recupera de fallos: horas que faltan, errores sin dejar datos a medias | B-02, B-04, SR |
| **Seguridad** | Cada persona ve solo su hogar y lo que sus permisos le dejan; no se exponen claves ni errores internos | P, R, S, I |
| **Mantenibilidad** | El código se puede cambiar sin romper lo anterior: pruebas automáticas, revisión de estilo y contrato | Pruebas automáticas, regresión |
| **Portabilidad** | Funciona en Android e iOS y en distintos tamaños de pantalla | DA |

> La revisión más reciente de la norma cambia el nombre de algunas características (por ejemplo, usabilidad pasa a «capacidad de interacción» y portabilidad a «flexibilidad») y agrega «protección». Para este proyecto se usan las 8 de la tabla.

### 1.2 ISO/IEC/IEEE 29119: cómo se organizan las pruebas

La norma define el proceso y los documentos de prueba. En Zentheris cada documento de la norma tiene un lugar fijo:

| Documento según la norma | Dónde está en Zentheris |
|---|---|
| Plan de pruebas | Este documento |
| Diseño y especificación de casos | La matriz de pruebas del backend y el registro de pruebas (ambos en `09_pruebas/`) |
| Registro de ejecución | Registro de pruebas, sección «Historial de ejecuciones» |
| Informe de incidencias | Registro de pruebas, sección «Hallazgos», y la lista de pendientes (`PENDIENTES.md`, en la raíz) |
| Informe de cierre | Registro de pruebas, sección «Informe de cierre» |
| Técnicas de diseño | [5. Diseño de casos](#5-diseño-de-casos-de-prueba) |

### 1.3 Ciclo PHVA aplicado a las pruebas

| Fase | Qué se hace | Resultado |
|---|---|---|
| **Planear** | Definir alcance, entornos y criterios (este plan). Diseñar los casos con las técnicas de la sección 5 | Casos escritos en el registro con estado «Pendiente» |
| **Hacer** | Preparar el entorno y ejecutar los pasos de cada caso | Resultado obtenido y evidencia guardada |
| **Verificar** | Comparar lo obtenido con lo esperado y aplicar los criterios de la sección 7 | Estado «Pasa» o «Falla» en el registro |
| **Actuar** | Corregir lo que falló, volver a ejecutar el caso y la regresión (sección 10), y mejorar el plan si hizo falta | Hallazgo cerrado; plan o casos ajustados |

---

## 2. Alcance

### 2.1 Qué se prueba

| Parte | Qué incluye | Dónde vive |
|---|---|---|
| **API (backend)** | Las operaciones del contrato, las reglas de negocio, los permisos, el simulador de consumo y las tareas programadas | Repositorio: `api/` |
| **Base de datos** | Tablas, reglas de integridad y seguridad por fila (cada usuario ve solo su hogar), almacenamiento de fotos | Repositorio: `supabase/`; carpeta: `02_base-de-datos/` |
| **App móvil** | Pantallas, navegación, textos, estados de carga, vacío y error, accesibilidad | Repositorio: `app/` |
| **Correos** | Confirmación de registro, recuperación de contraseña, cambio de correo e invitación al hogar | Plantillas: `06_catalogo-de-textos/` |
| **Despliegue** | El servidor publicado y su conexión con la base real | Servidor en Render; base en Supabase |

### 2.2 Qué no se prueba

| Fuera de alcance | Por qué |
|---|---|
| Medidores o sensores físicos | El MVP usa datos simulados |
| Funciones de la Fase 2 (transición energética y similares) | No hacen parte del MVP; ver reglas de negocio |
| Calibración con consumo real de hogares | Los umbrales se calibran con datos simulados |
| Carga masiva o estrés con muchos usuarios a la vez | Fuera del alcance del MVP académico |

### 2.3 Fuentes de verdad

Cada caso de prueba se basa en una de estas fuentes. Si dos fuentes se contradicen, manda la de más arriba.

| Prioridad | Fuente | Ruta |
|---|---|---|
| 1 | Reglas de negocio y modelo de datos | `01_reglas-y-modelo/` |
| 2 | Contrato de la API | `03_api/` (copia en el repositorio: `docs/api/`) |
| 3 | Registro de decisiones | `00_estado-y-pendientes/` (copia: `docs/decisiones/`) |
| 4 | Decisiones del responsable del proyecto | Lista de pendientes (`PENDIENTES.md`), sección «Ya hecho» |
| Apoyo | Historias de usuario y sus criterios de aceptación | `08_documentacion-tecnica/historias/` |
| Apoyo | Catálogo de textos | `06_catalogo-de-textos/` |
| Apoyo | Umbrales y datos simulados | `04_datos-simulados/` |
| Apoyo | Sistema de diseño | `05_sistema-de-diseno/` |

---

## 3. Entornos de prueba

| Entorno | Para qué | Quién lo usa | Qué necesita | Precauciones |
|---|---|---|---|---|
| **Local** (computador) | Pruebas automáticas con bases imitadas en memoria | Equipo y herramientas de IA | El repositorio clonado, `uv` para la API y `npm` para la app | Ninguna: no toca nada real |
| **Integración continua** (GitHub) | Repetir todas las pruebas automáticas en cada PR | Automático | Nada | Un PR no se fusiona si algo sale en rojo |
| **Base real** (Supabase de desarrollo) | Seguridad por fila, integridad y recorridos con datos reales | Una persona del equipo | El archivo de claves `api/.env` (nunca se comparte) | Solo cuentas de prueba temporales, que se borran al terminar. Nunca datos personales reales |
| **Servidor publicado** (Render) | Tiempos reales y recorridos de punta a punta | Una persona del equipo | La dirección pública del servidor | El plan gratuito se duerme: la primera llamada tarda más |
| **Correo** (Brevo y Supabase) | Que los correos lleguen y se vean bien | Una persona del equipo | Un buzón de prueba propio | Cupo diario limitado de correos: no repetir pruebas que envíen muchos |
| **Teléfonos** (Android e iOS) | Pantallas, accesibilidad y uso real | Equipo y personas de prueba | La app abierta con Expo o una build de prueba | Anotar modelo del teléfono y versión del sistema |

**Reglas de seguridad para todos los entornos:**

1. Las claves viven solo en `api/.env` y en las variables del servidor. Nunca se escriben en documentos, chats, evidencias ni capturas.
2. Lo que escribe en la base real o en el servidor lo ejecuta una persona del equipo, no una IA.
3. Las cuentas de prueba usan correos de ejemplo (`@example.com`), salvo las pruebas de correo, que usan un buzón propio.

---

## 4. Niveles y tipos de prueba

### 4.1 Niveles

| Nivel | Qué comprueba | En Zentheris | Dónde vive | Cómo se ejecuta | Cuándo |
|---|---|---|---|---|---|
| **Unitarias** | Cada pieza por separado: un cálculo, una regla, un formato | Estados de consumo, umbrales, proyección, simulador, formatos, textos | API: `api/tests/` (carpetas de dominio, simulador, umbrales). App: carpetas `__tests__/` dentro de `app/src/` | API: `uv run pytest -q` desde `api/`. App: `npm test` desde `app/` | En cada cambio y en cada PR |
| **Integración** | Que las piezas funcionen juntas: servicios con datos, API con contrato | Servicios, acceso a datos, contrato, permisos; con la base real, seguridad por fila e integridad | API: `api/tests/` (servicios, datos, contrato, permisos). Revisión de coherencia: `scripts/check_integration.py`. Base real: `09_pruebas/scripts/` | Automáticas: igual que las unitarias. Base real: los programas de `09_pruebas/scripts/`, que corre una persona | Automáticas: cada PR. Base real: etapa 1 de la ronda |
| **Sistema** | El producto completo de punta a punta | Recorridos con las 5 personalidades de consumo (simulados) y recorridos reales contra el servidor | Simulados: `api/tests/e2e/`. Reales: casos SR del registro | Simulados: automáticos. Reales: Postman o la página de documentación del servidor (`/docs`) | Simulados: cada PR. Reales: etapas 1 y 2 |
| **Aceptación** | Que cumpla lo que pidió el usuario | Criterios de aceptación de las historias de usuario | Casos AC del registro; historias en `08_documentacion-tecnica/historias/` | Manual, con la app, ante el responsable del proyecto o el instructor | Etapa 3 |

### 4.2 Tipos

| Tipo | Qué comprueba | En Zentheris |
|---|---|---|
| **Funcionales** | Que haga lo que dicen las reglas | Zonas por tipo de vivienda, historial, alertas, metas, tarifa, permisos, invitaciones |
| **No funcionales** | Cómo lo hace: rendimiento, seguridad, fiabilidad, accesibilidad, compatibilidad | Tiempo de crear el hogar, seguridad por fila, errores sin datos internos, recuperación de horas, lector de pantalla |
| **Regresión** | Que lo nuevo no rompa lo anterior | Todas las pruebas automáticas corren en cada PR; las manuales se repiten según la sección 10 |
| **Usabilidad** | Que las personas entiendan y usen la app sin ayuda | Casos US: tareas con personas reales y cuestionario de satisfacción |

---

## 5. Diseño de casos de prueba

### 5.1 Técnicas

| Técnica | En qué consiste | Ejemplo en Zentheris |
|---|---|---|
| **Partición de equivalencia** | Agrupar los datos en clases que se comportan igual y probar uno de cada clase | Tipos de vivienda: el apartaestudio tiene reglas de zonas distintas a las de apartamento, casa, dúplex y casa campestre |
| **Valores límite** | Probar justo en el borde, un poco antes y un poco después | La invitación número 20 del día pasa y la 21 no; un pico del 9,9 % no cuenta y uno del 10 % sí; 5 cupos por hogar |
| **Tabla de decisión** | Cruzar condiciones y ver el resultado de cada combinación | Permisos: administrador o miembro × permiso activado o no × operación |
| **Transición de estados** | Recorrer los estados posibles y los cambios permitidos y prohibidos | Invitación: pendiente → aceptada, rechazada, vencida o cancelada; una aceptada no vuelve a pendiente |
| **Escenarios (casos de uso)** | Seguir el recorrido real de una persona | El recorrido de una persona nueva: crear cuenta → crear el hogar → ver el panel → invitar a alguien |
| **Prueba de error** | Forzar fallos para ver que el sistema responde bien | Falla del historial inicial a mitad del proceso: no debe quedar nada creado |

### 5.2 Reglas para escribir un caso

1. **Trazable:** cada caso cita su fuente (regla, decisión, historia o contrato).
2. **Verificable:** el resultado esperado es concreto (un código, un valor, un texto o un tiempo), nunca «funciona bien».
3. **Repetible:** los pasos y los datos alcanzan para que otra persona lo repita igual.
4. **Independiente:** no depende de que otro caso haya corrido antes; si lo necesita, lo dice en las condiciones previas.
5. **Sin datos sensibles:** nada de claves, contraseñas reales ni datos personales en el caso ni en su evidencia.

---

## 6. Identificadores y plantilla de caso

### 6.1 Prefijos

Cada caso tiene un identificador único que **nunca se reutiliza**. Si un caso deja de servir, se marca «Retirada» y se conserva.

| Prefijo | Grupo | Dónde se define |
|---|---|---|
| P | Permisos | Matriz de pruebas del backend |
| R | Seguridad por fila y almacenamiento | Matriz de pruebas del backend |
| Z | Zonas por tipo de vivienda | Matriz de pruebas del backend |
| B | Historial inicial (backfill) y recuperación de horas | Matriz de pruebas del backend |
| U | Umbrales y proyección | Matriz de pruebas del backend |
| A | Alertas y consejos | Matriz de pruebas del backend |
| C | Contrato de la API | Matriz de pruebas del backend |
| I | Integridad de datos | Matriz de pruebas del backend |
| S | Seguridad de la API | Matriz de pruebas del backend |
| SR | Sistema con datos reales (recorridos contra el servidor) | Registro de pruebas |
| CO | Correos | Registro de pruebas |
| RD | Rendimiento | Registro de pruebas |
| FA | Funcionales de la app (por pantalla) | Registro de pruebas |
| DA | Dispositivos y accesibilidad | Registro de pruebas |
| US | Usabilidad con personas | Registro de pruebas |
| AC | Aceptación (historias de usuario) | Registro de pruebas |

Un grupo nuevo se agrega en esta tabla con un prefijo de dos letras que no choque con los existentes.

### 6.2 Plantilla de caso

| Campo | Qué va |
|---|---|
| **ID** | Prefijo y número de dos cifras (`SR-01`) |
| **Nombre** | Qué se prueba, en una frase |
| **Nivel y tipo** | Por ejemplo: sistema, funcional |
| **Calidad** | Característica de la sección 1.1 |
| **Fuente** | Regla, decisión, historia o sección del contrato |
| **Entorno** | Uno de la sección 3 |
| **Condiciones previas** | Lo que debe existir antes de empezar |
| **Datos** | Los datos exactos que se usan |
| **Pasos** | Numerados, uno por acción |
| **Resultado esperado** | Concreto y medible |
| **Automatizada** | Sí (dónde) o No |

El **resultado obtenido**, el **estado**, la **fecha**, **quién lo ejecutó** y la **evidencia** no van en la ficha del caso: se anotan en el registro cada vez que se ejecuta.

**Ejemplo de ficha:**

| Campo | Valor |
|---|---|
| ID | SR-02 |
| Nombre | Invitar a una persona y que acepte |
| Nivel y tipo | Sistema, funcional |
| Calidad | Adecuación funcional, seguridad |
| Fuente | Reglas de negocio, sección X (onboarding, hogar y membresía) |
| Entorno | Servidor publicado y base real |
| Condiciones previas | Cuenta A con hogar (administrador); cuenta B con ficha y sin hogar |
| Datos | Correo de la cuenta B |
| Pasos | 1. A invita a B. 2. B consulta sus invitaciones. 3. B acepta. 4. A consulta los miembros |
| Resultado esperado | B aparece como miembro activo con los permisos por defecto; A recibe el aviso «Nuevo miembro» |
| Automatizada | Parcial: simulada en `api/tests/e2e/`; real, no |

---

## 7. Criterios

### 7.1 Criterios de entrada (cuándo se puede empezar)

| Etapa | Se puede empezar cuando |
|---|---|
| Pruebas automáticas | El cambio está en una rama con PR abierto |
| Etapa 1 (base real) | Todas las pruebas automáticas pasan en `main`, el servidor tiene la última versión y existe `api/.env` |
| Etapa 2 (app) | La pantalla está fusionada en `main` y conectada a la API |
| Etapa 3 (entrega) | Las etapas 1 y 2 no tienen hallazgos críticos ni altos abiertos |

### 7.2 Criterios de salida (cuándo se da por terminado)

| Etapa | Se da por terminada cuando |
|---|---|
| Pruebas automáticas | Todo en verde en la integración continua |
| Etapa 1 | Todos sus casos en «Pasa» o con un hallazgo de severidad media o baja anotado |
| Etapa 2 | Igual que la etapa 1, en Android e iOS |
| Etapa 3 | Cada historia de usuario aceptada y el informe de cierre escrito |

### 7.3 Suspender y reanudar

Se suspende una ronda si aparece un hallazgo **crítico**, si el entorno no está disponible (servidor o base en pausa) o si el cupo de correos se agotó. Se reanuda cuando se corrige la causa, empezando por repetir el caso que falló.

### 7.4 Severidad de los hallazgos

| Severidad | Qué significa | Ejemplo |
|---|---|---|
| **Crítica** | Expone datos de otra persona, pierde datos o impide usar la app | Un usuario ve el consumo de un hogar ajeno |
| **Alta** | Una función principal no sirve y no hay otra forma de hacerla | No se puede aceptar una invitación |
| **Media** | Funciona mal pero hay otra forma, o el error es claro y recuperable | Un total sale con un redondeo distinto al de la regla |
| **Baja** | Detalle visual o de texto que no cambia el resultado | Una tilde que falta en un mensaje |

---

## 8. Ejecución y evidencias

### 8.1 Pasos para ejecutar un caso

1. Lee la ficha del caso en el registro (o en la matriz, si es de los grupos P a S).
2. Revisa los criterios de entrada de su etapa (sección 7.1) y prepara el entorno.
3. Sigue los pasos tal cual, con los datos indicados.
4. Compara lo obtenido con lo esperado.
5. Guarda la evidencia (sección 8.2).
6. Anota la ejecución en el registro: estado, fecha, quién, entorno y ruta de la evidencia.
7. Si falla: anota un hallazgo en el registro con su severidad y llévalo a la lista de pendientes.
8. Cuando se corrija: repite el caso y la regresión que corresponda (sección 10).

### 8.2 Evidencias

| Regla | Detalle |
|---|---|
| Dónde | `09_pruebas/evidencias/<ID>/` (una carpeta por caso) |
| Nombre | `<AAAA-MM-DD>_<descripcion-corta>.<ext>`, por ejemplo `2026-01-15_resultado.txt` |
| Qué sirve | Salida de consola, captura de pantalla, video corto, enlace al PR o a la ejecución del CI |
| Qué no va | Claves, tokens, contraseñas, correos personales sin tapar |
| Pruebas automáticas | No necesitan carpeta: su evidencia es la ejecución del CI en cada PR |

### 8.3 Estados de un caso

| Estado | Significa |
|---|---|
| ⏳ **Pendiente** | Diseñado, aún no se ejecuta |
| 🚧 **Bloqueada** | No se puede ejecutar todavía (falta la pantalla, el entorno o una decisión); se dice qué falta |
| 🤖 **Automatizada** | Corre sola en cada PR; su estado es el del CI |
| ✅ **Pasa** | La última ejecución dio lo esperado |
| ❌ **Falla** | La última ejecución no dio lo esperado; tiene un hallazgo abierto |
| ➖ **Retirada** | Ya no aplica; se conserva para no reutilizar su ID |

### 8.4 Programas de apoyo

Las pruebas contra la base real o el servidor que conviene repetir se convierten en programas guardados en `09_pruebas/scripts/`. Cada programa:

- se corre desde la carpeta `api/` del repositorio, que es donde está `api/.env`: `uv run python <ruta-del-programa>`;
- nunca imprime claves, contraseñas ni tokens;
- crea solo datos de prueba temporales y los borra al terminar;
- guarda su resultado en la carpeta de evidencias del caso.

---

## 9. La ronda de pruebas en 3 etapas

| Etapa | Qué cubre | Grupos | Entornos |
|---|---|---|---|
| **1. Backend con datos reales** | Lo que las pruebas automáticas no alcanzan porque usan bases imitadas: seguridad por fila, integridad, recorridos completos, correos y tiempos | R, I (con base real), SR, CO, RD, B-03 | Base real, servidor publicado, correo |
| **2. App** | Cada pantalla, en teléfonos reales, con accesibilidad y con personas | FA, DA, US, RD | Teléfonos, servidor publicado |
| **3. Entrega** | Aceptación de las historias de usuario e informe de cierre | AC | Teléfonos, con el responsable del proyecto o el instructor |

Las pruebas automáticas (grupos P a S) acompañan las tres etapas: corren en cada PR.

---

## 10. Regresión: qué repetir cuando algo cambia

| Si cambia… | Se repite |
|---|---|
| Cualquier código | Todas las pruebas automáticas (lo hace el CI en cada PR) |
| El contrato de la API | Grupo C y los casos SR que usen esas operaciones |
| Las reglas de permisos | Grupo P, casos SR de miembros y FA de las pantallas afectadas |
| La base de datos (migraciones o políticas) | Grupos R e I con base real |
| Las plantillas o el servicio de correo | Grupo CO |
| El simulador o los umbrales | Grupos B, U y A, y RD (tiempo de crear el hogar) |
| Una pantalla | Su caso FA y los DA de esa pantalla |
| El servidor o su plan | RD y un recorrido SR completo |
| Antes de la entrega | La ronda completa |

---

## 11. Roles y riesgos

### 11.1 Roles

| Rol | Qué hace |
|---|---|
| **Responsable de pruebas** | Mantiene este plan y el registro, decide prioridades y aprueba el cierre de cada etapa |
| **Ejecutor** | Corre los casos, guarda evidencias y anota resultados |
| **Revisor** | Confirma que una corrección resolvió el hallazgo antes de cerrarlo |
| **Herramienta de IA** | Diseña casos, escribe pruebas automáticas y programas de apoyo, revisa resultados y actualiza el registro; no ejecuta nada contra la base real ni ve claves (sección 13) |

Quién cumple cada rol y para cuándo se define en Notion.

### 11.2 Riesgos

| Riesgo | Efecto | Qué hacer |
|---|---|---|
| El servidor gratuito se duerme | La primera llamada tarda más y puede confundirse con un fallo | Despertarlo antes (ruta de salud) y medir aparte la primera llamada (RD) |
| La base gratuita se pausa por inactividad | Ninguna prueba real funciona | Reactivarla desde el panel de Supabase antes de empezar |
| Cupo diario de correos | Se agotan los correos y fallan registro e invitaciones | No repetir en real pruebas que envían muchos correos; esas quedan automatizadas |
| Correos en spam | Parece que no llegan | Revisar la carpeta de spam y anotarlo en el caso CO |
| Datos de prueba que quedan en la base real | Ensucian la base y los conteos | Programas que borran lo que crean; revisar al final |
| Exponer claves en una evidencia | Riesgo de seguridad | Revisar cada evidencia antes de guardarla |

---

## 12. Mantenimiento de este documento

### 12.1 Qué va en cada lugar

| Información | Dónde va | ¿Cambia seguido? |
|---|---|---|
| Cómo se prueba (método, criterios, técnicas, roles) | Este plan | Casi nunca |
| Qué casos existen, su estado, resultados, hallazgos e historial | Registro de pruebas (`09_pruebas/`) | Con cada ejecución |
| Casos de las pruebas automáticas del backend | Matriz de pruebas del backend (`09_pruebas/`; copia en `docs/pruebas/`) | Solo si se agrega un caso |
| Código de las pruebas automáticas | Repositorio: `api/tests/` y `app/src/` | Con cada cambio de código |
| Programas de apoyo y evidencias | `09_pruebas/scripts/` y `09_pruebas/evidencias/` | Cuando se ejecutan casos reales |
| Tareas, responsables y fechas | Notion | Según el equipo |
| Defectos por corregir | Lista de pendientes (`PENDIENTES.md`) | Cuando aparecen o se cierran |

### 12.2 Reglas para que no se desactualice

1. Aquí no se escriben fechas, conteos de pruebas, porcentajes ni nombres de versión de documentos. Se citan **rutas de carpetas** y **nombres de secciones**.
2. Este plan se edita solo si cambia el **método**: un entorno nuevo, un grupo de casos nuevo, una técnica o un criterio.
3. Los casos nuevos se agregan en el registro con su ficha; si son un grupo nuevo, se agrega su prefijo en la sección 6.1.
4. Un caso nunca se borra: se marca «Retirada».

---

## 13. Reglas para herramientas de IA

Si eres una herramienta de IA trabajando sobre las pruebas de Zentheris:

1. **Lee primero** este plan y después el registro de pruebas. Para el detalle de un caso del backend, la matriz (`09_pruebas/`).
2. **No inventes.** Cada caso sale de una fuente de la sección 2.3. Si falta información, escribe «HUECO:»; si dos fuentes chocan, escribe «CONTRADICCIÓN:» y aplica el orden de prioridad de esa sección.
3. **Nunca** leas, pidas ni muestres claves, contraseñas o tokens, ni el archivo `api/.env`.
4. **No ejecutes** nada que escriba en la base real o en el servidor. Prepara el programa en `09_pruebas/scripts/` y entrégale a una persona el comando para correrlo.
5. **Después de cada ejecución,** actualiza el registro: estado, fecha, quién, entorno, evidencia y, si falló, el hallazgo.
6. **Respeta el formato:** las fichas siguen la plantilla de la sección 6.2 y los estados son los de la sección 8.3.
7. **No cambies este plan** para anotar resultados; si el método necesita cambiar, propónlo primero al responsable de pruebas.
