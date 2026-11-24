/**
 * Barra inferior (BottomNav.md; Figma `Navegacion/Barra-inferior` 4083:3427).
 *
 * - Cinco secciones con íconos de Lucide: house, clock (DC-13), layout-grid, lightbulb y settings.
 * - Alto `bottomNav-height` (64) más el área segura inferior; fondo `background-surface` y borde
 *   superior `border-subtle`.
 * - Inactiva: ícono 24 en contorno y etiqueta en `text-muted`. Activa (Figma A3.1, A4.3, A5.1, A6.1,
 *   A7.1): contenedor 44 × 32 `accent-soft` con `radius.sm`, ícono `accent-primary` y etiqueta
 *   `text-accent`. Principal, Zonas y Consejos van rellenos; Historial y Configuración, en contorno.
 *   La casa activa es la forma de Figma (relleno con la puerta recortada), que Lucide no trae.
 *   Etiquetas `body-xs-medium-10`.
 * - Las subpantallas de Configuración y el catálogo de componentes no son pestañas (`href: null`)
 *   y ocultan la barra, como en Figma A7.2 a A9.6.
 *
 * TODO(pendiente: sesión 10): al crear los grupos (auth), (onboarding) y (tabs), las pestañas pasan a
 * `(tabs)/_layout.tsx` y las subpantallas a un Stack encima (GUIA-2 §Navegación).
 */
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Tabs } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { Clock, House, LayoutGrid, Lightbulb, Settings } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';

import { colors, fontFamilyFor, radius, sizes, spacing, typography } from '@/theme';
import { t } from '@/texts';

const ICON_SIZE = 24;
const LABEL = typography['body-xs-medium-10'];

/** Casa activa de Figma (`Icono/Nav/Principal`, opción 1): silueta rellena con la puerta recortada. */
const HOUSE_FILLED =
  'M30.74 16.53V25.88L33.78 26C34.37 26 34.93 25.78 35.35 25.38C35.77 24.99 36 24.45 36 23.89V14.42C36 14.12 35.93 13.81 35.79 13.53C35.66 13.26 35.46 13.01 35.21 12.81L27.43 6.5C27.03 6.18 26.53 6 26 6C25.47 6 24.97 6.18 24.57 6.5L16.79 12.81C16.54 13.01 16.34 13.26 16.21 13.53C16.07 13.81 16 14.12 16 14.42V23.89C16 24.45 16.23 24.99 16.65 25.38C17.07 25.78 17.63 26 18.22 26L21.26 25.88V16.53C21.26 16.22 21.43 15.92 21.73 15.7C22.02 15.48 22.42 15.36 22.84 15.36H29.16C29.58 15.36 29.98 15.48 30.27 15.7C30.57 15.92 30.74 16.22 30.74 16.53Z';

function HouseFilled({ color }: { color: string }) {
  return (
    <Svg width={ICON_SIZE} height={ICON_SIZE} viewBox="14 4 24 24">
      <Path d={HOUSE_FILLED} fill={color} stroke={color} strokeWidth={2} strokeLinejoin="round" />
    </Svg>
  );
}

/** Casa inactiva de Figma: silueta en contorno con la puerta rellena (Lucide la dibuja hueca). */
const HOUSE_OUTLINE =
  'M33.78 26C34.37 26 34.93 25.78 35.35 25.38C35.77 24.99 36 24.45 36 23.89V14.42C36 14.12 35.93 13.81 35.79 13.53C35.66 13.26 35.46 13.01 35.21 12.81L27.43 6.5C27.03 6.18 26.53 6 26 6C25.47 6 24.97 6.18 24.57 6.5L16.79 12.81C16.54 13.01 16.34 13.26 16.21 13.53C16.07 13.81 16 14.12 16 14.42V23.89C16 24.45 16.23 24.99 16.65 25.38C17.07 25.78 17.63 26 18.22 26H33.78Z';
const HOUSE_DOOR =
  'M21.26 25.88V16.53C21.26 16.22 21.43 15.92 21.73 15.7C22.02 15.48 22.42 15.36 22.84 15.36H29.16C29.58 15.36 29.98 15.48 30.27 15.7C30.57 15.92 30.74 16.22 30.74 16.53V25.88Z';

