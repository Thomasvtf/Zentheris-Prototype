# Historias de usuario v5 · MVP Zentheris

Versión 5.0 · 03/11/2026. Se derivan de las reglas v4.9 y el contrato 0.2.5 (DC-48), y reemplazan a las v4 FINAL, que quedan como históricas: tenían texto dañado e incluían IA, reportes y detección de anomalías, que no entran en el MVP. Formato: *Como … quiero … para …*, con criterios verificables, reglas y endpoint. La prioridad sigue el orden de construcción de la guía 3. Responsables y fechas viven en Notion.

## 1. Acceso y cuenta

| ID | Historia | Criterios de aceptación | Reglas · Endpoint |
|---|---|---|---|
| HU5-01 | Como persona nueva quiero crear mi cuenta para usar Zentheris | Pide nombre completo, correo, celular (opcional), contraseña y repetir contraseña. Los requisitos se marcan al cumplirse. Con verificación activa muestra «Revisa tu correo». La ficha se crea en el primer acceso. | RN-IX-01, IX-02, IX-03 · Supabase Auth, `POST /usuarios/me` |
| HU5-02 | Como usuario quiero iniciar sesión para ver mi hogar | Con hogar → Panel; sin hogar y con invitación → Invitación recibida; sin hogar ni invitación → Onboarding. | RN-X-01 · Supabase Auth, `GET /usuarios/me` |
| HU5-03 | Como usuario quiero recuperar mi contraseña | Escribo el correo, recibo un enlace y defino una contraseña que cumple las reglas. Si el enlace venció, veo `error.app.enlace_correo_vencido`. | RN-IX-04 |
| HU5-04 | Como usuario quiero cambiar mi contraseña | Primero valida la actual; la nueva cumple las reglas y es distinta. | RN-IX-05 · `/usuarios/me/contrasena/*` |
| HU5-05 | Como usuario quiero cambiar mi correo | El correo actual es de solo lectura; se envía un enlace al nuevo y el cambio se aplica al confirmar. | RN-IX-06 |
| HU5-06 | Como usuario quiero editar mi nombre, mi teléfono y mi foto | La edición se hace en la misma pantalla; sin foto se muestran las iniciales; la foto va a Storage. | RN-I-02, IX-07 · `PATCH /usuarios/me`, `/avatar` |
| HU5-07 | Como usuario quiero cerrar sesión | Desde Configuración. En Onboarding o Invitación recibida pide confirmación, cancela la creación del hogar y conserva la ficha. | RN-IX-08 |
| HU5-08 | Como usuario quiero eliminar mi cuenta | Pide confirmación. El administrador con más miembros debe transferir antes. Si soy el único miembro, también se elimina el hogar. | RN-IX-09 · `DELETE /usuarios/me` |

## 2. Hogar y onboarding

| ID | Historia | Criterios | Reglas · Endpoint |
|---|---|---|---|
| HU5-09 | Como persona sin hogar quiero crear mi hogar | Paso 1: nombre y tipo de vivienda. Paso 2: zonas con los filtros de RN-X-09. El backend valida igual; si algo falla no queda nada creado y se ofrece Reintentar. | RN-X-02, X-03, X-09 · `POST /onboarding` |
| HU5-10 | Como usuario quiero ver historial desde el primer día | Al terminar el onboarding hay 30 días de lecturas; mientras se generan, la app muestra una pantalla de carga. | RN-IV-01, IV-02 |

## 3. Panel, Zonas e Historial

