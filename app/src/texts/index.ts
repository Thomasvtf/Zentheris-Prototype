/**
 * Textos de la app desde catalogo.es-CO.json (copia exacta de docs/textos; el CI compara
 * su SHA-256). Ningún texto de interfaz se escribe a mano.
 *
 * - Variables: se escriben {nombre}; quien llama las pasa ya con formato es-CO (RN-XII-08).
 * - Plurales: un texto con claves zero/one/other se elige por n (0 / 1 / otros), según
 *   `_meta.plurales` del catálogo.
 * - Si falta una clave, se devuelve la propia clave para que se vea en pantalla y se
 *   marque en el PR (app/CLAUDE.md: no se inventan textos).
 */
import catalog from './catalogo.es-CO.json';

type Vars = Record<string, string | number>;
type PluralForms = { zero: string; one: string; other: string };

function lookup(key: string): unknown {
  return key.split('.').reduce<unknown>((node, part) => {
    if (node !== null && typeof node === 'object' && part in node) {
      return (node as Record<string, unknown>)[part];
    }
    return undefined;
  }, catalog);
}

function interpolate(text: string, vars: Vars = {}): string {
  return text.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

function isPlural(value: unknown): value is PluralForms {
  return (
    value !== null &&
    typeof value === 'object' &&
    ['zero', 'one', 'other'].every((form) => typeof (value as Record<string, unknown>)[form] === 'string')
  );
}

/** Texto de la clave `clave` con sus variables. Si falta, devuelve la clave. */
export function t(clave: string, vars?: Vars): string {
  const value = lookup(clave);
  if (typeof value !== 'string') {
    if (__DEV__) console.warn(`[texts] falta la clave «${clave}» o es plural (usa plural())`);
    return clave;
  }
  return interpolate(value, vars);
}

/** Texto plural de `clave` para `n` (0 → zero, 1 → one, otros → other); rellena {n}. */
export function plural(clave: string, n: number, vars?: Vars): string {
  const value = lookup(clave);
  if (!isPlural(value)) {
    if (__DEV__) console.warn(`[texts] la clave «${clave}» no es plural`);
    return clave;
  }
  const form = n === 0 ? value.zero : n === 1 ? value.one : value.other;
  return interpolate(form, { ...vars, n });
}
