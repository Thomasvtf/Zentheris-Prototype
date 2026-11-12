/**
 * Formato numérico es-CO (RN-XII-08), con las firmas de docs/diseno/componentes/index.d.ts.
 *
 * RN-XII-08: coma decimal y punto de miles («2,40 kW», «$14.400»); en cards y ejes los miles
 * se abrevian con «k» minúscula («$6,5k»); los porcentajes llevan espacio («34 %»); kW con
 * 2 decimales, kWh con 1 y COP sin decimales.
 *
 * Se formatea a mano, sin `Intl`, para que el resultado sea el mismo en Hermes, en la web y
 * en las pruebas. Decisiones de Nicolás del 11/11/2026 para casos que la regla no define:
 * - «k»: 1 decimal y se quita el «,0» (Metric.md: «$6,5k», «$28k»); también para millones
 *   («$1.250k»); por debajo de 1.000 no se abrevia.
 * - Negativos con guion ASCII («-12 %»); redondeo de la mitad alejándose de cero.
 * - `formatNumber` sin `decimales` usa 0.
 * - `null` = sin datos → «—» (index.d.ts, Metric.md); cero se muestra como cero.
 */

/** Decimales por unidad (RN-XII-08). */
export const DECIMALES = { kW: 2, kWh: 1, COP: 0, '%': 0 } as const;

const NO_DATA = '—';
/** Espacio sin ruptura entre la cifra y «%» (RN-XII-08: «34 %»). */
const NBSP = String.fromCharCode(0x00a0);

/** Redondea a `decimales` alejándose de cero en la mitad, sin errores de coma flotante. */
function roundHalfAwayFromZero(value: number, decimales: number): number {
  const sign = value < 0 ? -1 : 1;
  const shifted = Number(`${Math.abs(value)}e${decimales}`);
  return sign * Number(`${Math.round(shifted)}e-${decimales}`);
}

function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/** Cifra ya redondeada → texto es-CO (sin signo). */
function toEsCo(absValue: number, decimales: number): string {
  const [intPart, fracPart] = absValue.toFixed(decimales).split('.');
  return fracPart ? `${groupThousands(intPart)},${fracPart}` : groupThousands(intPart);
}

function signed(value: number, text: string): string {
  return value < 0 ? `-${text}` : text;
}

/** Miles con «k»: 1 decimal y sin «,0» final («6,5k», «28k», «1.250k»). */
function abbreviateThousands(value: number): string {
  const thousands = roundHalfAwayFromZero(value / 1000, 1);
  const text = toEsCo(Math.abs(thousands), 1).replace(/,0$/, '');
  return signed(thousands, `${text}k`);
}

/** Número es-CO con `decimales` (0 por defecto). Con `abreviar`, miles con «k». */
export function formatNumber(
  v: number | null,
  decimales: number = 0,
  opts?: { abreviar?: boolean },
): string {
  if (v === null) return NO_DATA;
  if (opts?.abreviar && Math.abs(v) >= 1000) return abbreviateThousands(v);
  const rounded = roundHalfAwayFromZero(v, decimales);
  return signed(rounded, toEsCo(Math.abs(rounded), decimales));
}

/** Pesos colombianos sin decimales («$14.400»); con `abreviar`, «$6,5k». */
export function formatCOP(v: number | null, opts?: { abreviar?: boolean }): string {
  if (v === null) return NO_DATA;
  const text = formatNumber(Math.abs(v), DECIMALES.COP, opts);
  return roundHalfAwayFromZero(v, DECIMALES.COP) < 0 ? `-$${text}` : `$${text}`;
}

/** Porcentaje con espacio sin ruptura («34 %»); 0 decimales por defecto. */
export function formatPercent(v: number | null, decimales: number = DECIMALES['%']): string {
  if (v === null) return NO_DATA;
  return `${formatNumber(v, decimales)}${NBSP}%`;
}
