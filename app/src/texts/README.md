# texts/

- `catalogo.es-CO.json`: **copia exacta** de `docs/textos/catalogo.es-CO.json`; el CI compara su SHA-256. Se edita en `docs/` y se vuelve a copiar.
- `index.ts`: `t(clave, vars)` y `plural(clave, n, vars)` (formas zero, one y other).
- **Ejemplo:** `t('formato.saludo.manana', { nombre })`, `plural('formato.vence.dias', 3)`.
- **No va:** textos de interfaz escritos a mano. Si falta una clave, `t()` devuelve la clave y se marca en el PR.
