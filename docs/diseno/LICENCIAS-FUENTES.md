# Licencias de tipografías e íconos

Revisión: 2026-11-02. Nivel de evidencia: **documentado en fuentes públicas**, no es asesoría legal. Antes de publicar la app, Nicolás o el equipo deben conservar el texto de licencia que viene con cada descarga oficial.

| Recurso | Licencia | Uso en la app (Expo) | Redistribución de archivos | Fuente consultada |
|---|---|---|---|---|
| **Inter** (Rasmus Andersson) | SIL Open Font License 1.1 | Permitido, también comercial | Permitida con el texto OFL; no vender la fuente sola | github.com/rsms/inter |
| **JetBrains Mono** | SIL Open Font License 1.1 | Permitido | Permitida con el texto OFL | CTAN (jetbrainsmono-otf), copias del archivo LICENSE |
| **Satoshi** (Indian Type Foundry, Fontshare) | ITF Free Font License (FFL) v1.0, 20-01-2021 | Permitido para uso personal y comercial «in any media (including … Mobile, Digital, Apps … OEM)» | **Restringida**: no se puede subir a un servidor público ni compartir por redes P2P; tampoco modificar el archivo original | Copia del texto FFL en GitHub y nota de licencias de un tercero; la página oficial fontshare.com/licenses/itf-ffl no se pudo leer (contenido generado con JavaScript) |
| **Lucide** (íconos) | ISC (derivados de Feather: MIT) | Permitido | Permitida con el aviso | `licencias/LUCIDE-LICENSE.txt` |

## Consecuencias para Zentheris

1. **Satoshi no se incluye en este paquete ni en el ZIP**, y **no debe subirse al repositorio `Thomasvtf/Zentheris-Prototype`: Nicolás confirmó el 2026-11-02 que es público**. Cada desarrollador la descarga de fontshare.com. Antes de cargarla en la app, confirmen que el repositorio es privado o que la FFL permite incluirla dentro del binario (la FFL nombra «Apps» y «OEM» como usos permitidos).
2. Inter y JetBrains Mono se pueden incluir en `assets/fonts/` del proyecto con su archivo `OFL.txt`.
3. Antes de la entrega oficial, verificar la FFL vigente en fontshare.com y guardar una copia junto al código. Pendiente de confirmar por Nicolás: no hubo acceso de lectura a la página oficial.

## Actualización 2026-11-02 (v3.2)

- **Repositorio público (confirmado por Nicolás):** la FFL restringe subir el archivo a servidores públicos. No se versiona ningún archivo de Satoshi en el repositorio. Añadir `Satoshi*` y la carpeta de fuentes de Satoshi a `.gitignore`; cada desarrollador descarga la fuente de fontshare.com y la coloca en una carpeta local ignorada. Inter y JetBrains Mono sí pueden versionarse con su `OFL.txt`.
- **Empaquetado de la app:** Nicolás confirmó que el uso de Satoshi en la app está permitido (decisión suya, 2026-11-02). La página oficial de Fontshare sigue sin poder leerse desde esta sesión, así que el texto vigente de la FFL debe conservarse junto al código antes de la entrega. Cómo cargar la fuente en el build (archivo local ignorado por git, o descarga en el paso de build) queda por decidir con el repositorio; sin revisar el código no se propone una solución concreta.
- No es asesoría legal.