| ID | Historia | Criterios | Reglas · Endpoint |
|---|---|---|---|
| HU5-11 | Como miembro quiero ver el consumo de la última hora completa | kW con 2 decimales, estado con palabra e ícono, variación frente a la hora anterior, intervalo visible y selector kW/COP (COP solo con tarifa). | RN-XI-01 a XI-03, XII-04 · `GET /consumo/actual` |
| HU5-12 | Como miembro quiero ver cómo va mi día | Acumulado en kWh, comparado con el promedio a esa hora o con el límite de la meta («Límite» solo con meta); estado según los umbrales v1. | RN-XI-04, DC-27 |
| HU5-13 | Como miembro quiero ver qué zona pesa más ahora | Zonas en orden alfabético con kW, participación y estado; vista larga o compacta. | RN-XI-05, XII-05, XII-06 · `GET /consumo/zonas` |
| HU5-14 | Como miembro quiero ver el detalle de una zona | Estado frente al promedio de esa hora (nunca contra la meta) y participación. Sin edición. | RN-XI-06, XII-07 · `GET /consumo/zonas/{id}` |
| HU5-15 | Como miembro quiero consultar Día, Semana y Mes | Barras, línea o anillo (el anillo solo con General: 4 zonas + «Otras zonas»); pico marcado con «Pico»; comparación del mismo tramo; costo y proyección. | RN-XIII-01 a XIII-06, DC-29 a DC-31 · `GET /historial` |
| HU5-16 | Como miembro sin permiso quiero entender por qué no veo datos | Solo las cards de datos cambian a «No tienes permiso…»; el saludo y la cabecera siguen visibles. | RN-XVII-05 |

## 4. Alertas y consejos

| ID | Historia | Criterios | Reglas · Endpoint |
|---|---|---|---|
| HU5-17 | Como miembro quiero enterarme si una zona consume demasiado | Alerta elevado o crítico, una por regla, zona y día, solo de horas en vivo, entregada según el permiso y el interruptor del momento. | RN-XIV-06 a XIV-08, DC-35 |
| HU5-18 | Como miembro quiero ver mis alertas | Filtros, la más reciente primero, tiempo relativo y punto de lectura. Se marcan leídas al entrar; las leídas se ocultan a los 7 días; estado vacío. | RN-XIV-01 a XIV-05, XIV-09 · `/alertas*` |
| HU5-19 | Como miembro quiero consejos para reducir el consumo | Pendientes de mayor a menor prioridad y completados opacos al final; «Todo bajo control» solo sin pendientes; el estado es individual. | RN-XV · `/consejos*` |
| HU5-20 | Como miembro quiero un resumen al cerrar el mes | Alerta de cierre: dentro o por encima de la referencia del hogar. Si quedó por encima, se crea un consejo general. | RN-XIV-07, XV-07, DC-32 |

## 5. Configuración, metas y tarifa

| ID | Historia | Criterios | Reglas · Endpoint |
|---|---|---|---|
| HU5-21 | Como usuario quiero controlar mis avisos y la base de comparación | Interruptores de Alertas, Consejos y Meta de consumo; son individuales. | RN-VI-04, VII-01, XVI-02, XVI-03 · `/preferencias` |
| HU5-22 | Como administrador (o con permiso) quiero fijar una meta mensual | En kWh, mayor que 0; muestra el promedio diario de 30 días y el equivalente por día; el tipo solo cambia textos; la meta anterior queda inactiva. | RN-V-03, XVI-04 · `/meta`, `/metas` |
| HU5-23 | Como administrador quiero configurar la tarifa | Operador de la lista aprobada, valor por kWh, mes de vigencia posterior a la vigente y cargo fijo opcional; aviso de subsidios. | RN-V-01, V-02, XVI-05 · `/tarifa`, `/tarifas` |
| HU5-24 | Como miembro quiero ver las fuentes de datos | Solo lectura; estados Activo, Pausado y Sin datos; sin permiso, sin valores en kW. | RN-XVI-06 · `/fuentes-datos` |

## 6. Miembros

| ID | Historia | Criterios | Reglas · Endpoint |
|---|---|---|---|
| HU5-25 | Como administrador quiero invitar a mi familia | Correo, enlace de 7 días y límite de 5 contando pendientes; no se puede repetir una invitación pendiente ni invitar a un miembro activo. | RN-X-05 · `POST /invitaciones` |
| HU5-26 | Como persona invitada quiero aceptar o rechazar | Al aceptar entro como miembro y se avisa al hogar; falla si ya tengo otro hogar o el hogar está lleno. | RN-X-06 · `/invitaciones/*` |
| HU5-27 | Como administrador quiero gestionar miembros y permisos | Expulsar, transferir, cancelar invitación y mover los 4 permisos, siempre con confirmación. Los miembros los ven en solo lectura y tienen «Salir del hogar». | RN-II-03, II-04, X-07, X-08 |

Total: 27 historias. Fuera del MVP: transición energética, huella de carbono, reportes, chatbot, push, IA.
