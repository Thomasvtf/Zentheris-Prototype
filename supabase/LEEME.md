# Migraciones definitivas de Zentheris (6)

**Estado (08/11/2026):** **aplicadas** en el proyecto definitivo `zentheris` (ref `hylseqruipigpewjfxmf`, organización «Zentheris»). La huella coincide al 100 % con el laboratorio `zentheris-dev` (ref `cjybhgmpiduwlaozjels`, «nicv25's Org»), donde pasaron 55 de 55 pruebas el 06/11/2026. Evidencia: `Archivos_Zentheris/02_base-de-datos/entornos/definitivo/acta-migracion-2026-11-08.md`.
**Fuente:** reglas v4.9 §3, [`docs/supabase/especificacion-supabase-v1.md`](../docs/supabase/especificacion-supabase-v1.md), decisiones DC-36 a DC-45.

## Orden, versión real y contenido

El nombre de cada archivo es `<version>_<nombre>.sql`, igual al historial de la base (`list_migrations`). Así Supabase CLI los reconoce como ya aplicados.

| # | Archivo (versión real) | Qué hace |
|---|---|---|
| 1 | `20261108223757_0001_extensiones_y_utilidades.sql` | `btree_gist`, esquema `privado` (no expuesto por la API), función de `updated_at` |
| 2 | `20261108223841_0002_tablas.sql` | 17 tablas con PK, FK, CHECK y comentarios |
| 3 | `20261108223859_0003_indices_y_triggers.sql` | Únicos parciales, índices, 17 triggers de `updated_at` y tope de 5 miembros (RN-II-02) |
| 4 | `20261108223928_0004_rls.sql` | Funciones auxiliares, RLS en 17 tablas, 16 políticas de lectura, sin escritura para la app (DC-40) |
| 5 | `20261108223946_0005_storage_avatares.sql` | Bucket privado `avatares` (2 MB; jpg, png, webp) y 4 políticas (DC-43) |
| 6 | `20261108224101_0006_semilla_perfiles_simulacion.sql` | Las 5 personalidades oficiales, con comprobación del SHA-256 dentro de la base (acta 04, DC-45) |

**Diferencia con el laboratorio:** allí hubo 8 migraciones. Las 07 y 08 solo ajustaron la política `invitaciones_leer`. Aquí ese ajuste ya viene dentro de la `0004`, así que el resultado final es idéntico.

> Los archivos con el nombre antiguo (`0001_…` a `0006_…`) son copias idénticas (mismo SHA-256) que quedaron porque la sesión no podía borrar. Están en `../_LIMPIEZA-PENDIENTE.md`. **Usa solo los que empiezan por la versión.**

## Cambios futuros

1. Una migración aplicada **no se edita** (RN-XIX-02). Todo cambio es un archivo nuevo: `<version>_0007_<nombre>.sql`, y así en adelante.
2. Se prueba primero en el laboratorio o en local, se revisa por PR y una persona designada la aplica en `zentheris` (ver `Archivos_Zentheris/02_base-de-datos/guias/guia-integracion-github.md` §5).
3. Si el cambio toca el esquema, se vuelve a ejecutar `Archivos_Zentheris/02_base-de-datos/pruebas/verificacion_post_migracion.sql` y se **actualiza la huella** de abajo en el mismo PR.
4. **No** se cargan los datos de prueba ni la función `pruebas.ejecutar()` en `zentheris`. Esos viven solo en el laboratorio (`Archivos_Zentheris/02_base-de-datos/entornos/zentheris-dev/`).

## Huella esperada (comprobación final)

Ejecuta `Archivos_Zentheris/02_base-de-datos/pruebas/verificacion_post_migracion.sql`. Laboratorio (07/11/2026) y `zentheris` (08/11/2026) dan **exactamente** esto:

| Campo | Valor esperado |
|---|---|
| tablas · tablas_con_rls · politicas_public · politicas_avatares | 17 · 17 · 16 · 4 |
| escrituras_app · personalidades · bucket_publico | 0 · 5 · false |
| huella_columnas | `164005fe1191bbb401335ee7f6cba91c` |
| huella_restricciones | `7a14edc19c79a8c9bcb2cced01511449` |
| huella_indices | `cc82ae7ff1ff5becb5f5b9367340ffcb` |
| huella_politicas | `df154cd9cf5fe498ec52b0ed524f69dd` |
| huella_funciones | `f8e7a190780d3855baa74cf97d1d0cc9` |
| huella_disparadores | `7f86782d1ed7106d5c2ad0448a779403` |
| huella_personalidades | `41d047e1b234fa248761e21e289867fd` |

Si todas coinciden, el esquema es el mismo que pasó las 55 pruebas, y las pruebas de permisos (RLS) se dan por válidas sin cargar datos de prueba en el proyecto definitivo.
