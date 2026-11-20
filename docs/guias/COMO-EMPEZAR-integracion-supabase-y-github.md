# Cómo empezar: llevar lo nuevo a GitHub y a Supabase

Lectura de 5 minutos. Esta guía vale igual en el repositorio y en la carpeta `Archivos_Zentheris`: cada documento se nombra con su ruta en el repositorio y, entre paréntesis, su ruta en la carpeta.

## Qué se sube y qué no

A GitHub solo va el contexto que Claude Code necesita para programar: los archivos `CLAUDE.md` (`CLAUDE.md`, `app/CLAUDE.md`, `api/CLAUDE.md` y `supabase/CLAUDE.md`; en la carpeta, `11_guias-de-desarrollo/claude-code/`) y la carpeta `docs/` con las fuentes vigentes. El resto de `Archivos_Zentheris` (históricos, informes, Figma, pendientes) se queda en la carpeta del equipo.

La carpeta es el original y el repositorio es la copia (DC-57 y DC-70). Qué archivo corresponde a cuál y si están sincronizados está en `MANIFIESTO.md` (solo en la carpeta).

Nunca subas claves, contraseñas ni los archivos de la fuente Satoshi: el repositorio es público.

## Paso 1 · GitHub: lo ya hecho y cómo se sigue

El contexto ya está en `main`: la refactorización se fusionó el 12/11/2026 (PR #1 a #8). Para llevar un cambio nuevo de documentación:

1. Edítalo primero en la carpeta, que es el original.
2. Desde `main`, crea una rama `docs/<tema>`. Las ramas usan el formato `<tipo>/<descripcion>`, sin `chore` (DC-59).
3. Copia el archivo a su ruta en el repositorio, comprueba que quedó igual (SHA-256) y abre un pull request hacia `main`. Lo aprueba otra persona del equipo (DC-61). Ningún commit ni PR lleva a Claude como coautor (DC-60).
4. Pide a quien administre el repositorio que proteja `main` (nadie sube directo) y que configure la aprobación de otra persona en los PR hacia `main`.

## Paso 2 · Supabase

1. La base ya está creada: proyecto `zentheris` (organización «Zentheris»), con las 6 migraciones aplicadas el 08/11/2026. No hay que crear ni inventariar nada.
2. Las migraciones están en `supabase/migrations/` (en la carpeta, `02_base-de-datos/migraciones/`). Especificación vigente: `docs/supabase/especificacion-supabase-v1.md` (`02_base-de-datos/especificacion-supabase-v1.md`, v1.1).
3. Si alguna clave estuvo en Notion, rótenla y guárdenla en un gestor de contraseñas.
4. Cada persona pone sus valores en su `.env` local, que no se sube.

## Paso 3 · Empezar a programar

Abre Claude Code en el repositorio y lee `CLAUDE.md` y `docs/guias/GUIA-DEL-EQUIPO.md` (`11_guias-de-desarrollo/GUIA-DEL-EQUIPO.md`). El plan de sesiones está en la Guía 3 §11: `docs/guias/GUIA-3-backend-y-arquitectura.md` (`11_guias-de-desarrollo/guias-detalle/GUIA-3-backend-y-arquitectura.md`). Cada sesión es una subrama y un pull request.

## Si tienes dudas

- Qué construir en la app: `docs/guias/GUIA-2-interfaces-app.md` (`11_guias-de-desarrollo/guias-detalle/GUIA-2-interfaces-app.md`; lectura corta: `11_guias-de-desarrollo/GUIA-2-interfaces-app-resumen.md`).
- Qué construir en el backend: `docs/guias/GUIA-3-backend-y-arquitectura.md` (`11_guias-de-desarrollo/guias-detalle/GUIA-3-backend-y-arquitectura.md`; lectura corta: `11_guias-de-desarrollo/GUIA-3-backend-y-arquitectura-resumen.md`).
- Qué falta: `PENDIENTES.md` (solo en la carpeta `Archivos_Zentheris`; la lista única de pendientes).
