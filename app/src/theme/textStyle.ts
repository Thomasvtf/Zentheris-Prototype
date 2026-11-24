/** Estilo de texto de React Native a partir de un rol tipográfico de los tokens. */
import type { TextStyle } from 'react-native';

import { fontFamilyFor } from './fonts';
import { typography } from './tokens';

export type TypographyName = keyof typeof typography;

/** Familia, tamaño y alto de línea del rol `name` (los colores van aparte, con tokens). */
export function textStyle(name: TypographyName): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
  };
}
