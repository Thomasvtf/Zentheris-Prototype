# StepIndicator

Progreso del onboarding: paso 1 = nombre del hogar y tipo de vivienda; paso 2 = zonas. Figma: `Navegacion/Indicador-pasos` (4111:412). **Aprobado v4.5** (D-SD-04, 07/11/2026).

| Prop | Tipo | Notas |
|---|---|---|
| `paso` | número | Texto «Paso n de N» siempre visible (no solo color). |
| `total` | número | 2 en el MVP. |

Barras de 4 px, `z-radius-full`: completadas `z-color-accent-primary`, pendientes `z-color-border-medium`.
