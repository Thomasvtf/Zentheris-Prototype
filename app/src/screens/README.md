# screens/

**Una carpeta por pantalla:** `<Nombre>/<Nombre>.tsx` (vista) + `use<Nombre>Data.ts` (hook con 4 estados: cargando, error, sin permiso y datos). Ver `app/CLAUDE.md`.

- **Va:** la composición de la pantalla con componentes del sistema de diseño y su hook de datos.
- **No va:** llamadas `fetch` directas (se usa `src/api/`), textos escritos a mano (se usa `t()`) ni colores fijos (se usan tokens).
- **Ejemplo:** `ComponentCatalog/ComponentCatalogScreen.tsx` (interna, solo en desarrollo; no tiene hook porque no pide datos).

Las pantallas sueltas que ya existen (`DashboardScreen.tsx` y las de las ramas del equipo) se mueven a su carpeta al aplicar las librerías a cada una, con aprobación (DC-63).
