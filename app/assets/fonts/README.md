# assets/fonts/

Fuentes de la app. Las abiertas van como archivos, todas en TTF, cada una con su `OFL.txt` (DC-66). Satoshi **no** se sube: cada persona la descarga de Fontshare en `satoshi/`, carpeta ignorada por git; las builds de EAS la incluyen por el `.easignore` de la raíz (DC-06).

| Carpeta | Fuente | Origen | Pesos |
|---|---|---|---|
| `inter/` | Inter 4.1 | GitHub `rsms/inter`, versión `v4.1`, archivo `Inter-4.1.zip` → `extras/ttf/` (su `LICENSE.txt` es la OFL 1.1; se copió como `OFL.txt`) | 400, 500, 600, 700 |
| `jetbrains-mono/` | JetBrains Mono 2.304 | GitHub `JetBrains/JetBrainsMono`, versión `v2.304`, archivo `JetBrainsMono-2.304.zip` → `fonts/ttf/` | 400, 500, 600, 700 |
| `satoshi/` | Satoshi | Fontshare (licencia ITF FFL) · **no está en git** | — |

Los pesos son los de `docs/diseno/tokens.json` (`fontWeight`). Descargadas el 11/11/2026.

## Satoshi: cómo instalarla en tu equipo (obligatoria para los títulos)

Satoshi es la fuente de los títulos (rol `display` de los tokens). Su licencia (ITF Free Font License) permite usarla en la app, pero **no** subirla a un repositorio público; por eso cada persona la descarga:

1. Entra a [fontshare.com/fonts/satoshi](https://www.fontshare.com/fonts/satoshi) y descarga la familia completa (botón de descarga; es gratis).
2. Descomprime el archivo y copia **`Satoshi-Bold.otf`** (carpeta `Fonts/OTF/` del paquete) en **`app/assets/fonts/satoshi/Satoshi-Bold.otf`**, con ese nombre exacto.
3. Reinicia Metro limpiando la caché: `npx expo start --clear`.
4. Comprueba: en `/catalogo-componentes` el título de tipografía dice «Satoshi sí» y en la consola ya no aparece el aviso `[fonts] Falta …`.

La carpeta `satoshi/` está en `.gitignore` (git no la sube) y **no** está en el `.easignore` de la raíz, así que las builds de EAS sí la incluyen (DC-06).

## SHA-256

```
9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e  Inter-4.1.zip (descarga)
6f6376c6ed2960ea8a963cd7387ec9d76e3f629125bc33d1fdcd7eb7012f7bbf  JetBrainsMono-2.304.zip (descarga)
288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f  inter/Inter-Bold.ttf
97ad806f526e41546d46365bb3a393145f75b7b1568913db74549ad8b8dba872  inter/Inter-Medium.ttf
40d692fce188e4471e2b3cba937be967878f631ad3ebbbdcd587687c7ebe0c82  inter/Inter-Regular.ttf
78a843fade9d4612a5567302fb595b56976eb5fcebf4fea5a5912d638bafcde3  inter/Inter-SemiBold.ttf
262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a  inter/OFL.txt
5590990c82e097397517f275f430af4546e1c45cff408bde4255dad142479dcb  jetbrains-mono/JetBrainsMono-Bold.ttf
31c92d01a8a08528b718a43addf0ad3df0af2ca4b7b3290a452f70f358e14d3d  jetbrains-mono/JetBrainsMono-Medium.ttf
a0bf60ef0f83c5ed4d7a75d45838548b1f6873372dfac88f71804491898d138f  jetbrains-mono/JetBrainsMono-Regular.ttf
1b3bfa1ed5665a4ce3f9feb68d2d4e40e70bf8b4b7d9a3edd418f321b4e166a0  jetbrains-mono/JetBrainsMono-SemiBold.ttf
30f0c136e3c88e422d0791acd97238870f9054a9729bc34cf2ff0d4ed8cac4ad  jetbrains-mono/OFL.txt
```
