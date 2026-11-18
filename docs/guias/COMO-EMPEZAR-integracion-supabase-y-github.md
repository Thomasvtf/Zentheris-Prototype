# Cómo empezar: llevar lo nuevo a GitHub y a Supabase

Lectura de 5 minutos. Hazlo **solo cuando Nicolás autorice el paso a desarrollo**.

## Qué se sube y qué no

A GitHub solo va el contenido de `paquete-repo/`: los archivos `CLAUDE.md` y la carpeta `docs/`. Son el contexto que Claude Code necesita para programar. El resto de `Archivos_Zentheris` (históricos, informes, Figma, pendientes) se queda en la carpeta del equipo.

Nunca subas claves, contraseñas ni los archivos de la fuente Satoshi: el repositorio es público.

## Paso 1 · GitHub (una vez)

1. Desde `main`, crea la rama `docs/contexto-del-proyecto`. Las ramas de la refactorización usan el formato `<tipo>/<descripcion>`, sin `chore` (decisión del 10/11/2026).
2. Copia en la raíz del repositorio lo que hay dentro de `paquete-repo/` (respeta las carpetas: `app/CLAUDE.md` va en `app/`, y así).
3. Haz commit y abre un pull request hacia `main`. Se fusiona después de hablar con el equipo y con la aprobación de otra persona (opción C). Ningún commit ni PR lleva a Claude como coautor.
4. Pide a quien administre el repositorio que proteja `main` (nadie sube directo) y que configure la aprobación de otra persona en los PR hacia `main`.

## Paso 2 · Supabase (una vez)

1. La base ya está creada: proyecto `zentheris` (organización «Zentheris»), con las 6 migraciones aplicadas el 08/11/2026. No hay que crear ni inventariar nada.
2. Las migraciones están en `02_base-de-datos/migraciones/` y se copian a `supabase/migrations/` del repositorio. Especificación vigente: `02_base-de-datos/especificacion-supabase-v1.md` (v1.1).
3. Si alguna clave estuvo en Notion, rótenla y guárdenla en un gestor de contraseñas.
4. Cada persona pone sus valores en su `.env` local, que no se sube.

## Paso 3 · Empezar a programar

Abre Claude Code en el repositorio y sigue el plan de sesiones de `paquete-repo/LEEME-paquete-repo.md`. Cada sesión es una subrama y un pull request.

## Si tienes dudas

- Qué construir en la app: `GUIA-2-interfaces-app.md`.
- Qué construir en el backend: `GUIA-3-backend-y-arquitectura.md`.
- Qué falta y quién lo hace: `PENDIENTES-GENERAL-antes-de-backend.md`.
