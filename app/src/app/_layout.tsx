/**
 * Barra inferior (BottomNav.md; Figma `Navegacion/Barra-inferior` 4083:3427).
 *
 * - Cinco secciones con íconos de Lucide: house, clock (DC-13), layout-grid, lightbulb y settings.
 * - Alto `bottomNav-height` (64) más el área segura inferior; fondo `background-surface` y borde
 *   superior `border-subtle`.
 * - Inactiva: ícono 24 y etiqueta en `text-muted`. Activa: contenedor 48 × 28 `accent-soft` con
 *   `radius.sm`, ícono `accent-primary` y etiqueta `text-accent`. Etiquetas `body-xs-medium-10`.
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
import { Clock, House, LayoutGrid, Lightbulb, Settings } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';

import { colors, fontFamilyFor, radius, sizes, typography } from '@/theme';
import { t } from '@/texts';

const ICON_SIZE = 24;
const LABEL = typography['body-xs-medium-10'];

/** Ícono de la pestaña; la activa va dentro del contenedor `accent-soft` de 48 × 28. */
function NavIcon({ icono: Icono, focused }: { icono: LucideIcon; focused: boolean }) {
  return (
    <View style={[styles.iconBox, focused && styles.iconBoxActive]}>
      <Icono size={ICON_SIZE} color={focused ? colors['accent-primary'] : colors['text-muted']} />
    </View>
  );
}

/** Opciones de una pestaña visible: etiqueta del catálogo e ícono. */
function tab(labelKey: string, icono: LucideIcon) {
  const title = t(labelKey);
  return {
    title,
    tabBarAccessibilityLabel: title,
    tabBarIcon: ({ focused }: { focused: boolean }) => <NavIcon icono={icono} focused={focused} />,
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
        <Tabs.Screen name="index" options={tab('nav.principal', House)} />
        <Tabs.Screen name="historial" options={tab('nav.historial', Clock)} />
        <Tabs.Screen name="zonas" options={tab('nav.zonas', LayoutGrid)} />
        <Tabs.Screen name="consejos" options={tab('nav.consejos', Lightbulb)} />
        <Tabs.Screen name="configuracion" options={tab('nav.configuracion', Settings)} />

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
    width: sizes['iconButtonLg-size'],
    height: ICON_SIZE + 4,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconBoxActive: { backgroundColor: colors['accent-soft'] },
});
