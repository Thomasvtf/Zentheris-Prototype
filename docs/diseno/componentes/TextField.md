# TextField

Campo de formulario con etiqueta siempre visible, para registro, contraseña, meta y tarifa. Figma: `Control/Campo-texto` (507:920).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `etiqueta` | texto | Siempre visible. Opcional se marca en la etiqueta: «Celular (opcional)». |
| `estado` | `'default' \| 'activo' \| 'error' \| 'deshabilitado'` | |
| `placeholder` | texto | Solo como ejemplo («Ej. 4»), en `z-color-text-muted`. |
| `valor`, `tipo`, `sufijo` | | `sufijo` para unidades fijas («kWh»). |
| `error` | texto | Viene del código de error del contrato (`CONTRASENA_NO_CUMPLE_REGLAS`…). |
| `ayuda` | texto | Texto de ayuda bajo el campo. |

## Tokens
Caja 48 (`z-size-button-height`), radio `z-radius-md`, fondo `z-color-background-surfaceAlt`, borde `z-color-border-medium`; activo `z-color-border-accent`; error `z-color-border-error` + mensaje `z-color-text-error` con ícono circle-x 16; deshabilitado `z-color-state-disabled-*`. Etiqueta `body-s-medium`; valor `body-m-regular`; mensajes `body-xs-regular`.

## Pendiente
Contador de caracteres y lista de requisitos de contraseña (cumplido/no cumplido con ícono + texto) faltan en Figma.
