# **Zentheris - Reglas de Negocio y Modelo de Datos (v4.9)**

**Versión 4.9 · 03/11/2026.** Fuentes: v4.8 y el registro de decisiones de cierre de pendientes del 03/11/2026 (`00_estado-y-pendientes/registro-decisiones-cierre-2026-11-03.md`, DC-01 a DC-58, tomadas con la autonomía que delegó Nicolás) y la calibración de umbrales v1 (`04_datos-simulados/calibracion-umbrales-v1/`). Fuentes de la v4.8: v4.6, pedido de Nicolás del 02/11/2026 de pintar el pico en rojo y de evitar que se confunda con «Crítico»; v4.5, revisión de Nicolás del 02/11/2026 sobre las pantallas v4.5 en Figma, v4.4, decisiones de Nicolás del 02/11/2026 sobre la propuesta v4.5 y la revisión de la v4.4, contrato API `zentheris-api` 0.2.5 (sustituye a la 0.2.4 de la v4.8), acta 04 de `perfiles_simulacion` y paquete Avance 03 (conjuntos calibrados v1.0).

**Documento maestro del MVP.** Agrupa las reglas de negocio formales, el diccionario de datos actualizado (18 tablas), el modelo matemático del simulador, la descripción de todas las pantallas validadas y la lista de trabajo pendiente de diseño. Reemplaza a la v4.8 y anteriores, y complementa al diccionario de datos v3.1 (que queda como comparativa). Los endpoints se definen en el contrato API `zentheris-api` 0.2.5 (archivo OpenAPI aparte, `03_api/`; validación estructural propia sin errores, lint oficial con Redocly pendiente de correr por el equipo), derivado de este documento.

**Estado:** la estructura de datos está cerrada (D-SQL-1 a D-SQL-5 resueltas en la v4.9, sección 3) y los umbrales de estado quedaron calibrados (v1, sección 8). Con este documento se puede crear la base de datos en Supabase y construir la interfaz y el backend sin cambios adicionales de modelo. La base de datos **aún no está creada**: se crea cuando Nicolás autorice el paso a desarrollo. Lo que sigue abierto depende de terceros (sección 10). La v4.4 mantiene las 18 tablas y los catálogos de la v4.3: sus cambios son de reglas, definiciones de diseño pendiente y cierre de los parámetros de simulación.

**Cambios de la v4.9 (03/11/2026):** cierre de los pendientes previos al backend (registro DC-01 a DC-58, sección 9.5): (1) umbrales normal/elevado/crítico calibrados con el simulador (RN-XI-07, archivo `umbrales-estado.v1.json`); (2) definición de referencias, comparación entre periodos, pico y proyección al cierre (RN-XI-03, RN-XI-04, RN-XIII-01, RN-XIII-03, RN-XIII-05); (3) generación horaria por recuperación antes de cada consulta y evaluación de alertas solo sobre horas en vivo (RN-IV-05, RN-XIV-07); (4) backfill síncrono confirmado con medición local e inserción por lotes (RN-X-03); (5) cierre del modelo D-SQL-1 a D-SQL-5: `hogar_miembros.usuario_id` e `invitaciones_hogar.invitado_por` opcionales con borrado a nulo, `hogares.perfil_simulacion_id` obligatorio, restricciones de coherencia y RLS (sección 3); (6) Supabase, SMTP (Brevo), contraseña, Storage y JWT (RN-I-02, RN-IX-02, RN-IX-03); (7) formatos de `regla_origen`, `clave_evento` y `consejos.categoria`; (8) transición energética ratificada fuera del MVP. Sigue en 18 tablas, sin columnas nuevas. El documento v4.8 queda como histórico.

**Cambios de la v4.8 (02/11/2026):** decisiones de Nicolás sobre el catálogo de textos: (1) la referencia del cierre de mes (alerta RN-XIV-07 y consejo general de RN-XV-07) es siempre la del hogar (meta activa o promedio histórico), porque la alerta es única por hogar; la preferencia `base_comparacion` de cada miembro solo cambia las cards individuales (RN-XI-03, RN-XI-04, RN-XVI-03); (2) al cerrar sesión en Onboarding o Invitación recibida, la ficha de usuario (RN-IX-01) persiste; solo se cancela la creación del hogar. Sin tablas nuevas ni cambios de campos: siguen 18 tablas. **Pendiente:** verificación de las plantillas de correo de Supabase y revisión en dispositivo de los textos.