function HouseOutline({ color }: { color: string }) {
  return (
    <Svg width={ICON_SIZE} height={ICON_SIZE} viewBox="14 4 24 24">
      <Path d={HOUSE_OUTLINE} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
      <Path d={HOUSE_DOOR} fill={color} stroke={color} strokeWidth={2} strokeLinejoin="round" />
    </Svg>
  );
}

interface NavIconProps {
  icono: LucideIcon;
  focused: boolean;
  /** Activa: relleno (Principal, Zonas, Consejos) o contorno (Historial, Configuración). */
  relleno: boolean;
}

/** Ícono de la pestaña; la activa va dentro del contenedor `accent-soft` de 44 × 32. */
function NavIcon({ icono: Icono, focused, relleno }: NavIconProps) {
  const color = focused ? colors['accent-primary'] : colors['text-muted'];
  return (
    <View style={[styles.iconBox, focused && styles.iconBoxActive]}>
      {focused && relleno && Icono === House ? (
        <HouseFilled color={color} />
      ) : !focused && Icono === House ? (
        <HouseOutline color={color} />
      ) : (
        <Icono size={ICON_SIZE} color={color} fill={focused && relleno ? color : 'none'} />
      )}
    </View>
  );
}

/** Opciones de una pestaña visible: etiqueta del catálogo e ícono. */
function tab(labelKey: string, icono: LucideIcon, relleno: boolean) {
  const title = t(labelKey);
  return {
    title,
    tabBarAccessibilityLabel: title,
    tabBarIcon: ({ focused }: { focused: boolean }) => <NavIcon icono={icono} focused={focused} relleno={relleno} />,
  };
}

/** Rutas que no son pestañas: no aparecen en la barra y la ocultan. */
const HIDDEN = { href: null, tabBarStyle: { display: 'none' as const } };

export default function Layout() {
  const insets = useSafeAreaInsets();
  return (
    <>
      <StatusBar style="light" />
      <Tabs
        backBehavior="history"
        screenOptions={{
          headerShown: false,
          tabBarLabelPosition: 'below-icon',
          tabBarActiveTintColor: colors['text-accent'],
          tabBarInactiveTintColor: colors['text-muted'],
          tabBarStyle: {
            backgroundColor: colors['background-surface'],
            borderTopColor: colors['border-subtle'],
            height: sizes['bottomNav-height'] + insets.bottom,
            paddingBottom: insets.bottom,
          },
          tabBarLabelStyle: {
            fontFamily: fontFamilyFor(LABEL.family, LABEL.fontWeight),
            fontSize: LABEL.fontSize,
            lineHeight: LABEL.lineHeight,
          },
        }}
      >
        <Tabs.Screen name="index" options={tab('nav.principal', House, true)} />
        <Tabs.Screen name="historial" options={tab('nav.historial', Clock, false)} />
        <Tabs.Screen name="zonas" options={tab('nav.zonas', LayoutGrid, true)} />
        <Tabs.Screen name="consejos" options={tab('nav.consejos', Lightbulb, true)} />
        <Tabs.Screen name="configuracion" options={tab('nav.configuracion', Settings, false)} />

        <Tabs.Screen name="catalogo-componentes" options={HIDDEN} />
        <Tabs.Screen name="editar-perfil" options={HIDDEN} />
        <Tabs.Screen name="cambiar-contrasena" options={HIDDEN} />
        <Tabs.Screen name="gestionar-correo" options={HIDDEN} />
        <Tabs.Screen name="establecer-meta" options={HIDDEN} />
        <Tabs.Screen name="configurar-tarifa" options={HIDDEN} />
        <Tabs.Screen name="fuentes-datos" options={HIDDEN} />
        <Tabs.Screen name="miembros" options={HIDDEN} />
      </Tabs>
    </>
  );
}

const styles = StyleSheet.create({
  iconBox: {
    width: spacing['40'] + spacing['4'],
    height: spacing['32'],
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconBoxActive: { backgroundColor: colors['accent-soft'] },
});
