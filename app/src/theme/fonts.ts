/**
 * Fuentes de la app (DC-06 y DC-66).
 *
 * Inter y JetBrains Mono están en assets/fonts/ (TTF con su OFL.txt). Satoshi no se sube a
 * git: cada persona la pone en assets/fonts/satoshi/Satoshi-Bold.otf. Si falta, el rol
 * `display` usa Inter Bold (DC-06).
 */
import * as Font from 'expo-font';

type FontRole = 'display' | 'body' | 'data';
type FontWeight = '400' | '500' | '600' | '700';

/** Satoshi es opcional: Metro la trata como dependencia opcional porque va en try/catch. */
function loadOptionalSatoshi(): number | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('../../assets/fonts/satoshi/Satoshi-Bold.otf');
  } catch {
    return null;
  }
}

const satoshiBold = loadOptionalSatoshi();

/** Archivos que se cargan con expo-font, por nombre de familia. */
export const fontFiles: Record<string, number> = {
  'Inter-Regular': require('../../assets/fonts/inter/Inter-Regular.ttf'),
  'Inter-Medium': require('../../assets/fonts/inter/Inter-Medium.ttf'),
  'Inter-SemiBold': require('../../assets/fonts/inter/Inter-SemiBold.ttf'),
  'Inter-Bold': require('../../assets/fonts/inter/Inter-Bold.ttf'),
  'JetBrainsMono-Regular': require('../../assets/fonts/jetbrains-mono/JetBrainsMono-Regular.ttf'),
  'JetBrainsMono-Medium': require('../../assets/fonts/jetbrains-mono/JetBrainsMono-Medium.ttf'),
  'JetBrainsMono-SemiBold': require('../../assets/fonts/jetbrains-mono/JetBrainsMono-SemiBold.ttf'),
  'JetBrainsMono-Bold': require('../../assets/fonts/jetbrains-mono/JetBrainsMono-Bold.ttf'),
  ...(satoshiBold !== null ? { 'Satoshi-Bold': satoshiBold } : {}),
};

/** Indica si Satoshi está disponible en esta build. */
export const hasSatoshi = satoshiBold !== null;

if (__DEV__ && !hasSatoshi) {
  // Solo en desarrollo: Satoshi no está en git (licencia ITF FFL, DC-06) y cada persona la descarga.
  console.warn(
    '[fonts] Falta app/assets/fonts/satoshi/Satoshi-Bold.otf: los títulos usan Inter Bold. ' +
      'Descárgala de fontshare.com siguiendo app/assets/fonts/README.md.',
  );
}

const WEIGHT_SUFFIX: Record<FontWeight, string> = {
  '400': 'Regular',
  '500': 'Medium',
  '600': 'SemiBold',
  '700': 'Bold',
};

/** Familia que se pone en `fontFamily` para un rol y un peso de los tokens. */
export function fontFamilyFor(role: FontRole, weight: FontWeight): string {
  if (role === 'display') return hasSatoshi ? 'Satoshi-Bold' : 'Inter-Bold';
  const base = role === 'data' ? 'JetBrainsMono' : 'Inter';
  return `${base}-${WEIGHT_SUFFIX[weight]}`;
}

/** Carga todas las fuentes. Se llama una vez al iniciar la app. */
export async function loadFonts(): Promise<void> {
  await Font.loadAsync(fontFiles);
}