**Cambios de la v4.7 (02/11/2026):** a pedido de Nicolás, el pico del gráfico se pinta en rojo claro (`chart/peak` = #F59099, red-400 de la paleta), no en cian. Para que no se confunda con el estado crítico (`status/error` #EF4444), RN-XIII-03 fija una regla de separación: el pico no usa componentes de estado ni la palabra de estado, su etiqueta es neutra y el rojo de estado queda solo para «Crítico» (D17, que reemplaza a D12 y ajusta la D5). Sin tablas nuevas ni cambios de campos: siguen 18 tablas. **Pendiente:** verificar en dispositivo y con daltonismo; no hay accesibilidad certificada. El documento v4.6 queda como histórico.

**Cambios de la v4.6 (02/11/2026):** a partir de la revisión de Nicolás de las pantallas v4.5 en Figma: (1) el pico del gráfico lleva un color propio, el cian `chart/peak` (#38BDF8), además de la etiqueta «Pico»; sigue sin rojo ni amarillo (RN-XIII-03, D12, que ajusta la D5); (2) «Cerrar sesión» tiene un segundo punto de acceso, en el Onboarding y en la Invitación recibida, con el alcance de cancelar la creación del hogar (RN-IX-08, D13); (3) queda aprobada la lista de operadores de la tarifa (RN-XVI-05, D14) y los íconos de Lavandería, Terraza, Garaje y Cuarto de servicio (D15); (4) el anillo de distribución por zona queda vigente en Historial (RN-XIII-04, D16). No hay tablas nuevas ni cambios de campos: siguen 18 tablas. El documento anterior (v4.5) queda como histórico.

**Cambios de la v4.5 (02/11/2026):** Nicolás aceptó como decisión todas las recomendaciones de la propuesta v4.5 y de la revisión de la v4.4: (1) la card «Todo bajo control» solo aparece sin consejos pendientes (RN-XV-02, §7.2); (2) el anillo de zonas agrupa en «Otras zonas» desde la quinta zona y la lista muestra todas (RN-XIII-04); (3) formato numérico es-CO con decimales por unidad (RN-XII-08); (4) el pico se marca sin rojo, con la etiqueta «Pico»; el rojo queda para el estado crítico (RN-XIII-03); (5) el acumulado de hoy respeta el interruptor personal de comparación (RN-XI-04); (6) el estado `expirada` de las invitaciones se calcula al consultar (RN-X-05); (7) las alertas no leídas nunca se ocultan (RN-XIV-05); (8) una alerta por regla y zona al día, dicho de forma explícita (RN-XIV-08); (9) vigencia de los consejos pendientes de 7 días (RN-XV-05); (10) correcciones editoriales en §3, §4 y §6.5; (11) quedan ratificadas las decisiones 13, 17, 18 y 20 (sección 9.2). No hay tablas nuevas ni cambios de campos: siguen 18 tablas.

**Cambios de la v4.4:** (1) el backfill forma parte de la transacción de creación del hogar y, si falla, no queda nada creado (RN-X-03); (2) el backend envía el correo de invitación y se definen los casos de invitación repetida (RN-X-05); (3) la salida del administrador es en dos pasos con las pantallas existentes (RN-II-04, RN-X-07); (4) Fuentes de datos oculta los valores en kW sin el permiso de ver consumo actual (RN-XVI-06, RN-XVII-01); (5) la ficha del usuario se crea en el primer acceso con sesión (RN-IX-01); (6) las invitaciones pendientes solo las ve el administrador (RN-X-08, RN-XVI-07); (7) la foto se sube directamente a Storage (RN-I-02); (8) los mensajes por estado se entregan como códigos (RN-XI-09); (9) la personalidad es un dato interno y el backend verifica membresía, rol y permiso en cada llamada (RN-X-04, RN-I-03); (10) los parámetros de las 5 personalidades quedan cerrados con el acta 04 y la semilla usa SHA-256 (secciones 5 y 8.1); (11) nota en la tabla 12 sobre la cocina de *Consumo compacto*; (12) tres definiciones de diseño pendiente, sin pantallas nuevas ni cambios de navegación (sección 7); (13) nuevo apartado 9.1 con las decisiones aceptadas por Nicolás y pendientes actualizados (secciones 9 y 10).

**Cambios de la v4.3:** (1) la personalidad de simulación ya no se asigna al azar: se asigna por tipo de vivienda y zonas elegidas (RN-X-04), con 5 personalidades descritas en la tabla 12; (2) el catálogo de vivienda cambia a `apartamento`, `casa`, `apartaestudio`, `duplex` y `casa_campestre` (se quitan `cuarto` y `otro`); (3) el catálogo de zonas pasa de 6 a 9 (se agregan `terraza`, `garaje` y `cuarto_servicio`); (4) se definen las restricciones de zonas por tipo de vivienda y los filtros de la pantalla de onboarding (RN-X-02 y RN-X-09); (5) `perfiles_simulacion` agrega 3 columnas de base y `curva_horaria` pasa a ser una curva base más curvas propias por zona; (6) el simulador genera consumo solo para las zonas del hogar y no reparte el consumo de las zonas ausentes (RN-IV-07); (7) el modelo matemático (sección 5) usa curva y ruido por zona, con `ruido_config` común a todas las zonas, e incluye la estructura de los campos JSON; (8) se reescribe la condición de validez 6; (9) se corrige el ejemplo de Andrés; (10) la memoria e intensidad del ruido por zona queda como posible implementación futura (sección 2).

**Cambios de la v4.2:** (1) `perfiles_simulacion` lista las 6 columnas de base, incluida lavandería; (2) `metas_consumo` agrega `fecha_inicio` y `fecha_fin`; (3) las vigencias de tarifa y de meta usan intervalo con el fin excluido; (4) se confirma `inactivo` como estado de membresía; (5) `clave_evento` es única; (6) `consejos_usuario` valida el estado contra la fecha; (7) la campana se muestra solo a quien tiene el permiso de recibir alertas; (8) cada hogar tiene una sola fuente principal.

**Cambios de la v4.1:** Cerrar sesión queda solo en Configuración; el bloqueo por falta de permiso afecta solo las cards de datos (el saludo y la campana siguen visibles); los catálogos iniciales de alertas y consejos son ampliables; el texto de alerta crítica pasa a "Consumo crítico".

**Convenciones:**
* Cada regla tiene un identificador `RN-<bloque>-<número>` para poder trazarla en pruebas y tareas.
* Los valores y textos que aparecen en los mockups son ejemplos, no datos finales.
* Las decisiones que no fueron tomadas explícitamente por el equipo, sino resueltas con la recomendación más simple y coherente, están listadas en la sección 9.
* Fase 1 = MVP. Fase 2 = funciones posteriores (sección 2).

# **1. Reglas de Negocio (Zentheris MVP)**

## **I. Identidad, Acceso y Privacidad**

* **RN-I-01 · Autenticación segregada:** La seguridad y el acceso (contraseñas, recuperación) son delegados enteramente a Supabase (`auth.users`). Zentheris almacena únicamente una ficha de perfil (`usuarios`) vinculada 1:1, asegurando que el sistema no manipule credenciales en texto plano.  
* **RN-I-02 · Gestión de foto de perfil:** El usuario puede agregar o eliminar una foto personal almacenada en Supabase Storage. Si la elimina o no la sube, el sistema genera automáticamente un avatar con sus iniciales. La app sube la foto directamente a la carpeta del usuario en Storage y el backend guarda solo su ruta en `avatar_url`. **(v4.9, DC-43)** Bucket privado `avatares`, ruta `{usuario_id}/avatar.{jpg|png|webp}`, máximo 2 MB; escribe solo el dueño; leen el dueño y los miembros activos de su hogar; la app la muestra con una URL firmada.  
* **RN-I-03 · Aislamiento por hogar:** Un usuario solo puede leer y escribir datos de hogares donde tiene una membresía activa. El backend comprueba en cada llamada la membresía activa, el rol y el permiso que exige la acción; las políticas de seguridad por fila (RLS) de Supabase quedan como segunda defensa y se prueban en la fase de pruebas.

## **II. Pertenencia y Gestión del Hogar**

* **RN-II-01 · Una membresía activa por usuario:** En el MVP un usuario pertenece como máximo a un hogar activo a la vez (índice único parcial).  
* **RN-II-02 · Límites de membresía:** Un hogar tendrá como máximo **5 miembros activos**, incluyendo a **1 único administrador**.  
* **RN-II-03 · Permisos generales del hogar:** Los 4 permisos viven en `hogares` y aplican por igual a todos los miembros (no hay permisos distintos por persona). Por defecto: *ver consumo actual*, *ver historial* y *recibir alertas* activados, y *modificar metas* desactivado. El administrador siempre conserva acceso total.  
* **RN-II-04 · Salida y Expulsión:** Un miembro puede abandonar el hogar voluntariamente. El administrador tiene la potestad de expulsar a un miembro invitado. Si el administrador decide salir, primero transfiere el rol al miembro activo que designe, sin que este deba aceptarlo, y después sale (RN-X-07).  
* **RN-II-05 · Catálogo de Vivienda:** El hogar debe clasificarse obligatoriamente en una de 5 opciones predefinidas: `apartamento`, `casa`, `apartaestudio`, `duplex` (se muestra "Dúplex") y `casa_campestre` (se muestra "Casa campestre").

## **III. Espacios Físicos (Zonas) e Infraestructura**

* **RN-III-01 · Selección única y cerrada:** Las zonas de la vivienda se configuran exclusivamente durante el *onboarding*. No hay opciones para agregar, renombrar o eliminar zonas posteriormente en el MVP. El nombre de cada zona se asigna automáticamente según su tipo (por ejemplo, `cocina` se muestra como "Cocina"), es único dentro del hogar y no se edita.  
* **RN-III-02 · Catálogo de Zonas:** Restringido a 9 opciones fijas, agrupadas así: zonas **básicas** (`cocina`, `sala`, `dormitorio`, `bano`), **complementarias** (`oficina`, `lavanderia`) y **extras** (`terraza`, `garaje`, `cuarto_servicio`).  
* **RN-III-03 · Transparencia de sensores:** Las fuentes de medición y sensores son entidades de uso interno para el backend. El usuario no registra, conecta ni gestiona medidores físicos o virtuales; solo puede consultarlos en la pantalla de solo lectura Fuentes de datos.

## **IV. Motor de Simulación y Datos (Backfill)**

* **RN-IV-01 · Llenado inicial (Backfill):** Al completarse el *onboarding*, el sistema generará automáticamente 30 días de historial retroactivo (720 horas) utilizando los parámetros exactos de la personalidad (`perfiles_simulacion`) asignada al hogar, incluyendo su ruido y probabilidad de picos.  
* **RN-IV-02 · Experiencia de Usuario:** Durante la generación del Backfill, el usuario verá una pantalla de carga para garantizar que los datos estén completos al acceder al Panel Principal.  
* **RN-IV-03 · Consumo Horario:** Todo consumo almacenado representa el promedio de potencia (kW) medido a lo largo de 1 hora completa. No hay medición instantánea de segundos.  
* **RN-IV-04 · Versión del modelo:** La versión del modelo de simulación es una constante en el código del backend (entra en el cálculo de la semilla); no se guarda en tablas.  
* **RN-IV-05 · Generación hora a hora y recuperación:** El simulador agrega una lectura por sensor y hora. Si el servidor estuvo apagado, al arrancar genera las horas faltantes desde la última lectura hasta la última hora completa. La restricción única (`sensor_id`, `fecha_hora`) evita duplicados. **(v4.9, DC-34)** Como el servidor puede suspenderse, la recuperación también se ejecuta **antes de responder cualquier consulta de consumo del hogar** (Panel, Zonas, Historial, Fuentes de datos, Alertas), además de al arrancar y en la tarea programada mientras el servidor está activo.  
* **RN-IV-06 · Regla de no alteración:** Bajo ninguna circunstancia el usuario puede ingresar lecturas manuales ni editar el historial de kWh.
* **RN-IV-07 · Zonas simuladas:** el simulador genera lecturas solo para las zonas que el hogar eligió (un sensor por zona). Si la personalidad trae datos de una zona que el hogar no tiene, esos datos se ignoran: no se genera consumo para esa zona y su consumo no se reparte entre las demás. Por eso, un hogar con menos zonas que las que contempla su personalidad tiene un consumo total menor.

## **V. Reglas Financieras y Metas**

* **RN-V-01 · Cálculo en COP:** El costo financiero se calcula multiplicando el consumo en kWh por el precio del operador configurado (`tarifas_hogar`).  
* **RN-V-02 · Manejo del Cargo Fijo Mensual:** Si el usuario configura un cargo fijo, este valor **NO** se prorratea diariamente. Se suma intacto única y exclusivamente al costo total proyectado del mes.  
* **RN-V-03 · Límite de metas:** Solo puede existir una meta activa por hogar en kWh/mes. El tipo de meta (ahorro, eficiencia, presupuesto) solo cambia los textos visuales de la app, pero no genera alertas automáticas.

## **VI. Alertas y Consejos (Notificaciones In-App)**

* **RN-VI-01 · Aislamiento de entrega:** Las notificaciones (alertas y consejos) vivirán únicamente en la campana dentro de la aplicación móvil. No se integrarán notificaciones Push al dispositivo.  
* **RN-VI-02 · Entrega condicionada:** Una alerta se entrega (`alertas_usuario`) solo a los miembros que tengan el permiso de recibir alertas activo **en el instante exacto en que se dispara el evento**. No tiene efecto retroactivo.  
* **RN-VI-03 · Categorías y consejos:** La campana tiene 3 categorías de alerta: `consumo`, `consejo` e `informacion`. La categoría `consejo` es solo el aviso de que existe una recomendación; el contenido y su seguimiento viven en `consejos` y `consejos_usuario`. Los consejos se muestran a todos los miembros activos del hogar y cada uno registra su propio estado.  
* **RN-VI-04 · Interruptores personales:** `notif_consumo` y `notif_consejos` son individuales y solo controlan los avisos dentro de la campana de esa persona (no hay notificaciones externas). Se suman al permiso del hogar: el permiso decide si la alerta se entrega y el interruptor si la persona la ve.  
* **RN-VI-05 · Seguimiento independiente:** Marcar una alerta como "leída" o un consejo como "completado" es una acción individual que no afecta la bandeja de los demás familiares.

## **VII. Preferencias del Usuario**

* **RN-VII-01 · Alcance:** El campo `base_comparacion` (meta vs. promedio) es estrictamente individual y no afecta lo que ven otros miembros del hogar. Su valor por defecto es `promedio`.

## **VIII. IA y Machine Learning**

* **RN-VIII-01 · Prohibición actual:** No se implementará IA ni Machine Learning predictivo para adaptar la entrega de alertas o consejos según el comportamiento del usuario en el MVP. Todo funcionará por reglas matemáticas y umbrales.

## **IX. Registro, Acceso y Cuenta**

* **RN-IX-01 · Datos de registro:** nombre completo, correo, celular (**opcional**, el diseño lo indica como tal), contraseña y repetir contraseña. Repetir contraseña es solo una validación de la pantalla y no se guarda. La ficha (`usuarios`) y `preferencias_usuario`, con valores por defecto, se crean en el primer acceso con sesión. Con la verificación de correo activa, ese acceso ocurre después de confirmar el correo; mientras tanto, el nombre y el teléfono se guardan en los metadatos del registro de Supabase Auth.  
* **RN-IX-02 · Reglas de contraseña:** mínimo 8 caracteres, una mayúscula y un número. En el cambio de contraseña además debe ser distinta a la actual. La app valida estas reglas en el formulario. **(v4.9, DC-05)** Supabase Auth se configura con mínimo 8 caracteres y el requisito «letras y dígitos» (no tiene una opción idéntica a esta regla); la mayúscula y el número los valida la app en registro y restablecimiento, y el backend en el cambio de contraseña (`CONTRASENA_NO_CUMPLE_REGLAS`).  
* **RN-IX-03 · Verificación de correo:** la gestión de la cuenta es por correo. En desarrollo se usa un solo proyecto de Supabase con "Confirm email" desactivado; antes de la entrega se activa con un SMTP propio (tarea de entrega). **(v4.9, DC-03, DC-04)** Proyecto `zentheris-dev` en us-east-1; SMTP Brevo (plan gratuito, 300 correos al día) para Supabase Auth y para las invitaciones del backend; sin SMTP en desarrollo local, el backend escribe el enlace de invitación en el log. Con la verificación activa, el registro muestra el aviso "Revisa tu correo".  
* **RN-IX-04 · Recuperación de contraseña:** desde "¿Olvidaste tu contraseña?" el usuario escribe su correo, recibe un enlace de Supabase y define una nueva contraseña que cumple las reglas.  
* **RN-IX-05 · Cambio de contraseña:** exige ingresar primero la contraseña actual; los campos de la nueva contraseña solo se habilitan cuando la actual es correcta (verificación propia del backend, porque Supabase no la trae integrada).  
* **RN-IX-06 · Cambio de correo:** el usuario escribe el nuevo correo y lo confirma; Supabase envía un enlace de confirmación y el correo cambia al confirmarse. El correo actual se muestra solo como lectura.  
* **RN-IX-07 · Edición de perfil:** solo se editan nombre completo y teléfono (opcional), en la misma pantalla. El correo se cambia únicamente desde Gestionar correo.  
* **RN-IX-08 · Cerrar sesión:** el punto de acceso principal está en Configuración (sección Otros) y cierra la sesión en este dispositivo. Un usuario sin hogar no llega a Configuración, por eso hay un segundo punto de acceso: el enlace «Cerrar sesión» en las pantallas Onboarding e Invitación recibida (solo en esas dos). Ahí cierra la sesión **y cancela la creación del hogar**: no se guarda nada del hogar (hogar, zonas ni datos del paso 1 o 2; no hay borradores en el servidor) y al volver a iniciar sesión el onboarding empieza de cero (v4.6, D13). La ficha `usuarios` creada en el primer acceso (RN-IX-01) **sí persiste**; solo se cancela la creación del hogar (v4.8). Antes de cerrar la sesión ahí se muestra un diálogo de confirmación (catálogo `onboarding.cerrar_sesion_dialogo.*`, v4.9, DC-09). Editar perfil sigue sin «Cerrar sesión».  
* **RN-IX-09 · Eliminar cuenta:** es irreversible y exige una confirmación. El administrador no puede eliminar su cuenta sin transferir antes el rol. Se eliminan los datos personales del usuario (`usuarios`, `preferencias_usuario`, su seguimiento en `alertas_usuario` y `consejos_usuario`, y su foto) y se cierra su membresía. Los datos del hogar (lecturas, zonas, tarifas, metas, alertas y consejos) se conservan para los demás miembros; si era el único miembro, se elimina también el hogar con sus datos.

## **X. Onboarding, Hogar y Membresía**

* **RN-X-01 · Punto de entrada:** tras iniciar sesión, un usuario sin hogar y con una invitación pendiente ve primero la pantalla Invitación recibida (aceptar o rechazar). Un usuario sin hogar y sin invitación pasa al onboarding.  
* **RN-X-02 · Datos del onboarding:** nombre del hogar, tipo de vivienda (obligatorio, una de las 5 opciones) y selección de zonas del catálogo de 9, con estas restricciones según el tipo de vivienda: **apartaestudio** elige entre 3 y 5 zonas en total, solo entre las básicas, `oficina` y `lavanderia` (sin extras) y con al menos 3 básicas; **apartamento, casa, dúplex y casa campestre** deben incluir las 4 zonas básicas (`cocina`, `sala`, `dormitorio`, `bano`) y pueden agregar cualquier otra, sin límite superior. Estrato, ciudad, número de personas y demás datos del hogar son de la Fase 2.  
* **RN-X-03 · Creación del hogar:** ocurre en una sola transacción: hogar, membresía de administrador, zonas, la única fuente principal del hogar, llamada "Fuente principal [nombre del hogar]", un sensor por zona vinculado a esa fuente, permisos por defecto y personalidad de simulación. La transacción incluye el backfill de 30 días (RN-IV-01): si cualquier paso falla no se crea nada, ni hogar ni lecturas, y la pantalla de carga muestra un error con la opción de reintentar. Mientras se ejecuta, la app muestra la pantalla de carga (RN-IV-02). **(v4.9, DC-33)** Se mantiene síncrono: en local, generar las 6.480 lecturas del peor caso (9 zonas) tomó 0,03 s y guardarlas en PostgreSQL 16 en un solo lote, 0,12–0,14 s. Las lecturas se insertan por lotes (nunca fila por fila). Solo si el p95 medido en el servidor de despliegue supera 10 s se pasa a una respuesta 202 con consulta de estado, sin columnas nuevas. Las restricciones de RN-X-02 se validan también en el backend dentro de esta transacción.  
* **RN-X-04 · Asignación de la personalidad:** la personalidad se asigna de forma determinista según el tipo de vivienda y las zonas elegidas, no al azar. Se calcula al crear el hogar (RN-X-03) y no cambia después. Variables: **c** = cantidad de zonas elegidas entre `oficina`, `lavanderia`, `terraza` y `garaje`; **s** = 1 si el hogar tiene `cuarto_servicio`, 0 si no; **E** = cantidad de extras elegidas (`terraza`, `garaje`, `cuarto_servicio`); **OL** = tiene `oficina` o `lavanderia`. Para **apartaestudio**: 3 o 4 zonas → *Consumo compacto*; 5 zonas → *Consumo eficiente*. Para **apartamento, casa y dúplex**, se evalúa en este orden y gana la primera que se cumpla: (1) E ≥ 2 y OL → *Consumo amplio*; (2) c ≥ 2 o s = 1 → *Consumo familiar*; (3) c = 1 y s = 0 → *Consumo intermedio*; (4) c = 0 y s = 0 → *Consumo eficiente*. Para **casa campestre** se calcula como una casa y se sube un nivel (eficiente → intermedio, intermedio → familiar, familiar → amplio, amplio → amplio). El detalle, los ejemplos y la descripción de cada personalidad están en la tabla 12 (sección 3). Si la personalidad que corresponde no existe o está inactiva (`activo = false`), se usa *Consumo eficiente*. La personalidad es un dato interno del simulador: no se muestra en la app ni se expone en la API.  
* **RN-X-05 · Invitaciones:** solo las envía el administrador, por correo, con un enlace único que vence a los 7 días (el estado `expirada` se calcula al consultar, cuando `expira_en` es anterior a la hora actual; no hay un proceso programado). Quien no tiene cuenta debe crearla antes de aceptar. No se puede invitar cuando miembros activos más invitaciones pendientes suman 5; el límite de 5 activos se valida también al aceptar. El backend genera el enlace, guarda solo el hash del token y envía el correo con el SMTP del proyecto; el enlace abre la app. No se puede invitar a un correo que ya tiene una invitación pendiente en el mismo hogar ni a un miembro activo del hogar; el administrador puede cancelar la invitación y volver a invitar. **(v4.9, DC-42)** Al invitar, el backend marca primero como `expirada` cualquier invitación pendiente ya vencida del mismo correo en ese hogar, dentro de la misma transacción. Si el correo pertenece a una persona con otro hogar activo, la invitación se envía igual y falla al aceptar (RN-II-01), para no revelar a quién pertenece cada cuenta.  
* **RN-X-06 · Respuesta a una invitación:** al aceptar se crea la membresía con rol `miembro` y se genera una alerta de información "[Nombre] se unió al hogar". Al rechazar, la invitación queda `rechazada`. El administrador puede cancelar una invitación pendiente (`revocada`).  
* **RN-X-07 · Salida, expulsión y transferencia:** un miembro puede salir del hogar (`inactivo` y `fecha_salida`). El administrador puede expulsar a un miembro y transferir la administración a otro miembro activo, sin que este deba aceptar. El administrador no puede salir sin transferir antes el rol: son dos pasos separados con las pantallas existentes (transfiere desde el menú de acciones, pasa a ser miembro y sale con "Salir del hogar"). Si es el único miembro, no puede salir: elimina su cuenta y con ella el hogar (RN-IX-09). Todas estas acciones piden confirmación.  
* **RN-X-08 · Quién gestiona:** invitar, expulsar, transferir, cancelar invitaciones y mover los permisos es exclusivo del administrador. Los demás miembros ven la lista de miembros y los permisos en solo lectura, no ven las invitaciones pendientes y tienen el botón "Salir del hogar".
* **RN-X-09 · Filtros de la pantalla de onboarding:** la interfaz aplica en tiempo real las restricciones de RN-X-02: (a) el tipo de vivienda se elige primero y define las zonas disponibles; (b) con apartaestudio solo se muestran sala, cocina, dormitorio, baño, oficina y lavandería (sin extras), con un contador de 3 a 5 zonas: no se puede continuar con menos de 3 zonas básicas y al llegar a 5 se bloquean las demás; (c) con apartamento, casa, dúplex y casa campestre se muestran las 9 zonas y las 4 básicas aparecen marcadas y no se pueden desmarcar; (d) si el usuario cambia el tipo de vivienda con zonas ya elegidas, la selección se ajusta a lo permitido y se muestra un aviso; (e) cada bloqueo muestra un mensaje de ayuda que explica la razón. La validación del backend (RN-X-03) se mantiene: la interfaz no la sustituye.

## **XI. Estados de Consumo y Referencias**

* **RN-XI-01 · Consumo actual:** es el de la última hora completa (kW promedio de esa hora, no una medición instantánea) y se actualiza una vez por hora.  
* **RN-XI-02 · Estados:** hay tres, normal, elevado y crítico. Se calculan al consultar y no se guardan. Todos los textos usan "crítico" (no "sobreconsumo").  
* **RN-XI-03 · Referencia de comparación:** el promedio histórico de esa **misma hora del día** o, si el usuario tiene `base_comparacion = 'meta'` y una meta activa, la meta. Si elige meta y no hay meta activa, se usa el promedio histórico. "Sin referencia suficiente" es solo un respaldo: el backfill de 30 días debe evitar llegar a él. **(v4.9, DC-28)** El promedio histórico de una hora es el promedio de esa misma hora en los 30 días completos anteriores, ignorando horas sin lectura; con menos de 7 días con dato el estado es `sin_referencia`. Con meta, la referencia de una hora es el límite diario (meta mensual ÷ días del mes) repartido según el peso habitual de esa hora en el hogar (promedio de la hora ÷ suma de los 24 promedios).  
* **RN-XI-04 · Consumo acumulado de hoy:** suma hasta la última hora completa. Si el usuario tiene `base_comparacion = 'meta'` y hay una meta activa, se compara contra el límite diario (meta mensual ÷ días del mes) y se muestra el texto "Límite"; en otro caso se compara contra el promedio de lo acumulado hasta esa misma hora en días anteriores y no se muestra el límite. **(v4.9)** Con meta, el estado se mide como porcentaje del límite diario: normal por debajo de 80 %, elevado desde 80 % y crítico desde 100 % («Dentro», «Cerca» y «Superaste el límite»).  
* **RN-XI-05 · Participación de una zona:** es el consumo de la zona dividido entre el total de la última hora completa (la suma de las zonas activas; no se guarda una lectura extra del hogar). Su estado compara esa participación contra la participación habitual de la zona en el hogar, calculada con el backfill (v4.9: a la misma hora del día, en los 30 días previos). Es el mismo estado en el Panel, en Zonas y en la card de participación de la Zona individual.  
* **RN-XI-06 · Estado de consumo de una zona:** se muestra solo en la Zona individual y se compara siempre contra el promedio histórico de esa zona en esa misma hora del día, nunca contra una meta (la meta es del hogar).  
* **RN-XI-07 · Umbrales:** los porcentajes que separan normal, elevado y crítico son parámetros de calibración, iguales para todos los hogares en el MVP, definidos en un archivo de configuración del backend (no en tablas). Queda anotado evaluar más adelante si se personalizan por hogar. **(v4.9, DC-27)** Valores v1, calibrados con datos simulados (`04_datos-simulados/calibracion-umbrales-v1/umbrales-estado.v1.json`): consumo actual +20 % elevado y +40 % crítico; acumulado contra promedio +15 % y +30 %; estado de zona +30 % y +60 % con un exceso mínimo de 0,05 kWh; participación de zona +25 % y +50 % con el mismo exceso mínimo; día completo +15 % y +30 %. Los porcentajes se comparan redondeados a 6 decimales y los límites son inclusivos.  
* **RN-XI-08 · Costo en COP:** solo se muestra si existe una tarifa vigente; los kWh se muestran siempre. Sin tarifa, las cards de costo piden configurarla.  
* **RN-XI-09 · Mensajes de estado:** los textos cortos por estado (comparación con la hora anterior, "vas bien, sigue así", etc.) salen de un catálogo de textos. El backend entrega un código por estado y la app muestra el texto de su catálogo. Los títulos y mensajes de alertas y consejos los escribe el backend desde un archivo de configuración.

## **XII. Panel Principal, Zonas y Zona Individual**

* **RN-XII-01 · Saludo:** usa el primer nombre y cambia según la hora de Bogotá: "Buenos días" de 5:00 a 11:59, "Buenas tardes" de 12:00 a 18:59 y "Buenas noches" de 19:00 a 4:59.  
* **RN-XII-02 · Campana:** abre Alertas y muestra un indicador mientras haya alertas sin leer. Solo se muestra a quien tiene el permiso de recibir alertas; con ese permiso apagado, el miembro no ve la campana ni las alertas nuevas.  
* **RN-XII-03 · Nombres de zona:** se muestran Cocina, Sala, Dormitorio, Baño, Lavandería, Oficina, Terraza, Garaje y Cuarto de servicio, tomados del tipo. Las zonas se listan en orden alfabético por nombre en el Panel y en Zonas.  
* **RN-XII-04 · Selector kW/COP:** cambia todas las cards de la pantalla; COP solo aparece si hay tarifa vigente.  
* **RN-XII-05 · Zonas del Panel:** vista larga o compacta, con la participación de cada zona en la última hora completa y su estado.  
* **RN-XII-06 · Zonas (general):** cada card muestra ícono, nombre, kW de la última hora completa y estado de participación, y abre la Zona individual.  
* **RN-XII-07 · Zona individual:** tiene flecha atrás, nombre, un banner con el ícono de la zona (sin datos) y 3 cards: estado actual con gráfico (gauge o anillo y kW/COP), estado actual en texto y participación. No hay edición de la zona.
* **RN-XII-08 · Formato numérico:** formato es-CO: coma decimal y punto de miles ("2,40 kW", "$14.400"); en cards y ejes los miles se abrevian con «k» minúscula ("$6,5k"); los porcentajes llevan espacio ("34 %"). Decimales por unidad: kW, 2 decimales; kWh, 1 decimal ("145,3 kWh"); COP, sin decimales. Es una convención de presentación y no altera cálculos. Los ejemplos de este documento con un decimal en kW son anteriores a esta convención y se leen con 2 decimales.

## **XIII. Historial**

* **RN-XIII-01 · Periodos:** Día = hoy desde 00:00 hasta la última hora completa; Semana = de lunes hasta hoy; Mes = del día 1 hasta hoy. Cada comparación usa el mismo tramo del periodo anterior. Si no hay periodo anterior, se muestra "no hay datos". **(v4.9, DC-29)** Tramo anterior: ayer de 00:00 a la misma hora; la semana anterior del lunes al mismo día y hora; el mes anterior del día 1 al mismo día y hora (si el mes anterior es más corto, hasta su último día). Solo vale si tiene lecturas en todas sus horas; si no, "no hay datos". Variación: menor por debajo de −5 %, similar de −5 % a menos de +10 % (estado normal), mayor de +10 % a menos de +25 % (elevado) y muy mayor desde +25 % (crítico).  
* **RN-XIII-02 · Navegación:** solo los botones Día, Semana y Mes, que cambian todas las cards. No hay flechas ni calendario en el MVP.  
* **RN-XIII-03 · Pico:** es un valor (una hora en Día, un día en Semana y Mes) que supera el promedio histórico. La card muestra el último pico (el más reciente) y su estado mide cuánto lo supera. El gráfico marca el pico más alto del periodo, que puede ser otro, con un color propio, el rojo claro `chart/peak` (#F59099), y con la etiqueta «Pico», que no depende solo del color (v4.7, D17). **Regla de separación con el estado crítico:** (a) el pico no usa componentes de estado (píldora, ícono ni fondo de estado) ni muestra la palabra «Normal», «Elevado» o «Crítico»; (b) la etiqueta «Pico» es neutra (`text/primary`) con borde o relleno en rojo claro; (c) el rojo de estado (`status/error`, `chart/series4`) queda solo para estados (píldora, arco o anillo con la palabra y el ícono de estado) y nunca rellena una barra de serie ni una etiqueta de pico; (d) el pico se identifica por su posición y su etiqueta antes que por el color; (e) la card de Pico muestra el estado en texto, nunca con el color del pico. El color del pico solo ayuda a verlo; no cambia el estado. **(v4.9, DC-31)** Un valor es pico si supera su promedio histórico en al menos 10 % (en Día, el de esa hora; en Semana y Mes, el promedio diario de los 30 días previos). Su estado usa los umbrales del consumo actual (Día) o del día completo (Semana y Mes). Si ningún valor llega al 10 %, la card muestra «Sin picos en este periodo».
* **RN-XIII-04 · Gráfico de consumo:** barras, línea o anillo. El anillo (participación por zona) solo se ve con el filtro General y sus colores solo identifican cada zona. El filtro muestra General y las zonas del hogar. En el anillo, si el hogar tiene más de 4 zonas, se muestran las 4 de mayor participación y el resto se agrupa en «Otras zonas» (participación sumada del grupo); la lista junto al anillo muestra todas las zonas con su nombre y porcentaje.  
* **RN-XIII-05 · Costo estimado:** muestra el costo del periodo y la proyección al cierre, sin barra de progreso. El cargo fijo mensual solo entra en la vista Mes. El costo de cada fecha usa la tarifa vigente en esa fecha. **(v4.9, DC-30)** Proyección en kWh = acumulado del periodo + promedio de cada hora que falta hoy + días completos restantes × promedio diario de los últimos 30 días. Proyección en COP = costo acumulado + (proyección − acumulado) × precio vigente hoy + cargo fijo (solo en la vista Mes). Con datos simulados, el error medio fue de 1,4 % el primer día del mes.  
* **RN-XIII-06 · Unidades:** los totales de un periodo se expresan en kWh; el kW se usa para el consumo de una hora.  
* **RN-XIII-07 · Exclusiones:** no hay descarga de reportes (Fase 2) y las cards se muestran solo con minititulos, sin textos complementarios.

## **XIV. Alertas**

* **RN-XIV-01 · Filtros:** Todas, Consumos, Consejos e Información, que corresponden a las categorías `consumo`, `consejo` e `informacion`.  
* **RN-XIV-02 · Indicador de cada alerta:** un punto relleno significa no leída y un círculo vacío significa leída. El color del punto es la severidad: rojo crítica, amarillo advertencia, verde informativa.  
* **RN-XIV-03 · Lectura:** las alertas visibles se marcan como leídas (`leida_en`) cuando el usuario entra a la pantalla. Tocar una alerta no hace nada.  
* **RN-XIV-04 · Orden y tiempo:** la más reciente primero, con tiempo relativo ("Hace 10 min", "Ayer").  
* **RN-XIV-05 · Ocultamiento:** 7 días después de `leida_en`, la alerta se oculta de la lista de esa persona. No se borra el registro. Las alertas no leídas nunca se ocultan.  
* **RN-XIV-06 · Entrega:** solo a miembros que, al disparar el evento, tengan el permiso de recibir alertas y el interruptor personal correspondiente encendido (`notif_consumo` para las categorías consumo e información; `notif_consejos` para la categoría consejo).  
* **RN-XIV-07 · Catálogo inicial de alertas:** (1) *Consumo elevado*, categoría consumo, severidad advertencia: una zona entra en estado elevado. (2) *Consumo crítico*, categoría consumo, severidad crítica: una zona entra en estado crítico. (3) *Cierre de mes*, categoría información: se genera al terminar el mes calendario, con severidad informativa si el mes quedó dentro de la referencia y advertencia si la superó. La referencia es la del hogar (meta activa del hogar o promedio histórico), no la preferencia individual de cada miembro, porque la alerta es única por hogar (v4.8). (4) *Nuevo miembro*, categoría información, informativa: "[Nombre] se unió al hogar". (5) *Nuevo consejo*, categoría consejo, informativa: avisa que hay una recomendación nueva. Este catálogo es solo la base inicial: se pueden modificar y agregar reglas sin cambiar tablas (cada regla se identifica por `regla_origen`). **(v4.9, DC-32, DC-35)** Las alertas de consumo se evalúan solo sobre horas generadas en vivo, nunca sobre el backfill; «entra en estado» significa que la hora recién generada de la zona queda en elevado o crítico (RN-XI-06). El cierre de mes se evalúa en la primera generación posterior a las 00:00 del día 1, solo para meses que terminan después de la creación del hogar; sin meta activa el último día del mes, la referencia es el promedio diario de los días completos anteriores al mes (máximo 90) × los días del mes.  
* **RN-XIV-08 · Sin duplicados:** `clave_evento` combina regla, zona (o hogar) y fecha; una misma regla no se repite en la misma zona más de una vez al día: si la zona cambia de estado varias veces en el mismo día, solo se genera una alerta para esa regla y zona. Una alerta de estado elevado y otra de estado crítico son reglas distintas. **(v4.9, DC-25)** Formato: `<regla_origen>:<zona_id>:<AAAA-MM-DD>` (consumo), `<regla_origen>:<hogar_id>:<AAAA-MM>` (cierre de mes), `nuevo_miembro:<membresia_id>` y `nuevo_consejo:<consejo_id>`. Valores de `regla_origen` en alertas: `consumo_elevado`, `consumo_critico`, `cierre_mes_dentro`, `cierre_mes_encima`, `nuevo_miembro`, `nuevo_consejo_zona`, `nuevo_consejo_general`.  
* **RN-XIV-09 · Sin alertas:** la pantalla muestra un estado vacío.

## **XV. Consejos**

* **RN-XV-01 · Fase 1:** los consejos son estáticos y no accionables. Se prevé que más adelante un consejo de zona lleve a su zona.  
* **RN-XV-02 · Estado vacío:** la card "Todo bajo control" se muestra cuando no hay consejos pendientes, y debajo se ven los completados aún visibles, opacos. Con consejos pendientes no se muestra la card: se muestra la lista, con los completados opacos al final.  
* **RN-XV-03 · Completado:** marcar la casilla pasa el consejo a completado solo para esa persona (`consejos_usuario`). A los 7 días de `completada_en` se oculta de la lista de esa persona; no se borra. Si la persona lo desmarca antes, vuelve a pendiente.  
* **RN-XV-04 · Orden:** pendientes de mayor a menor prioridad (alta, media, baja) y completados al final. "Completado" no es una prioridad, es el estado individual.  
* **RN-XV-05 · Vigencia y generación:** un consejo pendiente se muestra durante su vigencia, 7 días contados desde `created_at` (decisión v4.5). Vencida la vigencia deja de mostrarse y la regla puede generar otro, para no repetir siempre los mismos. Mientras exista un consejo vigente de la misma regla (y zona, si aplica), no se crea otro.  
* **RN-XV-06 · Seguimiento por persona:** al crearse un consejo se crea una fila `pendiente` en `consejos_usuario` para cada miembro activo; un miembro que ingresa después no recibe consejos anteriores.  
* **RN-XV-07 · Catálogo inicial de reglas:** (1) una zona en estado elevado genera un consejo de esa zona con prioridad media; (2) una zona en estado crítico genera un consejo de esa zona con prioridad alta; (3) un cierre de mes por encima de la referencia del hogar (RN-XIV-07, v4.8) genera un consejo general (sin zona) con prioridad baja. Los textos de cada consejo, por tipo de zona, salen del catálogo de textos. **(v4.9, DC-24)** `regla_origen`: `zona_elevada`, `zona_critica`, `cierre_mes_encima`; `categoria`: `zona` o `general`. Cada regla y zona tiene dos variantes y el consejo nuevo usa la que no usó el anterior. Este catálogo es solo la base inicial: se pueden modificar y agregar reglas sin cambiar tablas.  
* **RN-XV-08 · Exclusiones:** el acceso a un chatbot queda para la Fase 2.

## **XVI. Configuración**

* **RN-XVI-01 · Estructura de la pantalla:** Cuenta (Editar perfil, Cambiar contraseña, Correo electrónico); Notificaciones (Alertas y Consejos); Energía y consumo (Meta de consumo, Establecer meta, Configurar tarifa, Fuentes de datos); Familia y acceso (Administrar miembros); Hogar y transición energética (Fase 2, "Próximamente"); Otros (Cerrar sesión); Zona de riesgo (Eliminar cuenta).  
* **RN-XVI-02 · Notificaciones:** el interruptor Alertas controla `notif_consumo` (alertas de consumo e información) y el de Consejos controla `notif_consejos`. El texto de Consejos es "Recibe recomendaciones de ahorro".  
* **RN-XVI-03 · Interruptor Meta de consumo:** es `base_comparacion` del usuario: encendido compara contra la meta y apagado contra el promedio histórico. No cambia la meta del hogar.  
* **RN-XVI-04 · Establecer meta:** la unidad es siempre kWh; la meta mensual debe ser mayor que 0; el promedio diario mostrado es la meta ÷ días del mes; se elige un tipo (ahorro, eficiencia, presupuesto) que solo cambia textos, incluido el cuerpo de la card «Acumulado de hoy» (v4.9, DC-10). Guardar una meta nueva deja la anterior en estado inactiva y cierra su `fecha_fin` con la `fecha_inicio` de la nueva (se conserva y no se muestra). Pueden modificarla el administrador y los miembros con `permiso_modificar_metas`; los demás la ven en solo lectura. Se muestra como referencia el consumo promedio de los últimos 30 días.  
* **RN-XVI-05 · Configurar tarifa:** operador (opcional, lista desplegable con la lista aprobada el 02/11/2026: Afinia, Air-e, CHEC, Celsia, Enel Colombia, EPM, ESSA y Otro operador, que vive en la app como archivo fijo; el texto elegido se guarda en `operador`), valor por kWh (obligatorio), vigente desde (mes y año, se guarda el día 1) y cargo fijo mensual (opcional: si se ingresa se suma al costo proyectado del mes, si no, no). Guardar crea una tarifa nueva y cierra la anterior con `vigente_hasta` igual al nuevo `vigente_desde` (fin excluido); el nuevo `vigente_desde` debe ser posterior al de la tarifa vigente. Solo el administrador la edita; los demás la ven en solo lectura. Guardar la tarifa no depende de los datos del hogar. La pantalla advierte que la estimación puede no incluir subsidios, contribuciones u otros cobros.  
* **RN-XVI-06 · Fuentes de datos:** pantalla de solo lectura, visible para todos los miembros; sin el permiso de ver consumo actual muestra nombres y estados, pero no los valores en kW (RN-XVII-01). Muestra la fuente principal y un sensor por zona con el consumo de la última hora completa (kW) y su estado: Activo, Pausado o Sin datos. Sin datos significa que al sensor no le llegó la lectura de la última hora completa; no es una columna guardada. La fuente principal muestra la suma de sus sensores. Los nombres son "Sensor [zona]" y "Fuente principal [nombre del hogar]".  
* **RN-XVI-07 · Miembros del hogar:** muestra el conteo de miembros activos, la lista (nombre, rol, estado), las invitaciones pendientes aparte (solo para el administrador), la sección "Permisos de los miembros" con los 4 permisos y el botón "Invitar miembro". Solo el administrador mueve los permisos y usa el menú de acciones de cada miembro (expulsar, transferir administración, cancelar invitación).

## **XVII. Permisos y Visibilidad**

* **RN-XVII-01 · Ver consumo actual:** controla el Panel principal, Zonas, Zona individual y los valores en kW de Fuentes de datos.  
* **RN-XVII-02 · Ver historial completo:** controla la pestaña Historial.  
* **RN-XVII-03 · Recibir alertas:** controla la entrega de alertas (regla XIV).  
* **RN-XVII-04 · Modificar metas:** controla la edición de la meta (regla XVI).  
* **RN-XVII-05 · Sin permiso:** se bloquean solo las cards de datos, que se reemplazan por un mensaje de falta de permiso; el encabezado de la pantalla y el saludo siguen disponibles. La campana de alertas se muestra según el permiso de recibir alertas (regla XII). El administrador conserva siempre el acceso total.

## **XVIII. Datos del Hogar y Transición Energética (Fase 2)**

* **RN-XVIII-01 · Alcance:** la pantalla Datos y transición, con Información del hogar y Perfil de transición, y la función Mi huella de carbono son de la Fase 2. En el MVP aparecen como "Próximamente" y esos campos quedan vacíos (salvo el tipo de vivienda, que se pide en el onboarding). Ratificado en la v4.9 (DC-01): la transición energética no entra en el MVP.  
* **RN-XVIII-02 · Información del hogar:** estrato (opciones de 1 a 6), tipo de vivienda (5 opciones), ciudad o municipio, número de personas (mínimo 1) y si trabajan o estudian desde casa. En la pantalla son obligatorios los cuatro primeros; en la base de datos son opcionales.  
* **RN-XVIII-03 · Perfil de transición:** área del techo (m²), factura promedio mensual, vehículo eléctrico (sí o no) y presupuesto estimado. Todos son opcionales. La fila de `perfil_transicion` se crea solo si el usuario llena algún campo de esa sección; sin fila significa que no se ha llenado.  
* **RN-XVIII-04 · Quién edita:** solo el administrador; los demás miembros lo ven en solo lectura.  
* **RN-XVIII-05 · Texto:** las descripciones hablan de "recomendaciones sobre energías renovables", no de personalización por IA.

## **XIX. Seguridad, Retención y Migraciones**

* **RN-XIX-01 · Retención:** las lecturas, alertas y consejos se conservan; ocultar una alerta o un consejo es solo de visualización por persona.  
* **RN-XIX-02 · Migraciones:** los cambios de esquema se aplican como migraciones numeradas en el repositorio.  
* **RN-XIX-03 · Roles técnicos:** el administrador técnico (gestión de usuarios, tarifas por defecto, métricas) no se modela en el MVP.

# **2. Fase 2: Futuras Posibles Implementaciones**

* **Adaptación para MiPyMEs:** Creación de versiones adaptadas para pequeñas y medianas empresas.  
* **Transición a energías renovables:** Integración de la información de la tabla `perfil_transicion` para recomendaciones sobre paneles solares, baterías de segunda vida y almacenamiento.  
* **Vehículos Eléctricos:** Funcionalidades específicas para monitorear y optimizar la carga de vehículos eléctricos.  
* **Integración de Hardware Físico:** Conexión con medidores inteligentes, sensores y enchufes reales (reemplazando el simulador).  
* **Machine Learning (Comportamiento del Usuario):** Implementar modelos para aprender a qué hora el usuario revisa la app y adaptar la entrega de alertas o generar consejos en momentos específicos.  
* **Reportes Avanzados:** Generación y descarga de informes ejecutivos en formato PDF o Excel.  
* **Chatbot:** acceso a un asistente conversacional (el ícono de destellos de la pantalla Consejos no se incluye en el MVP).  
* **Datos del hogar y transición energética:** pantalla Datos y transición (Información del hogar y Perfil de transición) y recomendaciones sobre energías renovables.  
* **Mi huella de carbono:** conocer el impacto ambiental del consumo.  
* **Navegación entre periodos del Historial:** flechas o calendario para ver periodos anteriores.  
* **Consejos accionables:** que un consejo lleve a la zona u otra pantalla relacionada.
* **Memoria e intensidad del ruido por zona:** permitir que `ruido_config` tenga valores propios de memoria (φ) e intensidad (σ) para cada zona, con un bloque `default` para las zonas sin valores propios (ver el ejemplo en la sección 5). En el MVP los dos valores son iguales para todas las zonas de la personalidad.

# **3. Diccionario de Datos (18 Tablas)**

A continuación, el detalle de las 18 tablas definidas (aún no creadas en Supabase), sus campos, tipos de datos, objetivos y relaciones. Convención: todas las tablas propias (todas menos `auth.users`) incluyen además `created_at` y `updated_at` (TIMESTAMPTZ); no se repiten en cada tabla. Las validaciones de los mockups no requirieron campos ni tablas adicionales a los indicados.

## **Módulo A: La Gente (Identidad y Accesos)**

### **1. auth.users (Supabase)**

Objetivo: Bóveda externa segura que guarda correos y contraseñas cifradas.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador maestro del usuario |
| `email` | TEXT | Unique | Correo de ingreso |
| `encrypted_password` | HASH | Not Null | Contraseña cifrada por seguridad |

### **2. usuarios**

**Objetivo:** Ficha de datos personales de la persona en la aplicación.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK, FK -> auth.users.id | Conecta con el ID maestro |
| `nombre_completo` | TEXT | Not Null | Nombre visible para los familiares |
| `telefono` | TEXT | Nullable | Celular opcional |
| `avatar_url` | TEXT | Nullable | Ruta de la foto de perfil en Supabase Storage |

### **3. preferencias_usuario**

**Objetivo:** Configuraciones individuales de interfaz y notificaciones para cada persona.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `usuario_id` | UUID | PK, FK -> usuarios.id | A quién pertenece el ajuste |
| `notif_consumo` | BOOLEAN | Default true | Interruptor para notificaciones de consumo |
| `notif_consejos` | BOOLEAN | Default true | Interruptor para notificaciones de consejos |
| `base_comparacion` | TEXT | Not Null, Check ('meta', 'promedio'), Default 'promedio' | Con qué se compara el consumo de esta persona |

## **Módulo B: La Casa (Hogar y Miembros)**

### **4. hogares**

**Objetivo:** Entidad central que representa la casa y agrupa sus configuraciones.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador del hogar |
| `nombre` | TEXT | Not Null | Nombre de la casa |
| `estrato` | SMALLINT | Nullable, Check 1 a 6 | Estrato socioeconómico (se completa en Fase 2) |
| `ciudad` | TEXT | Nullable | Ciudad o municipio (Fase 2) |
| `numero_personas` | INTEGER | Nullable, mayor o igual a 1 | Cantidad de habitantes (Fase 2) |
| `trabajo_estudio_casa` | BOOLEAN | Nullable | Si trabajan o estudian desde casa (Fase 2) |
| `tipo_vivienda` | TEXT | Not Null, Check Enum | Valida opciones (`apartamento`, `casa`, `apartaestudio`, `duplex`, `casa_campestre`); se pide en el onboarding |
| `perfil_simulacion_id` | UUID | Not Null, FK -> perfiles_simulacion.id | Personalidad asignada (v4.9: obligatoria, D-SQL-2) |
| `permiso_ver_consumo_actual` | BOOLEAN | Default true | Permiso por defecto |
| `permiso_ver_historial` | BOOLEAN | Default true | Permiso por defecto |
| `permiso_recibir_alertas` | BOOLEAN | Default true | Permiso por defecto |
| `permiso_modificar_metas` | BOOLEAN | Default false | Permiso por defecto |

### **5. perfil_transicion**

**Objetivo:** Datos opcionales del hogar para proyectos de energía limpia futuros.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador |
| `hogar_id` | UUID | FK UNIQUE -> hogares.id | Relación con el hogar |
| `area_techo_m2` | NUMERIC(8,2) | Nullable, mayor o igual a 0 | Metros cuadrados disponibles |
| `factura_promedio_cop` | NUMERIC(12,2) | Nullable | Gasto promedio mensual |
| `vehiculo_electrico` | BOOLEAN | Nullable | Indica si posee uno |
| `presupuesto_cop` | NUMERIC(14,2) | Nullable | Presupuesto estimado para inversión |

### **6. hogar_miembros**

**Objetivo:** Relaciona a las personas con su hogar y su rol.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador de la membresía |
| `hogar_id` | UUID | FK -> `hogares.id` | Casa vinculada |
| `usuario_id` | UUID | FK -> `usuarios.id`, Nullable, On Delete Set Null | Usuario vinculado; vacío solo en membresías inactivas de una cuenta eliminada (v4.9, D-SQL-1) |
| `rol` | TEXT | Check ('administrador', 'miembro') | Valida 'administrador' o 'miembro' |
| `estado` | TEXT | Check ('activo', 'inactivo') | Valida 'activo' o 'inactivo' |
| `fecha_ingreso` | TIMESTAMPTZ | Not Null | Desde cuándo pertenece al hogar |
| `fecha_salida` | TIMESTAMPTZ | Nullable | Cuándo salió o fue expulsado |

Restricción: índice único parcial que permite un solo administrador activo por hogar. (v4.9) Índice único parcial de una membresía activa por usuario (RN-II-01) y verificación: una membresía `activo` siempre tiene `usuario_id`.

### **7. invitaciones_hogar**

**Objetivo:** Gestiona enlaces temporales de invitación enviados por correo a familiares.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador de la invitación |
| `hogar_id` | UUID | FK -> hogares.id | Casa a la que se invita |
| `correo_invitado` | TEXT | Not Null | Destinatario |
| `invitado_por` | UUID | FK -> usuarios.id, Nullable, On Delete Set Null | Quién envía (vacío si esa cuenta se eliminó; v4.9, D-SQL-1) |
| `token_hash` | TEXT | Not Null, Unique | Enlace seguro |
| `estado` | TEXT | Check ('pendiente', 'aceptada', 'rechazada', 'expirada', 'revocada') | Situación de la invitación |
| `expira_en` | TIMESTAMPTZ | Not Null | Fecha de vencimiento (7 días) |
| `respondida_en` | TIMESTAMPTZ | Nullable | Fecha en que se aceptó o rechazó |

## **Módulo C: La Infraestructura Física**

### **8. zonas**

**Objetivo:** Espacios físicos de la casa predefinidos al registro.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador de la zona |
| `hogar_id` | UUID | FK -> `hogares.id` | Casa a la que pertenece |
| `nombre` | TEXT | Not Null | Nombre automático según el tipo; único dentro del hogar |
| `tipo` | TEXT | Check Enum | Valida opciones (`cocina`, `sala`, `dormitorio`, `bano`, `lavanderia`, `oficina`, `terraza`, `garaje`, `cuarto_servicio`) |
| `estado` | TEXT | Check ('activa', 'inactiva') | Valida 'activa' o 'inactiva' |

Restricción: nombre único dentro del hogar. El nombre se genera a partir del tipo.

### **9. fuentes_principales**

**Objetivo:** Medidor virtual general interno que agrupa sensores de la casa.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador del medidor |
| `hogar_id` | UUID | FK -> `hogares.id` | Casa a la que pertenece |
| `nombre` | TEXT | Not Null | Nombre del medidor |
| `estado` | TEXT | Check ('activa', 'inactiva') | Valida 'activa' o 'inactiva' |

Restricción: una sola fuente principal por hogar en el MVP (`hogar_id` único); todos los sensores del hogar se vinculan a ella.

### **10. sensores_zona**

**Objetivo:** Puntos de medición virtuales conectados a cada zona del hogar.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador del sensor |
| `zona_id` | UUID | FK UNIQUE -> `zonas.id` | Zona monitoreada |
| `fuente_principal_id` | UUID | FK -> `fuentes_principales.id` | Medidor asociado |
| `estado` | TEXT | Check ('activo', 'pausado') | Valida 'activo' o 'pausado' |

## **Módulo D: El Consumo**

### **11. lecturas**

**Objetivo:** Almacenamiento del consumo energético generado hora a hora en kilovatios.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador de la lectura |
| `sensor_id` | UUID | FK -> sensores_zona.id | Sensor que genera el dato |
| `fecha_hora` | TIMESTAMPTZ | Not Null | La hora exacta en Bogotá |
| `consumo_kwh` | NUMERIC(12,4) | Not Null, mayor o igual a 0 | Energía consumida en la hora |
| `calidad` | TEXT | Check ('simulada', 'estimada', 'real') | Valida 'simulada', 'estimada' o 'real' |

Restricción: única por (`sensor_id`, `fecha_hora`); una lectura por sensor y hora.

### **12. perfiles_simulacion**

**Objetivo:** Reglas matemáticas de comportamiento que utiliza el simulador para datos.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador de la personalidad |
| `nombre` | TEXT | Not Null, Unique | Nombre (ej. "Consumo eficiente") |
| `activo` | BOOLEAN | Default true | Estado del perfil |
| `base_cocina_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria de la cocina |
| `base_sala_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria de la sala |
| `base_dormitorio_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria del dormitorio |
| `base_bano_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria del baño |
| `base_lavanderia_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria de la lavandería |
| `base_oficina_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria de la oficina |
| `base_terraza_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria de la terraza |
| `base_garaje_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria del garaje |
| `base_cuarto_servicio_kwh_dia` | NUMERIC(10,4) | Not Null, mayor o igual a 0 | Base diaria del cuarto de servicio |
| `curva_horaria` | JSONB | Not Null | Curva base de 24 pesos y, opcionalmente, curvas propias por zona (ver estructura en la sección 5) |
| `humor_min` / `humor_max` | NUMERIC(6,4) | Not Null | Variación diaria |
| `ruido_config` | JSONB | Not Null | Variación estocástica: memoria (φ) e intensidad (σ), iguales para todas las zonas |
| `picos_config` | JSONB | Not Null | Probabilidad y parámetros de los eventos anormales, por zona |
| `factor_fin_semana` | NUMERIC(6,4) | Not Null, mayor que 0 | Multiplicador para fines de semana |

Restricción: se siembran 5 personalidades con los nombres exactos *Consumo compacto*, *Consumo eficiente*, *Consumo intermedio*, *Consumo familiar* y *Consumo amplio*. Si una zona no existe en el hogar, las columnas y curvas de esa zona se ignoran (RN-IV-07).

#### **Asignación de la personalidad (RN-X-04)**

**Variables**

| Variable | Qué es | Valores |
| :---- | :---- | :---- |
| B | Zonas básicas | `cocina`, `sala`, `dormitorio`, `bano` |
| Of, La | Zonas complementarias | `oficina`, `lavanderia` |
| Te, Ga, CS | Zonas extras | `terraza`, `garaje`, `cuarto_servicio` |
| c | Cantidad de zonas elegidas entre Of, La, Te y Ga | 0 a 4 |
| s | Si tiene cuarto de servicio | 1 si lo tiene, 0 si no |
| E | Cantidad de extras elegidas (Te, Ga, CS) | 0 a 3 |
| OL | Si tiene oficina o lavandería | Sí o no |

**Zonas permitidas por vivienda (RN-X-02)**

| Vivienda | Restricción de zonas |
| :---- | :---- |
| `apartaestudio` | Mínimo 3 básicas, máximo 5 zonas en total. Solo B, Of y La. Sin extras |
| `apartamento` | Las 4 básicas obligatorias, sin máximo |
| `casa` | Las 4 básicas obligatorias, sin máximo |
| `duplex` | Las 4 básicas obligatorias, sin máximo |
| `casa_campestre` | Las 4 básicas obligatorias, sin máximo |

**Condiciones de asignación**

Apartaestudio:

| Condición | Personalidad |
| :---- | :---- |
| 3 o 4 zonas | Consumo compacto |
| 5 zonas | Consumo eficiente |

Apartamento, casa y dúplex (se evalúan en orden; gana la primera que se cumpla):

| Orden | Condición | Personalidad |
| :---- | :---- | :---- |
| 1 | E ≥ 2 y OL | Consumo amplio |
| 2 | c ≥ 2 o s = 1 | Consumo familiar |
| 3 | c = 1 y s = 0 | Consumo intermedio |
| 4 | c = 0 y s = 0 | Consumo eficiente |

Casa campestre: se calcula igual que una casa y se sube un nivel, con tope en amplio.

| Resultado como casa | Resultado en casa campestre |
| :---- | :---- |
| Consumo eficiente | Consumo intermedio |
| Consumo intermedio | Consumo familiar |
| Consumo familiar | Consumo amplio |
| Consumo amplio | Consumo amplio |

**Ejemplos de comprobación**

| Vivienda | Zonas | Personalidad |
| :---- | :---- | :---- |
| Apartaestudio | Sala, cocina, dormitorio, baño | Consumo compacto |
| Apartaestudio | 4 básicas + lavandería | Consumo eficiente |
| Apartamento | 4 básicas | Consumo eficiente |
| Apartamento | 4 básicas + oficina | Consumo intermedio |
| Apartamento | 4 básicas + terraza | Consumo intermedio |
| Apartamento | 4 básicas + oficina + lavandería | Consumo familiar |
| Apartamento | 4 básicas + terraza + garaje | Consumo familiar |
| Apartamento | 4 básicas + lavandería + terraza + garaje | Consumo amplio |
| Casa | 4 básicas + cuarto de servicio | Consumo familiar |
| Dúplex | Las 9 zonas | Consumo amplio |
| Casa campestre | 4 básicas | Consumo intermedio |
| Casa campestre | 4 básicas + terraza | Consumo familiar |
| Casa campestre | 4 básicas + oficina + terraza | Consumo amplio |

#### **Las 5 personalidades**

Cada personalidad describe un tipo de hogar y un tipo de consumo. Los valores exactos (bases, curvas, ruido y picos) se definen dentro de un rango coherente con esa descripción y se ajustan en la calibración (sección 8). El objetivo de consumo mensual de un hogar con todas las zonas que contempla su personalidad debe respetar el orden: compacto < eficiente < intermedio < familiar < amplio.

| Personalidad | Quién la recibe | Hogar de referencia | Tipo de consumo |
| :---- | :---- | :---- | :---- |
| Consumo compacto | Apartaestudio de 3 o 4 zonas | Una o dos personas que pasan el día fuera, llegan en la noche, cocinan poco en casa y usan pocos equipos (un TV, un portátil, nevera pequeña). | Consumo bajo, concentrado en la noche y en la mañana temprano. Pocos picos y de baja potencia. Pesan sobre todo el dormitorio y la sala. |
| Consumo eficiente | Hogares con solo las zonas básicas (apartamento, casa, dúplex) o apartaestudio de 5 zonas | Dos personas que trabajan presencial, llegan tarde en la noche, cocinan en casa, tienen visitas ocasionales y pocos electrodomésticos de consumo fuerte (un TV, dos computadores). | Consumo moderado-bajo con doble pico, en la mañana y en la noche. La cocina es la zona de mayor peso. Ruido bajo y picos ocasionales. |
| Consumo intermedio | Hogares con las básicas y una zona adicional (oficina, lavandería, terraza o garaje); casa campestre con solo las básicas | Hogar con una persona que trabaja o estudia parte del tiempo en casa, o con lavadora propia, por lo que hay presencia y consumo durante el día. | Consumo medio con más actividad diurna en la zona adicional. Picos ocasionales de potencia media. |
| Consumo familiar | Hogares con dos o más zonas adicionales (oficina, lavandería, terraza o garaje) o con cuarto de servicio, sin llegar a amplio; casa campestre con una sola zona adicional | Familia de cuatro o más personas, con alguien en casa durante el día, uso frecuente de lavadora y cocina, y más equipos encendidos a la vez. | Consumo alto y sostenido durante el día, con picos en la mañana, la tarde y la noche. Picos más frecuentes. |
| Consumo amplio | Apartamento, casa o dúplex con dos o más extras y oficina o lavandería; casa campestre con dos o más zonas adicionales o con cuarto de servicio | Vivienda grande con varias zonas exteriores y de servicio, equipos de alto consumo (bombas, iluminación exterior, plancha, lavadora), visitas frecuentes y fines de semana de alta ocupación. | Consumo más alto, con mayor variación entre días y picos más potentes. El fin de semana se nota con claridad. |

Los horarios por zona se arman con unas pocas formas reutilizables (diurna, doble pico, nocturna y plana). Por ejemplo, el dormitorio usa una forma nocturna en todas las personalidades, la oficina una diurna y la cocina una de doble pico en las comidas.

**Nota (v4.4).** En los datos cerrados (acta 04), la cocina de *Consumo compacto* concentra cerca del 67 % del consumo, por la nevera documentada en el hogar de referencia C1. La descripción de esta tabla se conserva como intención de diseño; la diferencia está aceptada como limitación en el acta 04.


## **Módulo E: Dinero y Metas**

### **13. tarifas_hogar**

**Objetivo:** Historial de precios del kilovatio y cargos fijos en pesos.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador de la tarifa |
| `hogar_id` | UUID | FK -> hogares.id | Casa asociada |
| `operador` | TEXT | Nullable | Empresa prestadora |
| `precio_kwh` | NUMERIC(12,2) | Not Null, mayor o igual a 0 | Precio en COP por kWh |
| `cargo_fijo_mensual` | NUMERIC(12,2) | Nullable, mayor o igual a 0 | Cargo fijo en COP (opcional) |
| `vigente_desde` | DATE | Not Null | Fecha de inicio |
| `vigente_hasta` | DATE | Nullable | Fin de la vigencia (excluido); nulo = tarifa vigente |

Restricción: al guardar una tarifa nueva, la anterior se cierra con `vigente_hasta` igual al nuevo `vigente_desde` (intervalo [desde, hasta), con el fin excluido). Las vigencias de un hogar no se solapan y solo hay una vigencia abierta.

### **14. metas_consumo**

**Objetivo:** Objetivo o límite mensual de energía activo para el hogar.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador de la meta |
| `hogar_id` | UUID | FK -> `hogares.id` | Casa asociada |
| `tipo` | TEXT | Check ('ahorro', 'eficiencia', 'presupuesto') | Valida 'ahorro', 'eficiencia', o 'presupuesto' |
| `valor_kwh_mensual` | NUMERIC | Not Null, mayor que 0 | Límite mensual en kWh |
| `estado` | TEXT | Check ('activa', 'inactiva') | Valida 'activa' o 'inactiva' |
| `fecha_inicio` | DATE | Not Null | Desde cuándo rige la meta |
| `fecha_fin` | DATE | Nullable | Fin de la meta (excluido); nulo = meta vigente |

Restricción: índice único parcial que permite una sola meta activa por hogar. Al guardar una meta nueva, la anterior pasa a `inactiva` (se conserva) y su `fecha_fin` es la `fecha_inicio` de la nueva (intervalo [inicio, fin), con el fin excluido).

## **Módulo F: Avisos y Sugerencias**

### **15. alertas**

**Objetivo:** Eventos y avisos de consumo generados a nivel de hogar.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador de la alerta |
| `hogar_id` | UUID | FK -> hogares.id | Casa asociada |
| `categoria` | TEXT | Check ('consumo', 'consejo', 'informacion') | Valida 'consumo', 'consejo', o 'informacion' |
| `severidad` | TEXT | Check ('informativa', 'advertencia', 'critica') | Valida 'informativa', 'advertencia', o 'critica' |
| `titulo` / `mensaje` | TEXT | Not Null | Contenido de la alerta |
| `zona_id` | UUID | FK -> zonas.id (Nullable) | Zona específica si aplica |
| `regla_origen` | TEXT | Not Null | Regla que generó la alerta |
| `clave_evento` | TEXT | Not Null, Unique | Control interno para evitar duplicados |

### **16. alertas_usuario**

**Objetivo:** Registra la fecha exacta en que una persona leyó alertas (seguimiento individual).

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `alerta_id` | UUID | PK, FK -> `alertas.id` | Alerta vinculada |
| `usuario_id` | UUID | PK, FK -> `usuarios.id` | Usuario vinculado |
| `leida_en` | TIMESTAMPTZ | Nullable | Fecha de lectura |

### **17. consejos**

**Objetivo:** Recomendaciones prácticas de ahorro generadas a nivel de todo hogar.

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador del consejo |
| `hogar_id` | UUID | FK -> hogares.id | Casa asociada |
| `categoria` | TEXT | Not Null, Check ('zona', 'general') | Categoría (v4.9, DC-24) |
| `prioridad` | TEXT | Check ('baja', 'media', 'alta') | Valida 'baja', 'media', 'alta' |
| `zona_id` | UUID | FK -> zonas.id (Nullable) | Zona si aplica |
| `titulo` / `descripcion` | TEXT | Not Null | Textos de ayuda |
| `regla_origen` | TEXT | Not Null | Origen |

### **18. consejos_usuario**

**Objetivo:** Registra si una persona específica ya aplicó una recomendación dada (seguimiento individual).

| Campo | Tipo | Restricciones / Relación | Descripción |
| :---- | :---- | :---- | :---- |
| `id` | UUID | PK | Identificador |
| `consejo_id` | UUID | FK -> `consejos.id` | Consejo vinculado |
| `usuario_id` | UUID | FK -> `usuarios.id` | Usuario vinculado |
| `estado` | TEXT | Check ('pendiente', 'completada') | Valida 'pendiente' o 'completada' |
| `completada_en` | TIMESTAMPTZ | Nullable | Fecha de cumplimiento |

Restricción: única por (`consejo_id`, `usuario_id`). Al crearse un consejo se crea una fila `pendiente` por cada miembro activo del hogar; al desmarcarlo, `completada_en` vuelve a quedar vacío. Validación: `pendiente` exige `completada_en` vacío y `completada` exige `completada_en` con fecha.

## **Cardenalidades y Relaciones**

* `auth.users` **(1:1)** `usuarios`  
* `usuarios` **(1:1)** `preferencias_usuario`  
* `usuarios` **(1:N)** `hogar_miembros` **(N:1)** `hogares` (Relación M:N resuelta por la tabla intermedia)  
* `hogares` **(1:N)** `invitaciones_hogar`  
* `usuarios` **(1:N)** `invitaciones_hogar` (Como remitente: `invitado_por`)  
* `perfiles_simulacion` **(1:N)** `hogares`  
* `hogares` **(1:0..1)** `perfil_transicion`  
* `hogares` **(1:N)** `zonas`  
* `hogares` **(1:N)** `fuentes_principales`  
* `zonas` **(1:0..1)** `sensores_zona` **(N:1)** `fuentes_principales` (Un sensor enlaza una zona a una fuente)  
* `sensores_zona` **(1:N)** `lecturas`  
* `hogares` **(1:N)** `tarifas_hogar`  
* `hogares` **(1:N)** `metas_consumo`  
* `hogares` **(1:N)** `alertas`  
* `zonas` **(0..1:N)** `alertas` (Una alerta puede apuntar a una zona específica o a toda la casa)  
* `alertas` **(1:N)** `alertas_usuario` **(N:1)** `usuarios` (Relación M:N para lectura individual)  
* `hogares` **(1:N)** `consejos`  
* `zonas` **(0..1:N)** `consejos`  
* `consejos` **(1:N)** `consejos_usuario` **(N:1)** `usuarios` (Relación M:N para completado individual)

## **Resumen de cambios frente al diccionario v3.1**

| Tabla | Cambio |
| :---- | :---- |
| `hogares` | Se agrega `trabajo_estudio_casa` (opcional); `tipo_vivienda` es obligatorio, se pide en el onboarding y tiene 5 opciones (`apartamento`, `casa`, `apartaestudio`, `duplex`, `casa_campestre`); estrato, ciudad y número de personas quedan opcionales (Fase 2). |
| `preferencias_usuario` | `base_comparacion` es obligatorio con valor por defecto `promedio`. |
| `hogar_miembros` | Estado `activo` / `inactivo`; se agregan `fecha_ingreso` y `fecha_salida`; un administrador activo por hogar y una membresía activa por usuario. |
| `invitaciones_hogar` | Estados `pendiente`, `aceptada`, `rechazada`, `expirada`, `revocada`; se agrega `respondida_en`. |
| `zonas` | Nombre automático según el tipo, único por hogar; el catálogo incluye lavandería y pasa a 9 tipos (se agregan `terraza`, `garaje` y `cuarto_servicio`). |
| `lecturas` | Única por (`sensor_id`, `fecha_hora`); consumo mayor o igual a 0. |
| `perfiles_simulacion` | Una columna de base por tipo de zona (9, incluidas terraza, garaje y cuarto de servicio); humor por hogar y día; `curva_horaria` con curva base y curvas propias por zona; ruido de memoria de primer orden por zona y día (`ruido_config` con φ y σ comunes a todas las zonas); picos por zona y hora (`picos_config`). |
| `tarifas_hogar` | Una tarifa nueva cierra la anterior (`vigente_hasta` = nuevo desde, fin excluido); el cargo fijo es opcional. |
| `metas_consumo` | Una sola meta activa; la anterior pasa a inactiva y se conserva; se agregan `fecha_inicio` y `fecha_fin`. |
| `consejos_usuario` | Única por (`consejo_id`, `usuario_id`); se crea una fila por miembro activo; el estado se valida contra `completada_en`. |
| `alertas` | `clave_evento` única. |
| `fuentes_principales` | Una sola fuente principal por hogar. |
| Todas las propias | Se agregan `created_at` y `updated_at`. |

No se agregan tablas nuevas: el modelo sigue en 18 tablas (`auth.users` y 17 propias).

## **Integridad, seguridad y almacenamiento (v4.9)**

Cierra D-SQL-1 a D-SQL-5 (registro DC-36 a DC-45). No agrega columnas.

| Tema | Definición |
| :---- | :---- |
| Borrado de cuenta (D-SQL-1) | `usuarios` y `preferencias_usuario` se borran en cascada desde `auth.users`; `alertas_usuario` y `consejos_usuario` del usuario, en cascada; `hogar_miembros.usuario_id` e `invitaciones_hogar.invitado_por` pasan a nulo. Si era el único miembro, el backend elimina el hogar y sus datos en la misma operación (RN-IX-09). |
| Personalidad (D-SQL-2) | `hogares.perfil_simulacion_id` obligatorio. |
| Sensor y zona del mismo hogar (D-SQL-3) | Lo garantiza la transacción de RN-X-03; una consulta de integridad lo comprueba en las pruebas. Sin columna nueva. |
| Coherencia (D-SQL-4) | `vigente_hasta > vigente_desde`; tarifas de un hogar sin solapamiento (exclusión con `btree_gist`); `fecha_fin > fecha_inicio`; `pendiente` ↔ `completada_en` vacío; `updated_at` automático. |
| RLS (D-SQL-5) | Activa en las 17 tablas propias. Lectura solo con membresía activa en el hogar y el permiso de la pantalla (RN-XVII); cada usuario lee solo sus filas de `alertas_usuario`, `consejos_usuario` y `preferencias_usuario`. La app no escribe tablas: escribe el backend con conexión de servicio, que comprueba membresía, rol y permiso en cada llamada (RN-I-03). `perfiles_simulacion` sin acceso para clientes. |
| Únicos e índices | Membresía activa por usuario; administrador activo por hogar; meta activa por hogar; una tarifa abierta por hogar; una invitación pendiente por hogar y correo (en minúsculas); lectura por sensor y hora; `clave_evento`; índices por hogar y fecha en `alertas` y `consejos`, y por usuario en `alertas_usuario` y `consejos_usuario`. |
| Storage | Bucket privado `avatares` (RN-I-02, DC-43). |
| Migraciones | Supabase CLI, `supabase/migrations/` numeradas (RN-XIX-02). Semilla de `perfiles_simulacion` desde `consolidado_perfiles_simulacion.json` con verificación de su SHA-256 (sección 8.1). |

La especificación completa para crear el proyecto está en `02_base-de-datos/especificacion-supabase-v1.md`.


# **4. Ejemplo Práctico: El Recorrido de Andrés**

Todo inicia cuando **Andrés** descarga Zentheris. Él se registra, y su correo y contraseña se guardan en la caja fuerte externa de auth.users. Al instante, el sistema crea su ficha personal en usuarios (donde él decide subir una foto que se guarda en Supabase Storage, y la URL va al campo avatar_url). También se crea su configuración por defecto en preferencias_usuario (notificaciones activas).

Andrés crea su casa ("Apto 502", de tipo apartamento), lo que genera un registro en `hogares`. Automáticamente, la tabla hogar_miembros lo nombra "Administrador". Durante este proceso (onboarding), la app le exige las 4 zonas básicas (cocina, sala, dormitorio y baño) y él agrega además la lavandería. En ese segundo, se crean 5 registros fijos en zonas. De forma invisible para Andrés, el sistema le asigna un medidor general en `fuentes_principales` y conecta 5 `sensores_zona` (uno para cada zona).

Luego, la casa de Andrés necesita una personalidad. El sistema no la sortea: la calcula con su tipo de vivienda y sus zonas. Como es un apartamento con las 4 básicas y una sola zona adicional (lavandería), se le asigna el perfil de simulación "Consumo intermedio" (`perfiles_simulacion`). Con esas reglas matemáticas, la app muestra una pantalla de carga ("Preparando y analizando tu hogar...") mientras el sistema viaja 30 días al pasado y llena la tabla de lecturas hora por hora (720 horas × 5 zonas = 3.600 registros) (el Backfill). Cuando Andrés por fin ve el panel principal, las gráficas ya tienen información histórica.

Más adelante, Andrés pone el precio de su recibo en `tarifas_hogar` y un límite de ahorro mensual en metas_consumo. Envía una invitación por correo a su esposa mediante invitaciones_hogar. Cuando ella acepta, ingresa como miembro en hogar_miembros.

A partir de ahí, el simulador inyecta lecturas cada hora. Si el motor de reglas detecta que la cocina consumió el doble, crea un evento en `alertas` ("Consumo crítico en la cocina") y una sugerencia en consejos. Ambos reciben el aviso, pero la tabla alertas_usuario registra individualmente quién ya la leyó: si la esposa la lee en su celular, a Andrés le sigue apareciendo pendiente hasta que él mismo la revise.

# **5. Modelo Matemático de Simulación de Consumo**

### **Estado del modelo**

Esta fórmula es la definición final de la estructura del simulador del MVP. Los valores de cada personalidad (bases, curvas, rangos y probabilidades) están cerrados en los conjuntos v1.0 del 29/10/2026, aprobados en el acta 04 con sus códigos SHA-256 (sección 8.1). Cualquier cambio exige regenerarlos, repetir las pruebas y emitir una nueva acta; no modifica la fórmula ni las tablas.  
El modelo cumple las reglas del MVP:

* Genera los 30 días (720 horas) de historial retroactivo al terminar el onboarding, con los parámetros exactos de la personalidad asignada, incluyendo su ruido y su probabilidad de picos.  
* No usa IA ni Machine Learning predictivo; funciona solo con reglas matemáticas y umbrales.  
* Cada consumo representa una hora completa, por lo que su valor en kWh equivale a la potencia promedio en kW de esa hora.
* Genera lecturas solo para las zonas que el hogar eligió; el consumo de una zona que el hogar no tiene no se genera ni se reparte (RN-IV-07).

---

## **Parte 1: Sección técnica**

#### **Notación**

* **z:** Zona del hogar. Solo participan las zonas que el hogar eligió (`Z_h`), de los 9 tipos: cocina, sala, dormitorio, bano, lavanderia, oficina, terraza, garaje y cuarto_servicio  
* **w_z:** Curva horaria de la zona z (24 pesos que suman 1)  
* **n_z(t):** Ruido de la zona z en la hora t
* **d:** Día simulado  
* **t:** Hora del día, en hora de Bogotá (de 0 a 23)  
* **p:** Personalidad asignada al hogar (`perfil_simulacion_id`)  
* **L:** Consumo final simulado, en kWh

#### **Ecuación principal**

El consumo de cada zona, día y hora es:  
**L = (T × Q) + (Suma de eventos E)**  
Donde (T × Q) es el consumo regular y E es la energía aportada por eventos de sobreconsumo. Cada zona del hogar se calcula por separado. El consumo total del hogar en una hora es la suma de sus zonas (no se guarda como lectura extra, ver RN-XI-05); si el hogar tiene menos zonas que las que contempla su personalidad, el total es menor y no se reparte.

#### **Objetivo diario**

**T = B × H × F**

* **B:** consumo diario base de la zona, en kWh/día. Sale de la columna `base_<tipo>_kwh_dia` del tipo de zona (una columna por tipo, 9 en total).  
* **H:** humor del día. Se sortea una vez por día para todo el hogar (el mismo H para todas sus zonas), con distribución uniforme entre `humor_min` y `humor_max`.  
* **F:** factor de calendario. Es igual a `factor_fin_semana` si el día es sábado o domingo, de lo contrario es 1.

El valor T es el total de kWh regulares que la zona debe consumir ese día, sin contar eventos.

#### **Peso de cada hora**

La personalidad define para cada zona una curva horaria (w_z), con 24 valores no negativos que suman 1. En `curva_horaria` se guarda una curva base y, de forma opcional, curvas propias para las zonas que se comportan distinto (por ejemplo, un dormitorio nocturno o una oficina diurna). Si una zona no tiene curva propia, usa la base.  
Para evitar que cada hora varíe sin relación con la anterior, se genera un ruido con memoria de primer orden, de forma independiente para cada zona y cada día.

* Memoria del ruido (φ): Un valor cercano a 0 produce horas casi independientes, y uno cercano a 1 produce cambios muy suaves.  
* Intensidad de la variación (σ): tamaño máximo del empujón aleatorio nuevo de cada hora.  
* Ambos parámetros viven en `ruido_config` y son los mismos para todas las zonas de la personalidad. La memoria y la intensidad propias de cada zona quedan como posible implementación futura (sección 2).  
* Fórmula del ruido de cada hora: **n_z(t) = φ · n_z(t−1) + σ · ε**, donde ε es un número sorteado uniforme entre −1 y 1. Se sortea un ε distinto por zona, día y hora; cada hora conserva una fracción φ del ruido de la hora anterior y suma un empujón nuevo.  
* Cada día y cada zona empiezan con ruido 0 a las 00:00 y la memoria solo actúa dentro del mismo día. Así cada día se puede generar por separado y, con la misma semilla, da siempre el mismo resultado.

El peso con ruido es **w'_z(t) = máx(0, w_z(t) · (1 + n_z(t)))**, así nunca es negativo. Después se renormaliza, **Q_z(t) = w'_z(t) / Σ w'_z**, para que las 24 horas de la zona vuelvan a sumar 1 (peso Q).  
Por esta propiedad, la suma de las 24 horas regulares de cada zona es exactamente T.

#### **Eventos de sobreconsumo**

Los parámetros están en `picos_config`. En cada hora y zona:

* 1. Se sortea si ocurre un evento según la probabilidad de pico.  
* 2. Si ocurre, se sortean la potencia P (en W), la duración D (en minutos) y el minuto de inicio dentro de rangos definidos en la personalidad.  
* 3. La energía total del evento E es: P × (D/60) × (fracción de uso) / 1000.  
* 4. La energía se reparte entre las horas que el evento cubre, en proporción a los minutos de solapamiento. Así, un evento que cruza el cambio de hora aporta energía a ambas horas. Si la parte restante cae fuera del rango generado (después de la última hora del backfill), esa parte se descarta; en la generación hora a hora, el sobrante se suma a la lectura de la hora siguiente cuando esta se genera.

#### **Valor registrado**

Cada consumo final (L) se guarda como una fila de `lecturas`, en `consumo_kwh`, para el sensor de la zona y con `calidad = 'simulada'`. El historial no puede ser editado ni alimentado manualmente por el usuario.

#### **Reproducibilidad**

Los sorteos usan un generador de números pseudoaleatorios con semilla:  
**semilla = SHA-256(hogar_id, fecha, versión del modelo)**  
Con el mismo hogar, fecha y versión se obtienen los mismos datos, lo que permite comprobar el simulador en pruebas. La semilla no requiere campos nuevos, porque puede calcularse en el código. Los sorteos de cada zona se derivan de esa semilla combinada con el tipo de zona, de modo que cada zona tiene su propia secuencia. El algoritmo es SHA-256 y cada sorteo combina hogar, fecha, versión del modelo, tipo de zona y dominio del sorteo (convención A14 del Avance 03, aceptada en el acta 04).

#### **Correspondencia con las tablas**

* **B (Consumo base):** campos `base_<tipo>_kwh_dia` (una columna por tipo de zona, 9 en total) en `perfiles_simulacion`  
* **w_z (Curva por zona):** campo `curva_horaria` en `perfiles_simulacion` (curva base y curvas propias por zona)  
* **H (Humor):** campos `humor_min` y `humor_max` en `perfiles_simulacion`  
* **F (Calendario):** campo `factor_fin_semana` en `perfiles_simulacion`  
* **Parámetros de ruido (φ y σ):** campo `ruido_config` en `perfiles_simulacion`, comunes a todas las zonas  
* **Parámetros de picos:** campo `picos_config` en `perfiles_simulacion`


Los cambios de la v4.3 en la estructura de las tablas son solo las 3 columnas de base nuevas y los catálogos de vivienda y zonas. Los campos JSON mantienen su nombre y cambian su contenido, que se estructura así.

#### **Estructura de los campos JSON (ejemplo)**

Los valores son ilustrativos: sirven para fijar la forma de los datos, no son los valores calibrados. Los valores oficiales están en los archivos aprobados en el acta 04 (sección 8.1). Las claves de zona coinciden con los valores de `zonas.tipo`: `cocina`, `sala`, `dormitorio`, `bano`, `lavanderia`, `oficina`, `terraza`, `garaje` y `cuarto_servicio`.

**`curva_horaria`:** una curva base y, de forma opcional, curvas propias por zona. Cada curva tiene 24 valores (horas 0 a 23).

```json
{
  "base": [0.01,0.01,0.01,0.01,0.01,0.02,0.04,0.06,0.04,0.03,0.03,0.04,
           0.06,0.05,0.04,0.03,0.03,0.04,0.07,0.10,0.10,0.09,0.04,0.04],
  "dormitorio": [0.05,0.05,0.05,0.05,0.05,0.05,0.06,0.04,0.02,0.01,0.01,0.01,
                 0.01,0.01,0.01,0.01,0.01,0.01,0.02,0.04,0.07,0.10,0.14,0.12]
}
```

**`ruido_config`:** dos valores para toda la personalidad. `memoria` es φ e `intensidad` es σ.

```json
{
  "memoria": 0.6,
  "intensidad": 0.05
}
```

**`picos_config`:** parámetros de los eventos de sobreconsumo por zona. Una zona sin entrada no genera eventos. `probabilidad` es la probabilidad por hora; `franjas` multiplica esa probabilidad en rangos de horas; `potencia_w`, `duracion_min`, `minuto_inicio` y `fraccion_uso` son rangos [mínimo, máximo] de los que se sortea cada evento.

```json
{
  "cocina": {
    "probabilidad": 0.02,
    "franjas": [ { "desde": 18, "hasta": 21, "multiplicador": 2.0 } ],
    "potencia_w": [1000, 1800],
    "duracion_min": [10, 30],
    "minuto_inicio": [0, 59],
    "fraccion_uso": [0.5, 0.9]
  },
  "lavanderia": {
    "probabilidad": 0.01,
    "franjas": [],
    "potencia_w": [500, 2000],
    "duracion_min": [30, 90],
    "minuto_inicio": [0, 59],
    "fraccion_uso": [0.6, 1.0]
  }
}
```

**Reglas de coherencia**

* Toda curva tiene exactamente 24 valores mayores o iguales a 0 que suman 1.  
* Una zona sin curva propia usa `base`; `base` es obligatoria.  
* Las claves de zona de `curva_horaria` y `picos_config` solo pueden ser tipos del catálogo de zonas.  
* `memoria` está entre 0 y 1 (sin incluir 1) e `intensidad` es mayor o igual a 0.  
* En cada rango, el mínimo es menor o igual al máximo.  

**Decisión actual y opción futura.** En el MVP, `ruido_config` tiene solo dos valores por personalidad (los de arriba): la diferencia de comportamiento entre zonas ya sale de su curva, su base y sus picos, y con 5 personalidades solo hay 10 valores que calibrar. Como posible implementación futura (sección 2), `ruido_config` podría tener memoria e intensidad propias por zona, con un bloque `default` para las zonas que no tengan valores propios:

```json
{
  "default":    { "memoria": 0.6, "intensidad": 0.05 },
  "cocina":     { "memoria": 0.4, "intensidad": 0.10 },
  "dormitorio": { "memoria": 0.8, "intensidad": 0.03 }
}
```

Esta opción da más realismo por zona, pero aumenta el trabajo de calibración (hasta 20 valores por personalidad con 9 zonas) y la validación (el bloque `default` y las claves de zona).


#### **Condiciones de validez**

* 1. Todo valor de consumo debe ser mayor o igual a 0.  
* 2. Los 24 valores de los pesos por hora (Q) deben sumar 1 para cada zona y día.  
* 3. La suma regular de un día debe ser igual a T.  
* 4. Todo pico debe corresponder a un evento sorteado.  
* 5. Con la misma semilla, el resultado debe ser idéntico.  
* 6. El promedio mensual de un hogar que tiene todas las zonas que contempla su personalidad debe quedar cerca del objetivo de esa personalidad. Si el hogar tiene menos zonas, su promedio es menor por diseño (no se reparte el consumo faltante). Los objetivos deben respetar el orden compacto < eficiente < intermedio < familiar < amplio. Como referencia, el consumo mensual medio por usuario urbano en Bogotá fue de 132,14 kWh en estrato 3 y 135,69 kWh en estrato 4 durante 2024.

---

## **Parte 2: Explicación sencilla**

**La idea general**  
Imagina que para cada zona y cada día el simulador responde tres preguntas en orden:

* 1. ¿Cuánta energía gasta esta zona hoy?  
* 2. ¿Cómo se reparte esa energía entre las 24 horas?  
* 3. ¿Pasó algo especial, como encender un aparato potente?

Con las respuestas arma un número para cada hora, y ese número es la lectura que ve el usuario.  
**Qué hace cada pieza**

* **Base de la zona:** Es el gasto normal de un día en esa zona. La cocina gasta más que un dormitorio. Aparece siempre y fija el tamaño del consumo.  
* **Humor del día:** Es un número que se sortea una vez al día para todo el hogar. Si sale 1,10, ese día el hogar estuvo un 10% más activo; si sale 0,90, estuvo más tranquilo. Evita que todos los días sean iguales.  
* **Factor de fin de semana:** Es un empujón extra que se aplica solo sábado y domingo, porque la gente suele pasar más tiempo en casa. Entre semana vale 1 y no cambia nada. Cada personalidad tiene el suyo, así que un hogar que sale los fines de semana puede tener un valor menor que 1.  
* **Objetivo del día:** Es el resultado de multiplicar esas tres piezas. Responde la primera pregunta con un total en kWh. Por ejemplo, 1,8 x 1,10 x 1,15 = 2,277 kWh para la cocina un sábado.  
* **Curva de horas y pesos:** La curva dice qué parte del día le toca a cada hora. A las 3:00 AM le toca muy poco, y a las 7:00 PM le toca bastante. Es como cortar el objetivo del día en 24 porciones de distinto tamaño. Cada zona tiene su propio horario: el dormitorio puede concentrar su consumo en la noche, la oficina en las horas de trabajo y la cocina en las comidas. Si una zona no tiene horario propio, usa el general de la personalidad.  
* **Ruido con memoria:** Un día real nunca sigue la curva al pie de la letra. Cada hora se mueve un poco, pero no de manera brusca: si a las 6 PM la cocina estuvo algo más activa, a las 7 PM todavía queda algo de esa actividad. El ruido de cada hora tiene dos partes: una fracción del ruido de la hora anterior (la memoria) y un empujón nuevo y aleatorio (la intensidad). Cada zona tiene su propio ruido, pero todas usan la misma memoria e intensidad de la personalidad. Así las gráficas se ven naturales y no como dientes de sierra.  
* **Zonas que el hogar no tiene:** Si la personalidad contempla una zona que el hogar no eligió (por ejemplo, una oficina), esa zona simplemente no consume y su parte no se reparte entre las demás. Por eso un hogar con menos zonas gasta menos en total.  
* **Renormalización:** Después de mover las porciones con el ruido, estas pueden sumar un poco más o menos que el 100% del día. El simulador las vuelve a ajustar para que sumen exactamente 100%. La forma del día se conserva y el total del día vuelve a ser el objetivo.  
* **Eventos:** Cada hora hay una pequeña probabilidad de que ocurra algo especial, como encender una freidora de aire. Si ocurre, el simulador calcula su energía con la potencia del equipo, cuánto tiempo estuvo encendido y qué fracción de ese tiempo trabajó a máxima potencia. Esa energía se suma al consumo normal, y si el evento cruza el cambio de hora, se reparte entre las dos horas.  
* **Semilla:** Es la forma de que los números aleatorios no cambien cada vez que se ejecuta el simulador. Con la misma semilla, el mismo hogar produce los mismos datos, lo que permite comprobar que el código funciona.

**Cómo se junta todo (Ejemplo)**  
Un sábado a las 19:00 en la cocina del ejemplo:

* 1. Objetivo del día: 2,277 kWh.  
* 2. Peso de las 19:00 después del ruido y la renormalización: aproximadamente 0,093.  
* 3. Consumo regular: 2,277 x 0,093 = 0,21 kWh.  
* 4. Se enciende la freidora de 1.200 W durante 20 minutos con factor de uso 0,7, y aporta 0,28 kWh.  
* 5. Lectura final de esa hora: 0,21 + 0,28 = 0,49 kWh.

Sin la freidora, la lectura habría sido 0,21 kWh. El valor 0,49 es un pico con causa conocida, y sirve para probar alertas como "Consumo crítico en la cocina".  
**Para qué sirve el resultado**

* **Historial de 30 días:** el usuario ve gráficas con datos desde el primer momento.  
* **Alertas y consejos:** se disparan con reglas y umbrales sobre estas lecturas, sin IA.  
* **Comparaciones:** "hoy gastaste menos que ayer" tiene sentido porque los días varían, pero con coherencia.  
* **Pruebas:** al ser reproducible, puedes verificar que el simulador sea correcto.  
* **Hardware futuro:** cuando existan medidores reales, el campo calidad ya distingue las lecturas simuladas de las reales.

# **6. Pantallas de la App (validadas con mockups)**

Cada pantalla indica sus elementos, qué contienen, a qué responden y un ejemplo breve. Los ejemplos son ilustrativos. Los cambios que cada pantalla necesita frente al mockup están en la sección 7.

## **6.1 Inicio neutral**

Primera pantalla al abrir la app sin sesión.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Marca | Logo y nombre Zentheris | Identidad de la app | Zentheris |
| Botón Iniciar sesión | Abre el formulario de acceso | Entrada de usuarios existentes | — |
| Botón Registro | Abre el formulario de registro | Entrada de usuarios nuevos | — |

## **6.2 Inicio de sesión**

Formulario de acceso con Supabase.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Pestañas | Iniciar sesión / Registrarse | Alternar entre acceso y registro | Pestaña activa: Iniciar sesión |
| Correo electrónico | Campo de texto | Identifica la cuenta | usuario@correo.com |
| Contraseña | Campo con botón ver/ocultar | Valida el acceso | •••••••• |
| ¿Olvidaste tu contraseña? | Enlace | Inicia la recuperación por correo | — |
| Botón Iniciar sesión | Acción principal | Autentica y entra a la app | — |
| Enlace Crear cuenta | Enlace inferior | Lleva al registro | — |

## **6.3 Registro**

Formulario para crear la cuenta.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Nombre completo | Campo de texto | Se guarda en `usuarios.nombre_completo` | Ana Pérez |
| Correo electrónico | Campo de texto | Se guarda en `auth.users` | ana@correo.com |
| Celular (opcional) | Campo de texto marcado como opcional | Se guarda en `usuarios.telefono` | 300 123 4567 |
| Contraseña | Campo con ver/ocultar y requisitos | Mínimo 8 caracteres, una mayúscula y un número | Ejemplo2026 |
| Repetir contraseña | Campo con ver/ocultar | Solo validación, no se guarda | Ejemplo2026 |
| Botón Crear cuenta | Acción principal | Crea la cuenta; con verificación activa muestra "Revisa tu correo" | — |
| Enlace Iniciar sesión | Enlace inferior | Vuelve al acceso | — |

## **6.4 Panel principal**

Resumen del consumo del hogar en la última hora completa y en el día. Responde: ¿cómo voy ahora y hoy?

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Cabecera | Título, campana de alertas con indicador de no leídas (solo con el permiso de recibir alertas) y saludo según la hora | Entrada rápida a Alertas | "Buenas tardes, Ana" |
| Card Consumo actual | Valor de la última hora completa, cápsula de estado, comparación con la hora anterior y mensaje por estado | Último consumo y cómo está frente a la referencia | 0,62 kW · Normal · "2% más que la hora anterior" |
| Card Consumo actual (gráfico) | El mismo dato en gauge o anillo (botones arriba a la derecha), texto genérico del estado y selector kW/COP | Misma información con otra forma de mostrarla; el selector cambia toda la pantalla | Gauge al 40% · "Dentro de lo normal" |
| Card Consumo acumulado hoy | Acumulado del día, barra de progreso, "Límite" solo con meta activa, título y texto del estado | Cómo va el día frente a la meta o al promedio | 3,1 kWh · Límite 4,4 kWh · "Estás dentro del límite" |
| Zonas | Vista larga o compacta; por zona nombre, valor, participación y estado | Qué zonas pesan más en la última hora | Cocina · 34% · Normal |
| Barra de navegación | Principal, Historial, Zonas, Consejos, Configuración | Moverse entre secciones | — |

## **6.5 Historial**

Consumo por periodo. Responde: ¿cómo he consumido y cómo me comparo con antes?

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Selector de periodo | Día, Semana, Mes | Cambia todas las cards | Semana |
| Card Pico del periodo | Valor del último pico, cuándo ocurrió y estado | Cuándo fue el último pico y cuánto superó el promedio | "Último pico: viernes" · Elevado |
| Card Consumo | Gráfico de barras, línea o anillo, selector kW/COP y filtro por zona (General y zonas del hogar) | Evolución del consumo; el pico más alto va marcado con la etiqueta «Pico»; el anillo solo con General | Barras Lun–Dom, miércoles marcado como pico |
| Card Comparación | Periodo actual y anterior (mismo tramo), porcentaje y estado | Si se consume más o menos que antes | 28 kWh vs 19 kWh · "7% más que la semana anterior" |
| Card Costo estimado | Costo del periodo y proyección al cierre; sin tarifa pide configurarla | Cuánto cuesta el consumo | 94.000 COP · Proyección 105.000 COP |
| Botón Ver consejos | Botón al final | Lleva a Consejos | — |

## **6.6 Zonas**

Estado rápido de cada zona.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Card de zona | Ícono del tipo, nombre, kW de la última hora completa y estado de participación; orden alfabético | Estado de cada zona; abre la Zona individual | Cocina · 1,8 kW · Elevado |

## **6.7 Zona individual**

Detalle de una zona. Responde: ¿cómo está esta zona y cuánto pesa en la casa?

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Cabecera | Flecha atrás y nombre de la zona | Volver a Zonas | Sala |
| Banner | Ícono que representa la zona, sin datos | Identificación visual | Ícono de sofá |
| Card Estado actual (gráfico) | Consumo de la última hora de la zona en gauge o anillo, texto del estado y kW/COP | Estado de consumo de la zona frente a su promedio histórico a esa hora | 1,1 kW · "Dentro del rango habitual" |
| Card Estado actual (texto) | Mismos campos de la card 1 del Panel con el valor de la zona | Estado de consumo de la zona | 1,1 kW · Normal |
| Card Participación | Porcentaje del total, kW de la zona frente a kW totales, barra sobre 100 y estado | Cuánto pesa la zona en la última hora | 34% · "1,1 kW de 3,2 kW" · Normal |

## **6.8 Consejos**

Recomendaciones de ahorro estáticas. Responde: ¿qué puedo hacer para ahorrar?

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Cabecera | Título (sin ícono de chatbot) | Identificación de la pantalla | Consejos |
| Card Todo bajo control | Mensaje cuando no hay consejos pendientes | Indica que no hay recomendaciones por atender | "¡Todo bajo control!" |
| Lista de consejos | Casilla, título, descripción y etiqueta de prioridad (Alta, Media, Baja); completados opacos al final | Marcar un consejo lo pasa a completado para esa persona | "Apaga el aire al salir" · Alta prioridad |

## **6.9 Alertas**

Avisos de consumo, consejos e información. Responde: ¿qué ha pasado?

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Cabecera | Flecha atrás y título | Volver | Alertas |
| Filtros | Todas, Consumos, Consejos, Información | Filtran por categoría | Filtro: Consumos |
| Lista | Ícono, título, tiempo relativo y punto (relleno = no leída, color = severidad) | Se marca como leída al entrar; tocar no hace nada | "Consumo elevado en Cocina" · Hace 1 h · punto amarillo |
| Estado vacío | Mensaje cuando no hay alertas | Indica que no hay avisos | "No tienes alertas" |

## **6.10 Configuración**

Menú de ajustes agrupado por secciones.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Cabecera | Avatar (o iniciales) y nombre del usuario | Identidad del usuario | Ana Pérez |
| Cuenta | Editar perfil, Cambiar contraseña, Correo electrónico | Abre cada subpantalla | — |
| Notificaciones | Interruptor Alertas y Consejos | Controlan `notif_consumo` y `notif_consejos` | Alertas: encendido |
| Energía y consumo | Interruptor Meta de consumo, Establecer meta, Configurar tarifa, Fuentes de datos | Meta de consumo = `base_comparacion`; el resto abre su pantalla | Meta de consumo: apagado → compara con el promedio |
| Familia y acceso | Administrar miembros del hogar | Abre Miembros del hogar | — |
| Hogar y transición energética | Información del hogar y Mi huella de carbono, con etiqueta "Próximamente" | Funciones de la Fase 2 | — |
| Otros | Cerrar sesión | Cierra la sesión en este dispositivo | — |
| Zona de riesgo | Eliminar cuenta | Inicia el borrado de la cuenta con confirmación | — |

## **6.11 Editar perfil**

Datos personales y foto.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Avatar | Foto o iniciales con ícono de lápiz | Agregar o eliminar la foto | Iniciales "AP" |
| Información personal | Nombre completo, correo (solo lectura) y teléfono | Muestra los datos de la cuenta | Ana Pérez · ana@correo.com · 300 123 4567 |
| Botón Editar información | Activa la edición de nombre y teléfono en la misma pantalla | Actualiza `usuarios` | — |

## **6.12 Cambiar contraseña**

Cambio seguro de contraseña.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Contraseña actual | Campo con ver/ocultar | Se verifica primero | •••••••• |
| Nueva y Confirmar | Campos que se habilitan solo con la actual correcta | Definen la nueva contraseña | Ejemplo2027 |
| Lista de requisitos | 8 caracteres, una mayúscula, un número y ser diferente | Indica qué cumple la nueva contraseña | Chips que se marcan al cumplirse |
| Botón Guardar nueva contraseña | Acción principal (deshabilitada hasta cumplir todo) | Actualiza la contraseña | — |

## **6.13 Gestionar correo**

Cambio del correo de acceso.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Aviso | Explica que el correo sirve para iniciar sesión y recibir avisos | Contexto | — |
| Correo actual | Correo vigente, solo lectura | Referencia | ana@correo.com |
| Nuevo correo y Confirmar correo | Dos campos de texto | Definen el correo nuevo | ana.nueva@correo.com |
| Bloque Verificación | Avisa que se enviará un enlace al nuevo correo antes de guardar | Explica el siguiente paso | — |
| Botón Continuar | Deshabilitado hasta que los datos sean válidos | Envía el enlace de confirmación | — |

## **6.14 Establecer meta**

Meta mensual de consumo del hogar.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Consumo promedio actual | Promedio diario de los últimos 30 días | Referencia para elegir la meta | 14,2 kWh/día |
| Meta mensual | Valor en kWh con botones − y +, y el promedio diario equivalente (meta ÷ días del mes) | Define `valor_kwh_mensual` | 330 kWh · "11,0 kWh por día" |
| Tipo de meta | Ahorro, Eficiencia o Presupuesto con su descripción | Solo cambia textos | Ahorro |
| Botón Guardar meta | Acción principal | Crea la meta activa y deja la anterior inactiva | — |

## **6.15 Configurar tarifa**

Tarifa eléctrica del hogar.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Tarifa activa | Operador, valor por kWh, vigencia y botón Editar tarifa | Muestra la tarifa vigente | Operador X · 892 COP/kWh · desde septiembre de 2026 |
| Operador (opcional) | Lista desplegable | Se guarda en `operador` | Operador X |
| Valor aplicado de energía | Campo numérico en COP/kWh (obligatorio) | Se guarda en `precio_kwh` | 892 |
| Vigente desde | Selector de mes y año (obligatorio) | Se guarda el día 1 en `vigente_desde` | Septiembre de 2026 |
| Cargo fijo mensual (opcional) | Campo numérico | Se guarda en `cargo_fijo_mensual` | 12.000 |
| Aviso | La estimación puede no incluir subsidios ni contribuciones | Aclara el alcance del cálculo | — |
| Botón Guardar tarifa | Acción principal | Crea la tarifa nueva y cierra la anterior | — |

## **6.16 Fuentes de datos**

Estado de las fuentes de lectura (solo lectura).

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Fuente principal | Nombre, consumo de la última hora (suma de sus sensores) y estado | Muestra la fuente interna | Fuente principal Apto 502 · 2,4 kW · Activo |
| Sensor por zona | Nombre, zona, kW de la última hora y estado (Activo, Pausado, Sin datos) | Muestra cada punto de medición | Sensor Cocina · 0,9 kW · Activo |

## **6.17 Miembros del hogar**

Gestión de integrantes y permisos.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Resumen | Conteo de miembros activos | Informa cuántos integrantes hay | "2 miembros activos" |
| Lista | Avatar o iniciales, nombre, rol, estado y menú de acciones; invitaciones pendientes aparte, solo para el administrador | Ver quién pertenece al hogar | Ana · Administrador · Activo |
| Menú de acciones | Expulsar, transferir administración, cancelar invitación (solo administrador) | Gestiona los miembros | — |
| Permisos de los miembros | Cuatro interruptores: ver consumo actual, ver historial, recibir alertas, modificar metas | Actualiza los permisos del hogar (solo administrador) | Modificar metas: apagado |
| Botón Invitar miembro | Único botón de invitación | Abre la invitación por correo | — |

## **6.18 Datos y transición (Fase 2)**

Datos del hogar para recomendaciones de energías renovables.

| Elemento | Qué contiene | A qué responde | Ejemplo |
| :---- | :---- | :---- | :---- |
| Información del hogar | Estrato, tipo de vivienda, ciudad o municipio, número de personas e interruptor "¿Trabajan o estudian desde casa?" | Se guarda en `hogares` | Estrato 3 · Apartamento · Bogotá · 4 personas |
| Perfil de transición | Área del techo, factura promedio, vehículo eléctrico y presupuesto | Se guarda en `perfil_transicion` | 40 m² · 180.000 COP · No · 5.000.000 COP |
| Botón Guardar información | Un solo botón para ambas secciones | Guarda ambas secciones; el perfil solo si se llenó algo | — |

# **7. Pantallas: Trabajo Pendiente de Diseño**

Se separa en tres tipos según el esfuerzo.

**Estado (v4.9):** las pantallas de 7.1, 7.2 y 7.3 existen en la copia de trabajo de Figma (flujos Administrador y Miembro, pantallas v4.5), aprobadas en general por Nicolás el 02/11/2026; el 03/11/2026 se alinearon con el catálogo de textos (DC-19 a DC-23). Las tablas siguientes se conservan como especificación de lo que cada pantalla debe cumplir. Falta la prueba en Android e iOS.

**Definiciones de diseño de la v4.4.** Son tres, marcadas con (v4.4) en las tablas. No agregan pantallas, no eliminan ninguna y no cambian la navegación ni los mockups validados; definen estados de pantallas que ya estaban pendientes de diseño:

1. **Carga del backfill (7.1):** estado de error con botón Reintentar si la creación del hogar falla (RN-X-03).
2. **Fuentes de datos (7.3):** estado sin permiso que reusa el de Panel y Zonas; se ven nombres y estados, sin valores en kW (RN-XVI-06).
3. **Miembros del hogar (7.3):** la variante de solo lectura no muestra el bloque de invitaciones pendientes (RN-X-08).

## **7.1 Pantallas que aún no existen y hay que crear**

| # | Pantalla | Qué debe contener | Se necesita para |
| :---- | :---- | :---- | :---- |
| 1 | Onboarding | Paso 1: nombre del hogar y tipo de vivienda (5 opciones). Paso 2: selección de zonas del catálogo de 9, con los filtros por tipo de vivienda de RN-X-09 (zonas disponibles, contador 3 a 5 en apartaestudio, 4 básicas marcadas y bloqueadas en las demás viviendas, mensajes de ayuda). | Crear el hogar (reglas X). Incluye el enlace «Cerrar sesión» (RN-IX-08) |
| 2 | Carga del backfill | Mensaje "Preparando y analizando tu hogar..." mientras se generan los 30 días. (v4.4) Estado de error con botón Reintentar si la creación falla; no queda nada creado. | Entrar al Panel con datos completos (reglas IV y X) |
| 3 | Recuperar contraseña | Campo de correo y botón para enviar el enlace. | Enlace "¿Olvidaste tu contraseña?" (regla IX) |
| 4 | Restablecer contraseña | Nueva contraseña y confirmar, con los requisitos. | Completar la recuperación (regla IX) |
| 5 | Revisa tu correo | Aviso de que se envió un enlace, con opción de reenviar. | Registro con verificación y cambio de correo (regla IX) |
| 6 | Invitar miembro | Campo de correo del invitado y botón enviar. | Invitaciones (regla X) |
| 7 | Invitación recibida | Nombre del hogar y quién invita, con aceptar o rechazar. Incluye el enlace «Cerrar sesión» (RN-IX-08). | Respuesta a invitaciones (regla X) |
| 8 | Selector de foto | Hoja inferior con subir foto o eliminar foto. | Lápiz del avatar (regla IX) |
| 9 | Diálogos de confirmación | Eliminar cuenta, expulsar miembro, salir del hogar, transferir administración y cancelar invitación. | Acciones irreversibles (reglas IX y X) |
| 10 | Menú de acciones del miembro | Opciones expulsar, transferir y cancelar invitación según el caso. | Gestión del administrador (regla X) |
| 11 | Selectores de operador y de mes/año | Lista de operadores y selector de mes y año. | Configurar tarifa (regla XVI) |

## **7.2 Pantallas existentes que necesitan actualización**

Cambian botones, textos, títulos o elementos, sin rediseñar la disposición.

| Pantalla | Cambios |
| :---- | :---- |
| Inicio neutral, Inicio de sesión y Registro | Unificar los nombres de la acción de registro (Registrarse, Registro y Crear cuenta); en Registro, mostrar el celular como opcional, mostrar los requisitos de la contraseña y cambiar "Nombre" por "Nombre completo". |
| Panel principal | Saludo según la hora; campana con indicador de no leídas; nombres de zona en español y en orden alfabético; aclarar que "Consumo actual" es la última hora; usar "crítico" en lugar de "sobreconsumo" (incluida la alerta, que pasa a "Consumo crítico"); unidad coherente con el selector kW/COP; reemplazar textos de ejemplo ("States", "Zones"). |
| Historial | Quitar el ícono de descarga; dejar solo la versión con minititulos; quitar la barra de progreso de la card de costo; textos de cada card acordes al periodo; totales en kWh; filtro de zonas con las del hogar (Dormitorio en lugar de "Cuartos"); porcentajes del anillo que sumen 100%. |
| Zonas | Unidad escrita kW; nombres de zona del catálogo (Dormitorio); orden alfabético; íconos de las zonas nuevas (terraza, garaje y cuarto de servicio). |
| Zona individual | Quitar el lápiz de edición; reemplazar el texto "States" por el texto del estado; corregir la etiqueta de la barra de participación (dice "Cocina" en Sala); unidades que cambian con el selector kW/COP. |
| Consejos | Quitar el ícono de destellos (chatbot, Fase 2); agregar la etiqueta de prioridad Baja; mostrar la card "Todo bajo control" solo cuando no hay consejos pendientes, con los completados opacos debajo (RN-XV-02). |
| Alertas | Reemplazar los ejemplos "Tarifa nocturna" y "Nuevo dispositivo en la familia" por el catálogo de alertas (regla XIV); botón de campana con indicador. |
| Configuración | Mantener la sección Otros con Cerrar sesión (lugar principal; el segundo punto de acceso del Onboarding y de la Invitación recibida está en RN-IX-08); cambiar el texto de Consejos a "Recibe recomendaciones de ahorro"; renombrar "Conectar medidores" a "Fuentes de datos"; describir el interruptor Meta de consumo como comparación contra meta o promedio; mantener "Próximamente" en Información del hogar y Mi huella de carbono; mostrar el nombre real del usuario. |
| Editar perfil | Quitar "Historial de consumo" y "Cerrar sesión" (queda solo en Configuración); el botón Editar información activa la edición en la misma pantalla; mostrar iniciales cuando no hay foto. |
| Gestionar correo | El correo actual muestra el correo real en solo lectura; el bloque de verificación debe decir que se enviará un enlace (no un código). |
| Establecer meta | Quitar el selector kWh/COP y el ícono "?"; calcular el promedio diario con los días del mes; redactar las descripciones de Eficiencia y Presupuesto. |
| Configurar tarifa | Quitar "Residencial" y "Fuente: valor de mi factura"; agregar el campo opcional de cargo fijo mensual; el operador es una lista desplegable. |
| Fuentes de datos (antes Medidores) | Renombrar el título; quitar los botones "+", "Agregar medidor" y el ícono "?"; estados Activo, Pausado y Sin datos; valor en kW de la última hora; nombres "Sensor [zona]" y "Fuente principal [nombre del hogar]". |
| Miembros del hogar | Renombrar la sección a "Permisos de los miembros"; dejar un solo botón "Invitar miembro"; contar solo miembros activos y mostrar las invitaciones pendientes aparte, solo al administrador; texto neutro en lugar de "Cada miembro puede ver el consumo"; agregar el menú de acciones del administrador; botón "Salir del hogar" para los miembros. |
| Datos y transición (Fase 2) | Cambiar "recomendaciones personalizadas" y "personalizar el análisis" por "recomendaciones sobre energías renovables". |
| Barra de navegación | Unificar los íconos de Zonas y Consejos, que cambian entre pantallas (pin y cuadros; hoja y bombilla). |

## **7.3 Pantallas que solo necesitan un estado visual distinto**

No cambian la disposición; requieren una variante.

| Pantalla | Estado | Cuándo aparece |
| :---- | :---- | :---- |
| Configurar tarifa | Solo lectura | Para miembros que no son administrador |
| Establecer meta | Solo lectura | Para quien no tiene `permiso_modificar_metas` |
| Miembros del hogar | Solo lectura, sin el bloque de invitaciones pendientes (v4.4), y botón Salir del hogar | Para miembros que no son administrador |
| Datos y transición | Solo lectura | Para miembros que no son administrador (Fase 2) |
| Editar perfil | Modo edición en la misma pantalla | Al pulsar Editar información |
| Alertas | Estado vacío | Cuando no hay alertas |
| Panel, Zonas y Zona individual | Sin permiso (cards de datos con mensaje; saludo visible) | Cuando el miembro no tiene "ver consumo actual" |
| Fuentes de datos | Sin permiso (v4.4): reusa el estado de Panel y Zonas; nombres y estados visibles, sin valores en kW | Cuando el miembro no tiene "ver consumo actual" |
| Historial | Sin permiso (cards de datos con mensaje; selector y encabezado visibles) | Cuando el miembro no tiene "ver historial completo" |
| Panel, Historial, Zonas y Fuentes de datos | Sin datos | Cuando falta la lectura de la última hora |
| Cards de costo (Panel e Historial) | Sin tarifa | Aparece "Configura tu tarifa" y se oculta el selector COP |
| Card de acumulado (Panel) | Sin meta | Barra contra el promedio y sin texto "Límite" |
| Historial (Comparación y Mes) | No hay datos | Cuando no existe el periodo anterior |
| Campana de alertas | Oculta | Cuando el miembro no tiene el permiso de recibir alertas |
| Cards de estado | Sin referencia suficiente | Solo como respaldo si no hay promedio ni meta |
| Consejos | Prioridad Baja y completados opacos | Etiqueta Baja y consejos completados aún visibles |

# **8. Parámetros de Calibración y Configuración**

Son valores, no estructura: se fijan en un archivo de configuración del backend y se ajustan con los datos del simulador. No alteran tablas.

| Parámetro | Qué controla | Estado |
| :---- | :---- | :---- |
| Umbrales de estado | Porcentajes sobre la referencia que separan normal, elevado y crítico (iguales para todos los hogares en el MVP) | **Calibrado v1 (v4.9, DC-27)** con datos simulados: `umbrales-estado.v1.json`; evaluar personalización por hogar más adelante |
| Parámetros de cada personalidad | Bases por zona (9), curvas horarias (base y por zona), humor mínimo y máximo, factor de fin de semana, ruido (φ y σ, comunes a todas las zonas) y picos por zona; rango de consumo mensual de cada una de las 5 personalidades (respetando compacto < eficiente < intermedio < familiar < amplio) | **Cerrado (v4.4):** conjuntos v1.0 del 29/10/2026, aprobados en el acta 04 (sección 8.1) |
| Vigencia del consejo pendiente | Días que se muestra un consejo pendiente antes de poder generar otro | Fijado en 7 días (decisión v4.5) |
| Ocultamiento de alertas y consejos completados | 7 días después de la lectura o de completar | Fijado |
| Backfill | 30 días (720 horas) por zona | Fijado |
| Vencimiento de invitaciones | 7 días | Fijado |
| Límite de miembros | 5 activos (contando invitaciones pendientes al invitar) | Fijado |
| Referencia de Sin datos | Falta la lectura de la última hora completa | Fijado |
| Umbrales de asignación de personalidad | Valores de c, E y número de zonas de RN-X-04 | Fijados en RN-X-04; se pueden ajustar tras la calibración |
| Textos de consejos de las zonas nuevas | Textos por tipo de zona para terraza, garaje y cuarto de servicio (los íconos quedaron aprobados el 02/11/2026) | Cerrado: catálogo de textos v1 (38 plantillas, DC-18) |
| Proyección al cierre | Fórmula de RN-XIII-05 | Fijada (v4.9, DC-30) |
| Pico mínimo | Porcentaje sobre el promedio desde el que un valor es pico | 10 % (v4.9, DC-31) |

## **8.1 Parámetros de simulación cerrados (acta 04)**

Los cinco conjuntos v1.0 son la versión oficial de `perfiles_simulacion` para el generador de historial. Fueron aprobados por confirmación explícita de Nicolás el 29/10/2026. Cualquier cambio a estos archivos exige regenerarlos, repetir las pruebas y emitir una nueva acta.

| Archivo | SHA-256 |
| :---- | :---- |
| `consumo_compacto.json` | 5b753d74c569ded1be73592bb00089b263ba53029dd9ee4c9baf1c71675ebc12 |
| `consumo_eficiente.json` | 1b3ee380a4cbf52621830f6f1f27be4b31787e8666babe9735b56dacf8405dcc |
| `consumo_intermedio.json` | 5bd93608a2c6017097388c2c4b3e51373cf732c8d522cf43dbf5b95d1c3bd1e8 |
| `consumo_familiar.json` | 2ac80e2772fc62dc55a0e143010d781cbd594c8f6ef8e04a31f839e2f699f452 |
| `consumo_amplio.json` | 328e44959c38ccc2f9ac9a342b1c1c6734ef0291866d4bb2c878e4bd47cc2ae6 |
| `consolidado_perfiles_simulacion.json` | 6cfa97152a120edfdfde45921a1382e23025981d4ae1652c5f476e5489a90922 |

**Objetivos mensuales.** kWh por 30 días del hogar de referencia con todas las zonas que contempla su personalidad. Son datos simulados; la media sale de 100 semillas en un mes simulado (noviembre de 2026).

| Personalidad | Objetivo (kWh/30 d) | Media simulada (kWh/30 d) | Error |
| :---- | :---- | :---- | :---- |
| Consumo compacto | 34,10 | 34,04 | −0,16 % |
| Consumo eficiente | 57,63 | 57,56 | −0,12 % |
| Consumo intermedio | 75,06 | 75,13 | +0,10 % |
| Consumo familiar | 109,83 | 109,87 | +0,04 % |
| Consumo amplio | 152,96 | 152,94 | −0,01 % |

El orden compacto < eficiente < intermedio < familiar < amplio se cumple en los hogares de referencia, no en todos los hogares posibles: un hogar con menos zonas consume menos (RN-IV-07).

**Limitaciones aceptadas (acta 04, sección 4):**

1. Los eventos de sobreconsumo pesan poco en energía: entre 0,2 % y 2,9 % del total de cada hogar.
2. La variación mensual es baja (CV de 1 % a 3 %); cumplir la banda de ±10 % no demuestra realismo de la variabilidad.
3. En *Consumo compacto* la cocina pesa cerca del 67 % por la nevera (nota de la tabla 12).
4. El factor de fin de semana es único por hogar: la oficina y la lavandería quedan mal representadas por día, aunque el total del hogar cuadra.
5. Humor y ruido son supuestos sin evidencia empírica directa.
6. Los eventos no distinguen días laborales de fines de semana.
7. Posible duplicación de equipos entre zonas en intermedio y amplio (unos 0,12 kWh/día en intermedio).
8. La semilla usa SHA-256 (sección 5).
9. La secadora de amplio usa la potencia media del ciclo, no la nominal.

**Estado de verificación.** Validado en simulación (100 semillas, 59 pruebas de software) y en PostgreSQL local (16 de 16 comprobaciones, 29/10/2026). No está probado en Supabase ni en el módulo real del backend. Los umbrales de estado (RN-XI-02, RN-XI-07) no forman parte de esta aprobación; se calibraron aparte en la v4.9 (sección 8). **Verificación repetida el 03/11/2026:** 6/6 SHA-256, manifiesto 95/95, 59/59 pruebas y backfill reproducible; inserción de 6.480 lecturas en PostgreSQL 16 local en 0,12–0,14 s.

# **9. Decisiones Asumidas por Recomendación**

Estas decisiones no fueron resueltas explícitamente por el equipo; se tomó la opción más simple y coherente con las reglas ya validadas. Se pueden cambiar sin afectar el resto del documento. Desde la v4.5, las decisiones 13, 17, 18 y 20 están ratificadas (sección 9.2).

| # | Decisión | Dónde aplica |
| :---- | :---- | :---- |
| 1 | Si la personalidad que corresponde por tipo de vivienda y zonas no existe o está inactiva, se usa *Consumo eficiente* | Regla X |
| 2 | La versión del modelo es una constante del código | Regla IV |
| 3 | Recuperar al arrancar las horas faltantes del simulador | Regla IV |
| 4 | RLS por membresía activa; retención sin borrados salvo cuenta eliminada | Reglas I y XIX |
| 5 | Eliminar cuenta: borrar datos personales, conservar los del hogar y eliminar el hogar si era el único miembro | Regla IX |
| 6 | El tipo de vivienda se pide en el onboarding (regla original) y los demás datos del hogar son Fase 2 | Reglas X y XVIII |
| 7 | Agregar `trabajo_estudio_casa` (opcional) a `hogares` | Tabla 4 |
| 8 | `base_comparacion` obligatorio con valor por defecto `promedio` | Tabla 3 |
| 9 | Catálogo inicial de 5 alertas y 3 reglas de consejos, con sus claves anti-duplicado | Reglas XIV y XV |
| 10 | Vigencia de consejos medida desde `created_at`, sin campos nuevos | Regla XV |
| 11 | Permisos "ver consumo" y "ver historial" reemplazan las cards de datos por un mensaje (saludo visible; la campana depende del permiso de recibir alertas) | Regla XVII |
| 12 | Saludo por franjas horarias de Bogotá | Regla XII |
| 13 | Nombres visibles de zona (Cocina, Sala, Dormitorio, Baño, Lavandería, Oficina, Terraza, Garaje, Cuarto de servicio) | Regla XII |
| 14 | Un nuevo `vigente_desde` de tarifa debe ser posterior al vigente | Regla XVI |
| 15 | Estrato con opciones de 1 a 6 | Regla XVIII |
| 16 | La fila de `perfil_transicion` se crea solo si se llena algo | Regla XVIII |
| 17 | Las 4 zonas básicas aparecen marcadas y no se pueden desmarcar en apartamento, casa, dúplex y casa campestre | Regla X (RN-X-09) |
| 18 | Apartaestudio con 5 zonas queda como *Consumo eficiente*, sin importar si la quinta es oficina o lavandería | Regla X (RN-X-04) |
| 19 | Dúplex sigue las mismas reglas de zonas y de asignación que casa y apartamento | Reglas X |
| 20 | Casa campestre se calcula como una casa subiendo un nivel, con tope en amplio; solo con básicas queda en *Consumo intermedio* | Regla X (RN-X-04) |
| 21 | Si el hogar no tiene una zona que contempla su personalidad, el consumo total baja y no se reparte entre las demás zonas | Regla IV (RN-IV-07) |
| 22 | `ruido_config` tiene memoria e intensidad comunes a todas las zonas; el ruido por zona queda para la Fase 2 | Sección 5 y sección 2 |
| 23 | Los valores de catálogo nuevos son `duplex`, `casa_campestre` y `cuarto_servicio` (se muestran Dúplex, Casa campestre y Cuarto de servicio) | Reglas II y III |
| 24 | Los sorteos de cada zona se derivan de la semilla del hogar y día combinada con el tipo de zona | Sección 5 |
| 25 | La quinta personalidad se llama *Consumo intermedio* (reemplaza el concepto de personalidad diurna) y las 5 personalidades siguen una escala de menor a mayor consumo | Tabla 12 |

## **9.1 Decisiones aceptadas por Nicolás (29-30/10/2026)**

Estas decisiones surgieron al definir el contrato API y las aprobó Nicolás como responsable del proyecto. Van aparte porque no fueron ratificadas por el equipo completo.

| # | Decisión | Dónde aplica |
| :---- | :---- | :---- |
| N1 | El backfill forma parte de la transacción de creación del hogar; si falla, no queda nada creado | RN-X-03 |
| N2 | El backend envía el correo de invitación; se bloquea invitar dos veces al mismo correo o a un miembro activo, y la invitación a alguien con otro hogar falla al aceptar | RN-X-05 |
| N3 | La salida del administrador es en dos pasos con las pantallas existentes | RN-II-04, RN-X-07 |
| N4 | Fuentes de datos oculta los valores en kW sin el permiso de ver consumo actual | RN-XVI-06, RN-XVII-01 |
| N5 | La ficha del usuario se crea en el primer acceso con sesión, con nombre y teléfono tomados de los metadatos del registro | RN-IX-01 |
| N6 | Las invitaciones pendientes solo las ve el administrador | RN-X-08, RN-XVI-07 |
| N7 | La app sube la foto directamente a Storage y el backend guarda solo su ruta | RN-I-02 |
| N8 | Los mensajes por estado se entregan como códigos; los textos de alertas y consejos salen de la configuración del backend | RN-XI-09 |
| N9 | La personalidad es interna y no se expone; el backend verifica membresía, rol y permiso en cada llamada | RN-X-04, RN-I-03 |
| N10 | Nota en la tabla 12 sobre la cocina de *Consumo compacto*, sin cambiar su descripción | Tabla 12 |
| N11 | Tres definiciones de diseño pendiente: error de la carga del backfill, Fuentes de datos sin permiso y Miembros sin invitaciones para no administradores | Sección 7 |

## **9.2 Decisiones aceptadas en v4.5 (02/11/2026)**

Nicolás aceptó como decisión las recomendaciones de la propuesta v4.5 y de la revisión de la v4.4. Quedan ratificadas las decisiones 13, 17, 18 y 20 de la sección 9; las demás siguen como asumidas.

| # | Decisión | Dónde aplica |
| :---- | :---- | :---- |
| D1 | La card «Todo bajo control» solo aparece sin consejos pendientes | RN-XV-02, §7.2 |
| D2 | Anillo de zonas con 4 zonas y «Otras zonas» desde la quinta; la lista muestra todas | RN-XIII-04 |
| D3 | Formato es-CO con decimales por unidad: kW 2, kWh 1, COP 0 | RN-XII-08 |
| D4 | «Espacios físicos de la casa» en lugar de «Habitaciones» | §3 (tabla 8) |
| D5 | El pico no usa rojo; se marca con la etiqueta «Pico» y el rojo queda para el estado crítico | RN-XIII-03 (**reemplazada por D17 en v4.7**: el pico sí usa rojo claro, con reglas de separación) |
| D6 | El acumulado de hoy respeta `base_comparacion` | RN-XI-04 |
| D7 | El estado `expirada` de las invitaciones se calcula al consultar | RN-X-05 |
| D8 | Las alertas no leídas nunca se ocultan | RN-XIV-05 |
| D9 | Una alerta por regla y zona al día, dicho de forma explícita | RN-XIV-08 |
| D10 | Vigencia de los consejos pendientes: 7 días | RN-XV-05, sección 8 |
| D11 | Correcciones editoriales del ejemplo de Andrés y de la tabla de Historial | §4, §6.5 |

## **9.3 Decisiones aceptadas en v4.6 (02/11/2026)**

Revisión de Nicolás de las pantallas v4.5 en Figma. Las decisiones D12 a D16 se registran aquí; la D12 ajusta la D5 solo en lo que dice sobre el color del pico.

| # | Decisión | Dónde aplica |
| :---- | :---- | :---- |
| D12 | El pico lleva un color propio junto a la etiqueta «Pico». **Reemplazada en v4.7 por D17.** Historial: blanco (descartado), cian #38BDF8 (descartado) y amarillo #FDE047 (descartado por choque con «Elevado») | RN-XIII-03 |
| D13 | «Cerrar sesión» también en Onboarding e Invitación recibida; cierra la sesión y cancela la creación del hogar sin guardar nada | RN-IX-08 |
| D14 | Lista de operadores de la tarifa: Afinia, Air-e, CHEC, Celsia, Enel Colombia, EPM, ESSA, Otro operador | RN-XVI-05, §10 |
| D15 | Íconos de Lavandería, Terraza, Garaje y Cuarto de servicio: washing-machine, fence, car, door-closed (probables en Lucide) | §7.2, §10 |
| D16 | El anillo de distribución por zona es vigente en Historial (Día, Semana y Mes), solo con el filtro General | RN-XIII-04 |

## **9.4 Decisiones aceptadas en v4.7 (02/11/2026)**

Pedido de Nicolás tras la revisión de la v4.6: pintar el pico en rojo y evitar que se confunda con «Crítico».

| # | Decisión | Dónde aplica |
| :---- | :---- | :---- |
| D17 | El pico se pinta en rojo claro `chart/peak` (#F59099, red-400 de la paleta), distinto del rojo de estado `status/error` (#EF4444). Para no confundirlo con «Crítico»: etiqueta «Pico» neutra; sin componentes ni palabras de estado en el pico; rojo de estado solo para estados; identificación por posición antes que por color. Reemplaza a D12 y ajusta la D5 | RN-XIII-03 |

**Riesgo abierto:** #F59099 es el mismo valor que el texto de error en oscuro (`z-color-red-400`). Por eso la separación depende de forma y texto, no del color. Si al probar en dispositivo o con daltonismo se confunde, la alternativa es cambiar el color del pico, no la regla de texto.

## **9.5 Decisiones de cierre (v4.9, 03/11/2026)**

Tomadas con la autonomía que delegó Nicolás el 03/11/2026, después de verificar su coherencia con este documento, el contrato, el catálogo de textos y el sistema de diseño. Se consideran aprobadas salvo que Nicolás pida revertir alguna. El detalle, con su evidencia, está en `00_estado-y-pendientes/registro-decisiones-cierre-2026-11-03.md`.

| Grupo | IDs | Resumen |
| :---- | :---- | :---- |
| Alcance y herramientas | DC-01 a DC-15 | Transición fuera del MVP; repositorio y ramas; Supabase `zentheris-dev` (us-east-1); SMTP Brevo; contraseña en Supabase; Satoshi sin versionar (`.easignore`); cupos; operador; diálogo de cierre de sesión; tipo de meta; números sin formato en la API; gráficos con react-native-gifted-charts; ícono `clock`; nombres Lucide verificados; pico D17 vigente en el sistema de diseño |
| Textos y diseño | DC-16 a DC-25 | Errores genéricos y su mapeo HTTP; metas; consejos de zonas nuevas; textos del pico; Fuentes de datos sin «Datos simulados»; el catálogo manda sobre Figma; cifras de ejemplo coherentes; estado «todo completado»; `consejos.categoria`; `regla_origen` y `clave_evento` |
| Datos y cálculos | DC-26 a DC-35 | Hashes y semilla repetidos; umbrales v1; referencias; comparación; proyección; pico; cierre de mes; backfill síncrono por lotes; generación por recuperación; alertas solo en vivo |
| Modelo y Supabase | DC-36 a DC-45 | D-SQL-1 a D-SQL-5; únicos e índices; invitación vencida; Storage; JWT; migraciones y semilla |
| Contrato, pruebas y documentos | DC-46 a DC-53 | Redocly como linter; contrato 0.2.5; historias v5; matriz de pruebas; Notion y credenciales (acciones externas); versiones; simulador de producción a partir del Avance 03 con `VERSION_MODELO` fija |
| Desarrollo (03/11/2026, después del cierre) | DC-54 a DC-58 | Proyecto de Supabase existente con el esquema reconstruido desde migraciones; refactor en el repositorio existente; arquitectura cliente-servidor con monolito modular por capas y contrato primero; desarrollo con Claude Code (`CLAUDE.md` y `docs/` en el repositorio, revisión humana); tokens vigentes del artifact |

# **10. Pendientes que dependen de terceros (v4.9)**

Ninguno bloquea el modelo de datos. Todos están en `PENDIENTES-GENERAL-antes-de-backend.md` (v2).

* Autorización de Nicolás para pasar a desarrollo (crear la base, configurar Supabase y generar Word y PDF de la v4.9).
* Crear las cuentas: proyecto de Supabase, Brevo (remitente verificado), Render y EAS.
* Correr el lint oficial del contrato (`npx @redocly/cli lint`) en un equipo con acceso a npm.
* Medir el backfill en Render + Supabase (criterio de 10 s, RN-X-03).
* Probar en Android e iOS, con lectores de pantalla, texto grande y simulación de daltonismo (pico D17).
* Notion: asignar responsables y fechas, crear las tareas faltantes y mover las credenciales a un gestor.
* Probar en Supabase las plantillas de correo y las variables `{{ }}`.
