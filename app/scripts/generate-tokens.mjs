#!/usr/bin/env node
/**
 * Genera app/src/theme/tokens.ts desde docs/diseno/tokens.json (fuente única de los tokens).
 *
 * Uso (desde app/):
 *   node scripts/generate-tokens.mjs           escribe src/theme/tokens.ts
 *   node scripts/generate-tokens.mjs --check   falla (código 1) si tokens.ts no está al día
 *
 * Sin dependencias: solo Node.
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = resolve(APP_DIR, '../docs/diseno/tokens.json');
const TARGET = resolve(APP_DIR, 'src/theme/tokens.ts');

const tokens = JSON.parse(readFileSync(SOURCE, 'utf8'));

const px = (value) => Number(String(value).replace(/px$/, ''));
const key = (name, prefix) => name.replace(prefix, '');

function resolveColors(list) {
  const raw = Object.fromEntries(list.map((t) => [t.name, t.value]));
  const resolveOne = (value, seen = new Set()) => {
    const match = /^\{(.+)\}$/.exec(value);
    if (!match) return value;
    const ref = match[1];
    if (seen.has(ref) || !(ref in raw)) throw new Error(`Referencia de color inválida: ${value}`);
    seen.add(ref);
    return resolveOne(raw[ref], seen);
  };
  return Object.fromEntries(list.map((t) => [key(t.name, 'z-color-'), resolveOne(t.value)]));
}

function scale(list, prefix, toValue = px) {
  return Object.fromEntries(list.map((t) => [key(t.name, prefix), toValue(t.value)]));
}

function typography(groups) {
  const out = {};
  for (const group of groups) {
    for (const style of group.styles) {
      const fontSize = px(style.fontSize);
      const entry = { family: group.family, fontSize, fontWeight: String(style.fontWeight) };
      if (style.lineHeight !== undefined) {
        entry.lineHeight = Math.round(fontSize * style.lineHeight * 100) / 100;
      }
      out[style.name] = entry;
    }
  }
  return out;
}

const sections = {
  colors: resolveColors(tokens.color.tokens),
  spacing: scale(tokens.spacing.tokens, 'z-space-'),
  radius: scale(tokens.radius.tokens, 'z-radius-'),
  sizes: scale(tokens.size.tokens, 'z-size-'),
  fontSizes: scale(tokens.fontSize.tokens, 'z-font-size-'),
  fontWeights: scale(tokens.fontWeight.tokens, 'z-font-weight-', String),
  lineHeights: scale(tokens.lineHeight.tokens, 'z-font-lineHeight-', Number),
  typography: typography(tokens.type.groups),
};

const docs = {
  colors: 'Colores (tema oscuro único). Las referencias {z-color-…} ya están resueltas.',
  spacing: 'Espacios en dp (escala de 4 a 64).',
  radius: 'Radios en dp.',
  sizes: 'Medidas de componentes y layout en dp (grid-columns sin unidad).',
  fontSizes: 'Tamaños de letra primitivos en dp. Se usan los estilos de `typography`.',
  fontWeights: 'Pesos de letra.',
  lineHeights: 'Interlineados de referencia (proporción).',
  typography: 'Estilos de texto. `family` es el rol (display, body o data); `lineHeight` ya está en dp.',
};

const lines = [
  '// GENERADO por app/scripts/generate-tokens.mjs desde docs/diseno/tokens.json. No editar a mano.',
  `// Fuente: ${tokens.meta.source} · versión ${tokens.version}.`,
  '',
];
for (const [name, value] of Object.entries(sections)) {
  lines.push(`/** ${docs[name]} */`);
  lines.push(`export const ${name} = ${JSON.stringify(value, null, 2)} as const;`);
  lines.push('');
}
lines.push(`export const fontFamilyRoles = ${JSON.stringify(tokens.type.families, null, 2)} as const;`, '');
const output = lines.join('\n');

if (process.argv.includes('--check')) {
  const current = existsSync(TARGET) ? readFileSync(TARGET, 'utf8').replace(/\r\n/g, '\n') : '';
  if (current !== output) {
    console.error('src/theme/tokens.ts no está al día con docs/diseno/tokens.json.');
    console.error('Ejecuta: node scripts/generate-tokens.mjs');
    process.exit(1);
  }
  console.log('tokens.ts al día con docs/diseno/tokens.json · OK');
} else {
  writeFileSync(TARGET, output, 'utf8');
  console.log(`Escrito ${TARGET}`);
}
