# Registro de pruebas de Zentheris

Lista viva de todos los casos de prueba: qué se prueba, cómo, en qué estado está y qué resultado dio. **Este es el único archivo que cambia cuando se ejecutan pruebas.**

El método (técnicas, criterios, severidades, estados y cómo guardar evidencias) está en el **plan de pruebas** (`09_pruebas/PLAN-DE-PRUEBAS.md`). Léelo primero si es tu primera vez.

> **Rutas.** Las rutas de este documento son las de la carpeta de documentación del proyecto. En el repositorio, `09_pruebas/` está en `docs/pruebas/`. Si una ruta no existe en el repositorio, ese archivo está solo en la carpeta de documentación.

---

## Cómo leer y actualizar este registro

**Estados:** ⏳ Pendiente · 🚧 Bloqueada · 🤖 Automatizada · ✅ Pasa · ❌ Falla · ➖ Retirada (definidos en el plan, sección 8.3).

**Para anotar una ejecución:**

1. Cambia el **estado** del caso en su tabla y la columna **Última ejecución**.
2. Agrega una fila en [Historial de ejecuciones](#6-historial-de-ejecuciones) (nunca borres filas anteriores).
3. Si falló, agrega el hallazgo en [Hallazgos](#5-hallazgos) y llévalo a la lista de pendientes (`PENDIENTES.md`).
4. Guarda la evidencia en `09_pruebas/evidencias/<ID>/`.

| Sección | Qué contiene |
|---|---|
| [1. Pruebas automáticas del backend](#1-pruebas-automáticas-del-backend) | Los casos de la matriz del backend y su estado |
| [2. Etapa 1: backend con datos reales](#2-etapa-1-backend-con-datos-reales) | Recorridos, correos, tiempos, seguridad e integridad con la base real |
| [3. Etapa 2: app](#3-etapa-2-app) | Pantallas, teléfonos, accesibilidad y usabilidad |
| [4. Etapa 3: entrega](#4-etapa-3-entrega) | Aceptación de historias e informe de cierre |
| [5. Hallazgos](#5-hallazgos) | Defectos encontrados y su estado |
| [6. Historial de ejecuciones](#6-historial-de-ejecuciones) | Cada vez que se ejecutó un caso manual |

---

## 1. Pruebas automáticas del backend

Casos definidos en la matriz de pruebas del backend (`09_pruebas/`; copia en `docs/pruebas/`), donde está el detalle de cada uno. Su código vive en `api/tests/` y corre en cada PR.

**Cómo correrlas (desde `api/`):** `uv run pytest -q`. La revisión de estilo es `uv run ruff check .` y la coherencia entre contrato, rutas, app y mapa, `uv run python ../scripts/check_integration.py`.

| ID | Caso | Tipo | Calidad | Estado | Última ejecución | Nota |
|---|---|---|---|---|---|---|
| P-01 | Usuario ajeno consulta un hogar | Integración, funcional | Seguridad | 🤖 | Cada PR | |
| P-02 | Sin permiso pide el consumo actual | Integración, funcional | Seguridad | 🤖 | Cada PR | |
| P-03 | Sin permiso pide el historial | Integración, funcional | Seguridad | 🤖 | Cada PR | |
| P-04 | Sin permiso crea una meta | Integración, funcional | Seguridad | 🤖 | Cada PR | |
| P-05 | Miembro hace algo de administrador | Integración, funcional | Seguridad | 🤖 | Cada PR | |
| P-06 | Administrador sin permisos activados ve todo | Integración, funcional | Seguridad | 🤖 | Cada PR | |
| P-07 | Fuentes de datos sin permiso | Integración, funcional | Seguridad | 🤖 | Cada PR | |
| P-08 | Sin permiso de alertas marca alertas | Integración, funcional | Seguridad | 🤖 | Cada PR | Sin archivo propio: cubierto en las pruebas de permisos y de punta a punta de alertas |
| R-01 | Leer lecturas de otro hogar directo en la base | Integración, no funcional | Seguridad | ⏳ | — | Necesita la base real: etapa 1 |
| R-02 | Escribir directo en cualquier tabla | Integración, no funcional | Seguridad | ⏳ | — | Necesita la base real: etapa 1 |
| R-03 | Leer los perfiles de simulación | Integración, no funcional | Seguridad | ⏳ | — | Necesita la base real: etapa 1 |
| R-04 | Ver la foto de perfil de otro hogar | Integración, no funcional | Seguridad | ⏳ | — | Necesita la base real: etapa 1 |
| Z-01 | Apartaestudio con terraza | Unitaria, funcional | Adecuación funcional | 🤖 | Cada PR | |
| Z-02 | Apartamento sin baño | Unitaria, funcional | Adecuación funcional | 🤖 | Cada PR | |
| Z-03 | Apartaestudio con demasiadas o muy pocas zonas | Unitaria, funcional | Adecuación funcional | 🤖 | Cada PR | |
| Z-04 | Combinaciones de vivienda y zonas → personalidad | Unitaria, funcional | Adecuación funcional | 🤖 | Cada PR | |
| B-01 | Historial inicial de un dúplex con 9 zonas | Integración, funcional | Adecuación funcional | 🤖 | Cada PR | |
| B-02 | Falla a mitad del historial inicial | Integración, funcional | Fiabilidad | 🤖 | Cada PR | |
| B-03 | Tiempo de crear el hogar en el servidor real | Sistema, no funcional | Eficiencia de desempeño | ✅ | Ver historial | Manual, con programa de apoyo (sección 2.3) |
| B-04 | Recuperar horas después de una pausa | Integración, funcional | Fiabilidad | 🤖 | Cada PR | |
| U-01 | Escenarios de umbrales contra la referencia | Unitaria, funcional | Adecuación funcional | 🤖 | Cada PR | |
| U-02 | Límite del pico (9,9 % y 10 %) | Unitaria, funcional | Adecuación funcional | 🤖 | Cada PR | |
| U-03 | Fórmula de la proyección | Unitaria, funcional | Adecuación funcional | 🤖 | Cada PR | |
| A-01 | Crítico dos veces el mismo día → 1 alerta | Integración, funcional | Adecuación funcional | 🤖 | Cada PR | |
| A-02 | El historial inicial no genera alertas | Integración, funcional | Adecuación funcional | 🤖 | Cada PR | |
| A-03 | Interruptor de alertas apagado | Integración, funcional | Adecuación funcional | 🤖 | Cada PR | |
| A-04 | Cierre de mes por encima de la referencia | Integración, funcional | Adecuación funcional | 🤖 | Cada PR | |
| A-05 | Consejo para cada miembro activo | Integración, funcional | Adecuación funcional | 🤖 | Cada PR | |
| C-01 | Cada respuesta coincide con el contrato | Integración, funcional | Compatibilidad | 🤖 | Cada PR | |
| C-02 | Revisión oficial del contrato (Redocly) | Integración, no funcional | Compatibilidad | 🤖 | Cada PR | Corre como paso aparte del CI |
| I-01 | Sensor y zona de hogares distintos | Integración, funcional | Seguridad | ⏳ | — | La regla está en la base: se comprueba con la base real (etapa 1) |
| I-02 | Tarifas que se pisan | Integración, funcional | Adecuación funcional | 🤖 | Cada PR | El rechazo de la API está automatizado; el de la propia base se confirma con la base real (etapa 1) |
| I-03 | Eliminar la cuenta del único miembro | Integración, funcional | Seguridad | ⏳ | — | Lógica automatizada con bases imitadas; falta confirmar con la base real (SR-04) |
| I-04 | Eliminar la cuenta de un miembro que no es único | Integración, funcional | Seguridad | ⏳ | — | Lógica automatizada con bases imitadas; falta confirmar con la base real (SR-04) |
| S-01 | Un error interno no expone la excepción | Integración, no funcional | Seguridad | 🤖 | Cada PR | |
| S-02 | Del enlace de invitación solo se guarda su huella | Unitaria, no funcional | Seguridad | 🤖 | Cada PR | |
| S-03 | Llamada sin sesión, con sesión inválida o vencida | Integración, no funcional | Seguridad | 🤖 | Cada PR | |
| S-04 | Fallo no previsto → 500 sin detalles | Integración, no funcional | Seguridad | 🤖 | Cada PR | |

---

## 2. Etapa 1: backend con datos reales

**Criterio de entrada:** todas las pruebas automáticas en verde en `main`, el servidor con la última versión y `api/.env` creado (plan, sección 7.1).

**Herramientas:** Postman (colección prevista en `09_pruebas/postman/`, por crear a partir del contrato) o la página de documentación del servidor (`/docs`). Los casos que escriben en la base usan programas de `09_pruebas/scripts/` que corre una persona.

### 2.1 Resumen

| ID | Caso | Tipo | Calidad | Estado | Última ejecución |
|---|---|---|---|---|---|
| SR-01 | Recorrido completo del administrador | Sistema, funcional | Adecuación funcional | ⏳ | — |
| SR-02 | Invitar a una persona y que acepte o rechace | Sistema, funcional | Adecuación funcional, seguridad | ⏳ | — |
| SR-03 | Gestionar miembros: permisos, expulsar, pasar la administración y salir | Sistema, funcional | Seguridad | ⏳ | — |
| SR-04 | Eliminar cuentas sin dejar datos sueltos (confirma I-03 e I-04) | Sistema, funcional | Seguridad, fiabilidad | ⏳ | — |
| SR-05 | Alertas, consejos y recuperación de horas con el paso del tiempo | Sistema, funcional | Adecuación funcional, fiabilidad | ⏳ | — |
| CO-01 | Correo de confirmación de registro | Sistema, funcional | Compatibilidad, usabilidad | ⏳ | — |
| CO-02 | Correo de recuperación de contraseña | Sistema, funcional | Compatibilidad, usabilidad | ⏳ | — |
| CO-03 | Correo de cambio de correo | Sistema, funcional | Compatibilidad, usabilidad | ⏳ | — |
| CO-04 | Correo de invitación al hogar | Sistema, funcional | Compatibilidad, usabilidad | ⏳ | — |
| RD-01 | Primera llamada con el servidor dormido | Sistema, no funcional | Eficiencia de desempeño | ⏳ | — |
| B-03 | Tiempo de crear el hogar (10 repeticiones) | Sistema, no funcional | Eficiencia de desempeño | ✅ | Ver historial |
| R-01 a R-04 | Seguridad por fila y fotos (detalle en la matriz) | Integración, no funcional | Seguridad | ⏳ | — |
| I-01 | Sensor y zona del mismo hogar (detalle en la matriz) | Integración, funcional | Seguridad | ⏳ | — |
| I-02 (base) | La base rechaza tarifas que se pisan (detalle en la matriz) | Integración, funcional | Adecuación funcional | ⏳ | — |

Apoyo para R e I: el entorno de prueba de la base ya tiene pruebas en SQL de seguridad por fila e integridad (`02_base-de-datos/entornos/zentheris-dev/supabase/tests/`). Sirven de guía para armar los pasos; no se corren en la base real sin autorización.

### 2.2 Fichas

#### SR-01 · Recorrido completo del administrador

| Campo | Valor |
|---|---|
| Fuente | Reglas de negocio, secciones IX (registro), X (onboarding), XII (panel y zonas), XIII (historial), V y XVI (metas, tarifa y configuración); contrato |
| Entorno | Servidor publicado y base real |
| Condiciones previas | Una cuenta de prueba nueva (correo de ejemplo) con sesión iniciada |
| Datos | Casa con las 4 zonas básicas; una tarifa del mes actual; una meta mensual |
| Pasos | 1. Crear la ficha del usuario. 2. Crear el hogar. 3. Consultar el panel. 4. Consultar zonas y una zona individual. 5. Consultar el historial de día, semana y mes. 6. Guardar la tarifa y volver a consultar el historial. 7. Guardar la meta y consultarla. 8. Consultar Fuentes de datos. 9. Cambiar una preferencia. 10. Eliminar la cuenta |
| Resultado esperado | Cada paso responde con el código del contrato. El total del panel es la suma de las zonas. Después de guardar la tarifa, el historial muestra costo. La meta muestra su límite por día. Al final no queda nada de la cuenta |
| Automatizada | Simulada en `api/tests/e2e/`; real, no |

#### SR-02 · Invitar a una persona y que acepte o rechace

| Campo | Valor |
|---|---|
| Fuente | Reglas de negocio, sección X (onboarding, hogar y membresía) |
| Entorno | Servidor publicado, base real y correo |
| Condiciones previas | Cuenta A con hogar (administradora); cuentas B y C con ficha y sin hogar |
| Datos | Correos de B y C (buzones propios, porque llega un correo real) |
| Pasos | 1. A invita a B y a C. 2. B ve su invitación y la acepta. 3. C ve su invitación y la rechaza. 4. A consulta los miembros y sus alertas |
| Resultado esperado | B queda como miembro activo con los permisos por defecto; C no. A recibe el aviso «Nuevo miembro» y B no. La invitación de C queda rechazada y no se puede volver a usar |
| Automatizada | Simulada en `api/tests/e2e/`; real, no |

#### SR-03 · Gestionar miembros

| Campo | Valor |
|---|---|
| Fuente | Reglas de negocio, secciones X y XVII (permisos y visibilidad) |
| Entorno | Servidor publicado y base real |
| Condiciones previas | El hogar de SR-02 con A (administradora) y B (miembro) |
| Pasos | 1. A le quita a B el permiso de ver el historial. 2. B pide el historial. 3. A le pasa la administración a B. 4. A sale del hogar. 5. B expulsa a otro miembro, si lo hay |
| Resultado esperado | En el paso 2, B recibe 403 `SIN_PERMISO_VER_HISTORIAL`. Después del paso 3, B es la administradora y A, miembro. A sale sin errores. Cada cambio se refleja al consultar los miembros |
| Automatizada | Simulada en `api/tests/e2e/`; real, no |

#### SR-04 · Eliminar cuentas sin dejar datos sueltos

| Campo | Valor |
|---|---|
| Fuente | Reglas de negocio, sección IX (eliminar cuenta); matriz, I-03 e I-04 |
| Entorno | Base real |
| Condiciones previas | Un hogar con un solo miembro y otro con dos miembros |
| Pasos | 1. En el hogar de dos, el miembro que no es administrador elimina su cuenta. 2. En el hogar de uno, el único miembro elimina su cuenta. 3. Revisar la base |
| Resultado esperado | Paso 1: su membresía queda inactiva y sin usuario, y los datos del hogar siguen. Paso 2: el hogar, sus zonas, sensores y lecturas desaparecen. No queda ningún dato suelto |
| Automatizada | Lógica simulada en `api/tests/`; con base real, programa por crear en `09_pruebas/scripts/` |

#### SR-05 · Alertas, consejos y recuperación de horas con el paso del tiempo

| Campo | Valor |
|---|---|
| Fuente | Reglas de negocio, secciones IV (recuperación de horas), XIV (alertas) y XV (consejos) |
| Entorno | Servidor publicado y base real |
| Condiciones previas | Un hogar de prueba creado y sin borrar durante al menos 24 horas |
| Pasos | 1. Anotar la hora de creación. 2. Al día siguiente, consultar el panel y el historial. 3. Consultar alertas, alertas sin leer y consejos. 4. Marcar alertas como leídas y un consejo como hecho |
| Resultado esperado | El historial llega hasta la última hora completa, sin huecos. Si hubo alertas, máximo una por regla, zona y día. Las alertas no leídas bajan al marcarlas. Al terminar, el hogar de prueba se elimina |
| Automatizada | Simulada en `api/tests/`; real, no. Que aparezcan alertas depende de los datos simulados de ese día |

#### CO-01 a CO-04 · Correos

| Campo | Valor |
|---|---|
| Fuente | Catálogo de textos (`06_catalogo-de-textos/`, plantillas de Supabase y textos del backend); reglas de negocio, secciones IX y X |
| Entorno | Correo real, con un buzón propio |
| Casos | **CO-01** confirmación de registro · **CO-02** recuperación de contraseña · **CO-03** cambio de correo · **CO-04** invitación al hogar |
| Pasos | 1. Provocar el correo (registrarse, pedir recuperación, cambiar el correo o recibir una invitación). 2. Buscarlo en la bandeja de entrada y en spam. 3. Revisar asunto y texto. 4. Abrir el enlace |
| Resultado esperado | Llega en pocos minutos. El asunto y el texto coinciden con el catálogo y las variables `{{ }}` aparecen reemplazadas. El enlace funciona una vez. Se anota si llegó a spam |
| Automatizada | No. El texto de la invitación está probado en `api/tests/`; el envío real, no |

#### RD-01 · Primera llamada con el servidor dormido

| Campo | Valor |
|---|---|
| Fuente | Guía de la app, sección de errores (tiempo de espera: 15 s; 60 s al crear el hogar), en `11_guias-de-desarrollo/`; guía del backend, sección Despliegue |
| Entorno | Servidor publicado |
| Condiciones previas | El servidor sin uso durante al menos 20 minutos, para que se duerma |
| Pasos | 1. Llamar a la ruta de salud y medir el tiempo. 2. Repetir enseguida y medir |
| Resultado esperado | La primera respuesta llega antes de 15 s, el tiempo de espera de la app; si no, se anota como hallazgo, porque la app mostraría «tiempo agotado». La segunda llamada es rápida |
| Automatizada | No |

#### B-03 · Tiempo de crear el hogar

| Campo | Valor |
|---|---|
| Fuente | Matriz, B-03; registro de decisiones, DC-33; reglas de negocio, sección X |
| Entorno | Servidor publicado y base real |
| Programa | `09_pruebas/scripts/medir_b03.py`. Desde `api/`: `uv run python <ruta-del-programa>` |
| Qué hace | Crea 10 cuentas de prueba temporales, mide la creación de una casa con las 9 zonas (el caso más pesado) y borra todo |
| Resultado esperado | p95 de 10 s o menos |
| Evidencia | `09_pruebas/evidencias/B-03/` |

---

## 3. Etapa 2: app

**Criterio de entrada:** la pantalla está fusionada en `main` y conectada a la API.

### 3.1 Funcionales por pantalla (FA)

Cada pantalla se revisa con esta **lista común**, además de lo que diga su sección en las reglas de negocio (sección 6, «Pantallas de la app»):

1. Se ve como el diseño (`05_sistema-de-diseno/` y `07_pantallas-y-mockups/`).
2. Los textos son los del catálogo (`06_catalogo-de-textos/`).
3. Muestra bien los estados de carga, vacío, sin datos y error.
4. Respeta los permisos: lo que no se puede ver, no aparece.
5. Los números coinciden con lo que responde la API y tienen el formato colombiano.
6. La navegación de ida y vuelta funciona.

| ID | Pantalla | Estado | Última ejecución | Nota |
|---|---|---|---|---|
| FA-01 | Inicio neutral | 🚧 | — | Falta conectar a la API |
| FA-02 | Registro | 🚧 | — | En una rama del equipo |
| FA-03 | Inicio de sesión y recuperar contraseña | 🚧 | — | En una rama del equipo |
| FA-04 | Onboarding (crear el hogar) | 🚧 | — | |
| FA-05 | Invitación recibida | 🚧 | — | |
| FA-06 | Panel principal | 🚧 | — | |
| FA-07 | Historial | 🚧 | — | |
| FA-08 | Zonas | 🚧 | — | |
| FA-09 | Zona individual | 🚧 | — | |
| FA-10 | Alertas | 🚧 | — | |
| FA-11 | Consejos | 🚧 | — | |
| FA-12 | Configuración y cerrar sesión | 🚧 | — | En una rama del equipo |
| FA-13 | Editar perfil y foto | 🚧 | — | |
| FA-14 | Cambiar contraseña | 🚧 | — | |
| FA-15 | Gestionar correo | 🚧 | — | |
| FA-16 | Establecer meta | 🚧 | — | |
| FA-17 | Configurar tarifa | 🚧 | — | |
| FA-18 | Fuentes de datos | 🚧 | — | |
| FA-19 | Miembros del hogar e invitar | 🚧 | — | |
| FA-20 | Eliminar cuenta | 🚧 | — | |

### 3.2 Dispositivos y accesibilidad (DA)

| ID | Caso | Cómo | Resultado esperado | Estado |
|---|---|---|---|---|
| DA-01 | Android | Recorrer todas las pantallas en un teléfono Android | Todo funciona y se ve bien; se anotan modelo y versión | 🚧 |
| DA-02 | iOS | Igual, en un iPhone | Igual que DA-01 | 🚧 |
| DA-03 | Lector de pantalla | TalkBack (Android) y VoiceOver (iOS) | Cada botón, gráfico y estado se anuncia con un nombre claro | 🚧 |
| DA-04 | Texto grande | Tamaño de letra máximo del sistema | Nada se corta ni se monta | 🚧 |
| DA-05 | Daltonismo | Simulador de daltonismo sobre gráficos y estados | Los estados y el pico se distinguen sin depender solo del color | 🚧 |
| DA-06 | Pantallas pequeñas y grandes | Un teléfono pequeño y uno grande | La distribución se adapta sin desplazamiento horizontal | 🚧 |

### 3.3 Usabilidad con personas (US)

| ID | Caso | Cómo | Resultado esperado | Estado |
|---|---|---|---|---|
| US-01 | Prueba con 5 personas que no conocen la app | Cada una hace 4 tareas sin ayuda: crear cuenta y hogar; encontrar la zona que más consume; configurar la tarifa; invitar a alguien. Se anota si la logra, cuánto tarda y dónde se traba. Al final responde el cuestionario SUS (10 preguntas) | La mayoría logra cada tarea sin ayuda. Puntaje SUS promedio de 68 o más (el promedio de referencia del cuestionario; propuesta, a confirmar por el responsable) | 🚧 |

### 3.4 Rendimiento en el teléfono (RD)

| ID | Caso | Cómo | Resultado esperado | Estado |
|---|---|---|---|---|
| RD-02 | Tiempo de abrir las pantallas principales | Medir con cronómetro el panel, el historial y las zonas, con el servidor despierto | HUECO: las reglas no fijan un tiempo. Se anota lo medido y nunca debe aparecer «tiempo agotado» | 🚧 |

---

## 4. Etapa 3: entrega

**Criterio de entrada:** las etapas 1 y 2 sin hallazgos críticos ni altos abiertos.

### 4.1 Aceptación (AC)

Cada grupo se acepta cuando **todas sus historias** cumplen sus criterios de aceptación (`08_documentacion-tecnica/historias/`), probadas en la app ante el responsable del proyecto o el instructor. En el historial de ejecuciones se anota el resultado de cada historia.

| ID | Grupo de historias | Estado | Última ejecución |
|---|---|---|---|
| AC-01 | Acceso y cuenta | 🚧 | — |
| AC-02 | Hogar y onboarding | 🚧 | — |
| AC-03 | Panel, Zonas e Historial | 🚧 | — |
| AC-04 | Alertas y consejos | 🚧 | — |
| AC-05 | Configuración, metas y tarifa | 🚧 | — |
| AC-06 | Miembros | 🚧 | — |

### 4.2 Informe de cierre

Se llena una vez, al terminar la etapa 3.

| Campo | Valor |
|---|---|
| Fecha de cierre | |
| Versión probada (commit de `main` y del servidor) | |
| Casos ejecutados por etapa (pasan / fallan / bloqueados) | |
| Hallazgos abiertos y su severidad | |
| Riesgos que quedan | |
| Decisión | Apto para la entrega / No apto |
| Aprobado por | |

---

## 5. Hallazgos

Defectos encontrados al ejecutar. Cada uno se lleva también a la lista de pendientes (`PENDIENTES.md`). Severidades en el plan, sección 7.4.

| Hallazgo | Caso | Severidad | Qué pasó | Pendiente | Estado |
|---|---|---|---|---|---|
| — | — | — | Sin hallazgos registrados | — | — |

---

## 6. Historial de ejecuciones

Una fila por cada ejecución manual o con programa de apoyo, la más reciente arriba. Las pruebas automáticas no se anotan aquí: su historial es el del CI.

| Fecha | Caso | Entorno | Quién | Resultado | Evidencia |
|---|---|---|---|---|---|
| 26/11/2026 | B-03 | Servidor publicado y base real | Nicolás (programa de apoyo) | ✅ Pasa. 10 de 10 válidas; casa con 9 zonas; mínimo 2,17 s, mediana 2,56 s, p95 2,76 s (límite 10 s) | `09_pruebas/evidencias/B-03/` |
| 22/11/2026 | B-03 (una sola medición) | Servidor publicado y base real | Nicolás | ✅ 1,9 s con 4 zonas; no cuenta como B-03 completo (pide 10 repeticiones) | Anotado en la lista de pendientes, sección «Ya hecho» |
