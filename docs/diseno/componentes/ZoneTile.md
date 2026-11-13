# ZoneTile

Zona del catálogo de 9 para el paso 2 del onboarding (RN-X-02, RN-X-09). Figma: `Control/Zona-seleccionable` (4110:450). **Propuesto v4.5**.

| Prop | Tipo | Notas |
|---|---|---|
| `zona` | Baño · Cocina · Cuarto de servicio · Dormitorio · Garaje · Lavandería · Oficina · Sala · Terraza | Ícono por zona (Lucide probable). |
| `estado` | `'disponible' \| 'seleccionada' \| 'basica' \| 'deshabilitada'` | Cada estado lleva ícono **y** palabra: Agregar · Elegida (check) · Básica (candado) · No disponible. |

## Reglas
- Apartamento, casa, dúplex y casa campestre: las 4 básicas (Baño, Cocina, Dormitorio, Sala) aparecen como `basica`, marcadas y bloqueadas (D17).
- Apartaestudio: solo básicas, Oficina y Lavandería; de 3 a 5 zonas, al menos 3 básicas; con 5 elegidas el resto pasa a `deshabilitada` y se muestra un aviso.
- Cambiar el tipo de vivienda ajusta la selección y muestra un aviso (RN-X-09 d). El backend valida igual (`ZONAS_NO_PERMITIDAS`, `ZONAS_BASICAS_FALTANTES`, `CANTIDAD_ZONAS_INVALIDA`, `ZONAS_DUPLICADAS`).
- Íconos de Lavandería, Terraza, Garaje y Cuarto de servicio: **candidatos** (washing-machine, fence, car, door-closed), en uso para revisión, sin aprobar.
