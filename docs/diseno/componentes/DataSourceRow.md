# DataSourceRow

Fila de la pantalla Fuentes de datos (antes Medidores), solo lectura (RN-XVI-06). Figma: `Configuracion/Fuente-datos` (4113:519). **Propuesto v4.5**.

| Prop | Tipo | Notas |
|---|---|---|
| `nombre` | texto | «Fuente principal [nombre del hogar]» o «Sensor [zona]». |
| `detalle` | texto | Zona o «Suma de los sensores activos». |
| `valor` | número \| null | kW de la última hora completa (2 decimales). `null` = «—», nunca 0. |
| `estado` | `'activo' \| 'pausado' \| 'sin_datos'` | Calculado; «Sin datos» = no llegó la lectura de la última hora completa. Sin amarillo ni rojo: no es severidad. |
| `mostrarValor` | booleano | `false` para miembros sin «ver consumo actual» (RN-XVII-01, N4): se ven nombre y estado. |

Sin botones «+», «Agregar medidor» ni ícono «?»: no hay gestión de dispositivos en el MVP.
