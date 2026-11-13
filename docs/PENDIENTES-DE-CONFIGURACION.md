# Pendientes de configuración · lo que se ajusta fuera del código

Versión 1 · 12/11/2026. Ajustes de GitHub y de los servicios externos que no se hacen con un commit. Las tareas de código de la refactorización están en `PENDIENTES-DE-REFACTORIZACION.md`.

| # | Quién | Cuándo | Tarea | Por qué | Hecho |
|---|---|---|---|---|---|
| 1 | Thomas (administrador del repositorio) | Antes de fusionar la cadena de refactorización (PR 1 a 6) | En GitHub, **Settings → General → Pull Requests:** dejar activada solo **«Allow merge commits»** y desactivar «Allow squash merging» y «Allow rebase merging». | DC-68: la cadena se fusiona con merge commit para que cada commit conserve su identificador. Hoy el repositorio permite las tres opciones. | [ ] |
| 2 | Thomas | Junto con la #1 | En la misma página, activar **«Automatically delete head branches»**. | DC-68: la rama ya fusionada se borra, y GitHub cambia solo la base del PR siguiente de la cadena a `main`. Hoy no se borran. | [ ] |
| 3 | Thomas | Junto con la #1 | **Settings → Rules → Rulesets** (o «Branch protection rules») para `main`: exigir PR antes de fusionar, con **1 aprobación** de otra persona. | DC-61: los PR hacia `main` los aprueba otra persona. Hoy `main` no está protegida y rige solo por acuerdo del equipo. El CI obligatorio se agrega después, cuando el CI de `main` quede en verde (DC-61). | [ ] |
| 4 | Quien cree el servicio de Render | Al crear el servicio de la API en Render | Poner como ruta de salud (**Health Check Path**) **`/api/v1/salud`**. Si el repositorio llega a tener `render.yaml`, va como `healthCheckPath: /api/v1/salud`. | Tarea #30 de `PENDIENTES-DE-REFACTORIZACION.md`: el PR 3 quita `/` y `/salud/bd`; con otra ruta, Render marcaría el servicio como caído. Hoy no hay cuenta de Render ni `render.yaml`. | [ ] |
