# Especificación de Supabase y base de datos v1.1 · 10/11/2026

Estado: **EJECUTADA el 08/11/2026** en el proyecto nuevo `zentheris` (ref `hylseqruipigpewjfxmf`); evidencia en `entornos/definitivo/acta-migracion-2026-11-08.md`. Esta v1.1 (10/11/2026) actualiza la v1 del 03/11/2026: cambia la sección 1 (proyecto nuevo, no el existente, M-1) y los datos de Auth (sección 2). Las tablas, RLS y Storage no cambian. No contiene SQL. Fuente: reglas v4.9 (sección 3 y «Integridad, seguridad y almacenamiento») y registro DC-36 a DC-45. El borrador `borrador-v4.4-no-ejecutado/` sirve como punto de partida, pero hay que aplicarle las diferencias de la sección 6.

## 1. Proyecto y entornos

| Elemento | Valor |
|---|---|
| Proyecto | **`zentheris`**, proyecto nuevo en la organización «Zentheris» (M-1; reemplaza el criterio de reutilizar el existente, DC-54). Ref `hylseqruipigpewjfxmf`. El original (`fmxfjimwdtdmbexszcpm`) quedó pausado; `zentheris-qa` se borró. Laboratorio de pruebas aparte (`zentheris-dev`, otra organización) |
| Región | us-east-1, junto a Render Virginia |
| Acceso | Equipo ya invitado a la organización «Zentheris» (rol Developer). Sin credenciales compartidas ni pegadas en Notion o el repositorio. |
| Plan | Gratuito. Se pausa tras una semana sin actividad: reactivarlo desde el panel antes de cada demostración. |
| Entrega | En el mismo proyecto: activar «Confirm email» (RN-IX-03). El SMTP propio con Brevo ya está configurado desde el 10/11/2026 |

**Histórico (DC-54, ya no aplica):** se pensó inventariar y limpiar el proyecto existente. Se prefirió un proyecto nuevo (M-1) y las claves del original, que estuvieron en Notion, ya no sirven. Las claves de `zentheris` no se han puesto en Notion; ver `guias/guia-claves-y-variables.md`.

## 2. Auth

| Ajuste | Valor |
|---|---|
| Proveedor | Correo y contraseña |
| Confirm email | **Desactivado** (verificado el 10/11/2026); se activa antes de la entrega |
| Contraseña | Mínimo 8; requisito «letras y dígitos» (DC-05). La app y el backend validan la mayúscula y el número (RN-IX-02). |
| SMTP | **Configurado** el 10/11/2026: Brevo, `smtp-relay.brevo.com:587`, Username = Login SMTP de Brevo, clave SMTP en el panel; remitente = Gmail verificado del proyecto, en minúsculas (Brevo distingue mayúsculas). entrega validada el 10/11/2026 (llegó a spam) Dominio propio: fuera del MVP (DC-04) |
| Plantillas | `06_catalogo-de-textos/catalogo-textos-v1/supabase/plantillas-auth.es-CO.json` (confirmación, recuperación, cambio de correo) |
| URL del sitio y redirecciones | Site URL `zentheris://`; redirecciones `zentheris://**` y `exp://**` (hecho, DC-44) |
| Metadatos de registro | `nombre_completo` y `telefono` (RN-IX-01, N5) |
| JWT | El backend valida con JWKS (`/auth/v1/.well-known/jwks.json`); si el proyecto usa el secreto HS256 heredado, con ese secreto (DC-44) |

## 3. Storage

Bucket `avatares`, **privado**. Ruta `{usuario_id}/avatar.{jpg|png|webp}`, máximo 2 MB, tipos `image/jpeg`, `image/png` e `image/webp`.

- Escritura y borrado: solo el usuario dueño de la carpeta.
- Lectura: el dueño y los miembros activos de su mismo hogar.
- La app muestra la foto con una URL firmada.
- Al eliminar la cuenta, el backend borra la carpeta (RN-IX-09).

## 4. Tablas, en orden de creación

`auth.users` ya existe. Se crean 17 tablas propias, todas con `created_at`, `updated_at` y la actualización automática de `updated_at`.

| # | Tabla | Dependencias | Restricciones clave (v4.9) |
|---|---|---|---|
| 1 | `perfiles_simulacion` | — | `nombre` único; 9 bases ≥ 0; `factor_fin_semana` > 0; JSON obligatorios |
| 2 | `usuarios` | auth.users | PK = FK a `auth.users`, borrado en cascada |
| 3 | `preferencias_usuario` | usuarios | Borrado en cascada; `base_comparacion` en (meta, promedio), por defecto promedio |
| 4 | `hogares` | perfiles_simulacion | `tipo_vivienda` del catálogo de 5; `perfil_simulacion_id` NOT NULL; estrato 1–6; personas ≥ 1; permisos por defecto true, true, true, false |
| 5 | `perfil_transicion` | hogares | `hogar_id` único; borrado en cascada |
| 6 | `hogar_miembros` | hogares, usuarios | `usuario_id` opcional, se vuelve nulo al borrar el usuario; rol y estado del catálogo; si el estado es activo, `usuario_id` es obligatorio; único parcial (usuario activo) y (hogar, administrador activo) |
| 7 | `invitaciones_hogar` | hogares, usuarios | `invitado_por` opcional, se vuelve nulo al borrar el usuario; `token_hash` único; 5 estados; único parcial (hogar, correo en minúsculas) entre las pendientes |
| 8 | `zonas` | hogares | Tipo del catálogo de 9; (hogar, nombre) único; borrado en cascada desde el hogar |
| 9 | `fuentes_principales` | hogares | `hogar_id` único |
| 10 | `sensores_zona` | zonas, fuentes_principales | `zona_id` único; estado activo o pausado |
| 11 | `lecturas` | sensores_zona | (sensor, fecha_hora) único; `consumo_kwh` NUMERIC(12,4) ≥ 0; `calidad` en (simulada, estimada, real); borrado en cascada desde el sensor |
| 12 | `tarifas_hogar` | hogares | `precio_kwh` ≥ 0; cargo fijo ≥ 0; `vigente_hasta` > `vigente_desde`; sin solapamiento por hogar (exclusión con `btree_gist`); una sola abierta |
| 13 | `metas_consumo` | hogares | Tipo del catálogo de 3; valor > 0; `fecha_fin` > `fecha_inicio`; única activa por hogar |
| 14 | `alertas` | hogares, zonas | Categoría y severidad del catálogo; `clave_evento` única; `zona_id` opcional |
| 15 | `alertas_usuario` | alertas, usuarios | PK (alerta, usuario); borrado en cascada desde ambos |
| 16 | `consejos` | hogares, zonas | Prioridad del catálogo; `categoria` en (zona, general) |
| 17 | `consejos_usuario` | consejos, usuarios | (consejo, usuario) único; `pendiente` ↔ `completada_en` vacío; borrado en cascada desde ambos |

