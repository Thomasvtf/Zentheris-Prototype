/**
 * Icon (Icon.md): glifo de Lucide por nombre, con la escala 16 · 20 · 24 · 32.
 * `IconName` reúne los nombres de docs/diseno/componentes/index.d.ts y, al final, los que la app
 * ya usa en pantallas aprobadas (Historial, Panel) y el contrato aún no lista.
 */
import React from 'react';
import {
  Activity,
  ArrowRightLeft,
  Bath,
  Bed,
  Bell,
  CalendarDays,
  Car,
  ChartColumn,
  ChartPie,
  ChartSpline,
  ChevronDown,
  ChevronLeft,
  ChevronsLeft,
  CircleAlert,
  CircleCheck,
  CirclePause,
  CircleX,
  Clock,
  Coins,
  CookingPot,
  Donut,
  DoorClosed,
  EllipsisVertical,
  Fence,
  Gauge,
  History,
  House,
  Image,
  Info,
  LayoutGrid,
  Lightbulb,
  List,
  Loader,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Monitor,
  Refrigerator,
  Settings,
  Shield,
  Sofa,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
  User,
  UserPlus,
  WashingMachine,
  X,
  Zap,
} from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';

import { colors } from '@/theme';

const ICONS = {
  // index.d.ts
  house: House,
  clock: Clock,
  history: History,
  'layout-grid': LayoutGrid,
  lightbulb: Lightbulb,
  settings: Settings,
  bell: Bell,
  'chevrons-left': ChevronsLeft,
  'circle-check': CircleCheck,
  'triangle-alert': TriangleAlert,
  'circle-alert': CircleAlert,
  'circle-x': CircleX,
  info: Info,
  zap: Zap,
  loader: Loader,
  user: User,
  shield: Shield,
  coins: Coins,
  'trending-up': TrendingUp,
  'trending-down': TrendingDown,
  'chart-pie': ChartPie,
  'chevron-down': ChevronDown,
  lock: Lock,
  mail: Mail,
  image: Image,
  'log-out': LogOut,
  'arrow-right-left': ArrowRightLeft,
  'circle-pause': CirclePause,
  'user-plus': UserPlus,
  x: X,
  'ellipsis-vertical': EllipsisVertical,
  refrigerator: Refrigerator,
  sofa: Sofa,
  bed: Bed,
  bath: Bath,
  monitor: Monitor,
  'washing-machine': WashingMachine,
  fence: Fence,
  car: Car,
  'door-closed': DoorClosed,
  // Extensión de la app (usados en pantallas; no están en index.d.ts)
  activity: Activity,
  'calendar-days': CalendarDays,
  'chart-column': ChartColumn,
  'chart-spline': ChartSpline,
  'chevron-left': ChevronLeft,
  'cooking-pot': CookingPot,
  donut: Donut,
  gauge: Gauge,
  list: List,
  'map-pin': MapPin,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

export interface IconProps {
  name: IconName;
  size?: 16 | 20 | 24 | 32;
  /** Color de los tokens; por defecto `text-muted` (ícono táctil en reposo). */
  color?: string;
  /** Solo íconos con significado propio; sin etiqueta, el lector de pantalla lo ignora. */
  label?: string;
}

export function Icon({ name, size = 24, color = colors['text-muted'], label }: IconProps) {
  const Glyph = ICONS[name];
  return (
    <Glyph
      size={size}
      color={color}
      accessible={label !== undefined}
      accessibilityLabel={label}
      importantForAccessibility={label === undefined ? 'no-hide-descendants' : 'auto'}
    />
  );
}