**Índices además de los únicos:** `alertas(hogar_id, created_at desc)`, `consejos(hogar_id, created_at desc)`, `alertas_usuario(usuario_id, leida_en)`, `consejos_usuario(usuario_id, estado)`, `hogar_miembros(hogar_id, estado)` y `zonas(hogar_id)`. La consulta horaria de `lecturas` usa el único (sensor, fecha_hora).

**Borrado del hogar:** si el usuario eliminado era el único miembro (RN-IX-09), el backend borra el hogar. Zonas, fuente, sensores, lecturas, tarifas, metas, alertas, consejos, invitaciones y perfil de transición se borran en cascada desde `hogares`.

## 5. RLS (segunda defensa; la primera es el backend, RN-I-03)

RLS activa en las 17 tablas. La app solo lee directo lo que necesite. Por contrato, todo pasa por la API. La matriz describe lo que un cliente autenticado puede **leer**. Escribir solo lo hace el backend.

| Tabla | Puede leer |
|---|---|
| usuarios | Su propia fila y las de miembros activos de su hogar (nombre y avatar) |
| preferencias_usuario, alertas_usuario, consejos_usuario | Solo sus filas |
| hogares, zonas, fuentes_principales, sensores_zona | Miembros activos del hogar |
| hogar_miembros | Miembros activos del hogar |
| invitaciones_hogar | El administrador del hogar; el invitado, solo las dirigidas a su correo |
| lecturas | Miembros activos con `permiso_ver_consumo_actual` o `permiso_ver_historial`, o el administrador |
| tarifas_hogar, metas_consumo, consejos | Miembros activos del hogar |
| alertas | Miembros activos con `permiso_recibir_alertas`, o el administrador |
| perfil_transicion | Miembros activos del hogar |
| perfiles_simulacion | Nadie (solo el backend) |

Se recomiendan funciones auxiliares de solo lectura: «es miembro activo del hogar», «es administrador del hogar» y «tiene permiso X en el hogar». Las pruebas de RLS van en la matriz de pruebas (`09_pruebas/`).

## 6. Diferencias que hay que aplicar al borrador v4.4 al regenerarlo

1. `hogar_miembros.usuario_id`: opcional, se vuelve nulo al borrar el usuario, con la condición «activo ⇒ usuario» (antes era RESTRICT).
2. `invitaciones_hogar.invitado_por`: opcional, se vuelve nulo al borrar el usuario.
3. `hogares.perfil_simulacion_id`: NOT NULL.
4. `consejos.categoria`: condición (zona, general).
5. Único parcial (hogar, correo en minúsculas) entre las invitaciones pendientes.
6. Las políticas RLS pasan de solo lectura por membresía a la matriz de la sección 5.
7. Cascadas desde `auth.users` hacia los datos personales.
8. Comprobar que el catálogo de zonas tiene 9 tipos y el de viviendas 5 (ya estaba en v4.4).

## 7. Semilla y comprobación

1. Cargar las 5 personalidades desde `consolidado_perfiles_simulacion.json`, después de comprobar que su SHA-256 es `6cfa9715…0a90922` (acta 04).
2. Comprobaciones posteriores: 17 tablas propias; 5 personalidades con nombres exactos; curvas de 24 valores que suman 1; RLS activa en las 17; bucket `avatares` privado.
3. Prueba de humo: crear un hogar de prueba con el endpoint de onboarding y verificar 720 × número de zonas lecturas, sin duplicados (consultas equivalentes a `02_verificacion.sql` del Avance 03).

## 8. Variables de entorno

**Backend (Render):** `DATABASE_URL` (Transaction Pooler, puerto 6543), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (solo en el servidor), `SUPABASE_JWKS_URL` o `SUPABASE_JWT_SECRET`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_REMITENTE`, `APP_ENLACE_INVITACION` (por ejemplo, `zentheris://invitacion?token=`), `ZONA_HORARIA=America/Bogota`, `RUTA_UMBRALES` y `RUTA_TEXTOS_BACKEND`.

**App (Expo):** `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY` y `EXPO_PUBLIC_API_URL`. La clave `anon` es pública por diseño; la `service_role` nunca va en la app.

Los valores reales nunca van en el repositorio ni en Notion: van en el panel de cada servicio y en `.env` local, que está en `.gitignore`.
