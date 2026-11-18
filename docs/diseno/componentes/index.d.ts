import type * as React from 'react';

export type EstadoConsumo = 'normal' | 'elevado' | 'critico' | 'sin_datos' | 'sin_referencia';
export type IconName = 'house' | 'clock' | 'history' | 'layout-grid' | 'lightbulb' | 'settings' | 'bell' | 'chevrons-left' | 'circle-check' | 'triangle-alert' | 'circle-alert' | 'circle-x' | 'info' | 'zap' | 'loader' | 'user' | 'shield' | 'coins' | 'trending-up' | 'trending-down' | 'chart-pie' | 'chevron-down' | 'lock' | 'mail' | 'image' | 'log-out' | 'arrow-right-left' | 'circle-pause' | 'user-plus' | 'x' | 'ellipsis-vertical' | 'refrigerator' | 'sofa' | 'bed' | 'bath' | 'monitor' | 'washing-machine' | 'fence' | 'car' | 'door-closed';

/** Cifra + unidad en formato es-CO. `valor: null` = sin datos («—»). COP solo con `tarifaVigente`. */
/** Decimales por defecto (RN-XII-08): kW 2, kWh 1, COP 0. */
export interface MetricProps { valor: number | null; unidad?: 'kW' | 'kWh' | 'COP' | '%'; tamano?: 'xl' | 'l' | 'm' | 's'; decimales?: number; tarifaVigente?: boolean; abreviar?: boolean }
export declare function Metric(props: MetricProps): React.ReactElement | null;

export interface StatusBadgeProps { estado: 'normal' | 'elevado' | 'critico'; variante?: 'capsula' | 'texto'; icono?: boolean }
export declare function StatusBadge(props: StatusBadgeProps): React.ReactElement | null;

export interface ButtonProps { variante?: 'primario' | 'secundario' | 'fantasma' | 'destructivo'; estado?: 'normal' | 'presionado' | 'deshabilitado' | 'cargando'; icono?: IconName; bloque?: boolean; type?: 'button' | 'submit'; onClick?: () => void; children?: React.ReactNode }
export declare function Button(props: ButtonProps): React.ReactElement;

export interface ChipProps { activo?: boolean; deshabilitado?: boolean; icono?: IconName; onClick?: () => void; children?: React.ReactNode }
export declare function Chip(props: ChipProps): React.ReactElement;

export interface TextFieldProps { etiqueta: string; estado?: 'default' | 'activo' | 'error' | 'deshabilitado'; placeholder?: string; valor?: string; tipo?: string; sufijo?: string; error?: string; ayuda?: string }
export declare function TextField(props: TextFieldProps): React.ReactElement;

export interface ProgressBarProps { porcentaje: number; estado?: 'normal' | 'elevado' | 'critico' | 'neutro'; etiqueta: string }
export declare function ProgressBar(props: ProgressBarProps): React.ReactElement;

export interface ConsumptionCardProps { tipo?: 'actual' | 'hoy'; estado?: EstadoConsumo | 'sin_permiso' | 'cargando'; valor?: number | null; decimales?: number; titulo?: string; periodo: string; comparacion?: string; tendencia?: 'sube' | 'baja'; progreso?: number; limite?: number }
export declare function ConsumptionCard(props: ConsumptionCardProps): React.ReactElement;

export interface StateMessageProps { tipo: 'sin_datos' | 'sin_permiso' | 'sin_tarifa' | 'sin_referencia' | 'vacio' | 'todo_bajo_control'; recurso?: string; titulo?: string; descripcion?: string; icono?: IconName; accion?: string; onAccion?: () => void }
export declare function StateMessage(props: StateMessageProps): React.ReactElement;

export interface InlineNoticeProps { tono: 'error' | 'advertencia' | 'informacion' | 'exito'; titulo: string; descripcion?: string; onReintentar?: (() => void) | false }
export declare function InlineNotice(props: InlineNoticeProps): React.ReactElement;

export interface SkeletonProps { tamano?: 'estandar' | 'compacta' }
export declare function Skeleton(props: SkeletonProps): React.ReactElement;

export interface AlertItemProps { categoria: 'consumo_elevado' | 'consumo_critico' | 'informacion' | 'miembro' | 'consejo'; severidad: 'informativa' | 'advertencia' | 'critica'; leida?: boolean; titulo: string; tiempo: string; icono?: IconName }
export declare function AlertItem(props: AlertItemProps): React.ReactElement;

export interface TipCardProps { estado?: 'pendiente' | 'completado'; prioridad?: 'alta' | 'media' | 'baja'; titulo: string; descripcion?: string }
export declare function TipCard(props: TipCardProps): React.ReactElement;

export interface PriorityTagProps { prioridad: 'alta' | 'media' | 'baja' }
export declare function PriorityTag(props: PriorityTagProps): React.ReactElement;

export interface ScreenHeaderProps { titulo: string; onAtras?: (() => void) | false; campana?: boolean; noLeidas?: number }
export declare function ScreenHeader(props: ScreenHeaderProps): React.ReactElement;

export interface BottomNavProps { activa: 'principal' | 'historial' | 'zonas' | 'consejos' | 'configuracion'; onCambiar?: (id: BottomNavProps['activa']) => void }
export declare function BottomNav(props: BottomNavProps): React.ReactElement;

/** RN-XIII-04: con más de 4 zonas, 4 segmentos + «Otras zonas»; la lista muestra todas. */
export interface ZoneDonutChartProps { zonas: { nombre: string; porcentaje: number }[]; total?: number; periodo?: string }
export declare function ZoneDonutChart(props: ZoneDonutChartProps): React.ReactElement;

/** RN-XIII-03: el pico más alto se marca con «Pico» y color propio (rojo claro `chart-peak`, D17). */
export interface BarChartProps { datos: { etiqueta: string; valor: number | null; eje?: string }[]; unidad?: 'kW' | 'kWh' | 'COP'; tarifaVigente?: boolean; titulo?: string; periodo?: string }
export declare function BarChart(props: BarChartProps): React.ReactElement | null;

/** Ficha añadida el 11/11/2026 (Figma 588:109). `proporcion` = min(potencia_kw ÷ (referencia_kw × 1,6), 1). Se dibuja a mano con react-native-svg. */
export interface ConsumptionGaugeProps { valor: number | null; unidad?: 'kW' | 'COP'; estado: EstadoConsumo; proporcion: number; decimales?: number }
export declare function ConsumptionGauge(props: ConsumptionGaugeProps): React.ReactElement | null;

/** Ficha añadida el 11/11/2026 (Figma 561:127). Anillo de un solo valor; no es ZoneDonutChart. Misma regla de `proporcion` que el Gauge. */
export interface ConsumptionRingProps { valor: number | null; unidad?: 'kW' | 'COP'; estado: EstadoConsumo; proporcion: number; decimales?: number }
export declare function ConsumptionRing(props: ConsumptionRingProps): React.ReactElement | null;

/** Ficha añadida el 11/11/2026 (Figma 537:109). Mismos datos que BarChart; el pico se marca igual (RN-XIII-03). */
export interface LineChartProps { datos: { etiqueta: string; valor: number | null; eje?: string }[]; unidad?: 'kW' | 'kWh' | 'COP'; tarifaVigente?: boolean; titulo?: string; periodo?: string }
export declare function LineChart(props: LineChartProps): React.ReactElement | null;

/** RN-XV-02/04: «¡Todo bajo control!» solo sin pendientes; pendientes por prioridad y completados al final. */
export interface TipListProps { consejos: TipCardProps[] }
export declare function TipList(props: TipListProps): React.ReactElement;


/* ===== v4.5 · componentes nuevos (PROPUESTOS, 02/11/2026) ===== */
/** Campo desplegable (Control/Selector). Abre una BottomSheet con OptionItem; igual en Android e iOS. */
export interface SelectProps { etiqueta: string; valor?: string; placeholder?: string; estado?: 'default' | 'abierto' | 'deshabilitado' | 'solo_lectura'; ayuda?: string; onAbrir?: () => void }
export declare function Select(props: SelectProps): React.ReactElement;
/** Opción de lista en una hoja inferior (Control/Lista-opcion). */
export interface OptionItemProps { texto: string; seleccionada?: boolean; deshabilitada?: boolean; onClick?: () => void }
export declare function OptionItem(props: OptionItemProps): React.ReactElement;
/** Requisito de contraseña, RN-IX-02 (Control/Requisito). */
export interface RequirementProps { texto: string; cumple?: boolean }
export declare function Requirement(props: RequirementProps): React.ReactElement;
/** Zona del catálogo de 9 en el onboarding, RN-X-02/RN-X-09 (Control/Zona-seleccionable). */
export interface ZoneTileProps { zona: 'Baño' | 'Cocina' | 'Cuarto de servicio' | 'Dormitorio' | 'Garaje' | 'Lavandería' | 'Oficina' | 'Sala' | 'Terraza'; estado?: 'disponible' | 'seleccionada' | 'basica' | 'deshabilitada'; ayuda?: string; onClick?: () => void }
export declare function ZoneTile(props: ZoneTileProps): React.ReactElement;
/** Progreso del onboarding (Navegacion/Indicador-pasos). */
export interface StepIndicatorProps { paso: number; total?: number }
export declare function StepIndicator(props: StepIndicatorProps): React.ReactElement;
/** Fila de acción de una hoja inferior (Menu/Accion). */
export interface ActionItemProps { texto: string; icono?: IconName; tono?: 'normal' | 'destructivo' | 'deshabilitado'; onClick?: () => void }
export declare function ActionItem(props: ActionItemProps): React.ReactElement;
/** Hoja inferior común a Android e iOS (Navegacion/Hoja-inferior). Se presenta sobre .zt-overlay. */
export interface BottomSheetProps { titulo: string; descripcion?: string; onCerrar?: () => void; children?: React.ReactNode }
export declare function BottomSheet(props: BottomSheetProps): React.ReactElement;
/** Confirmación de acciones irreversibles, RN-IX-09/RN-X-07 (Dialogo/Confirmacion). */
export interface ConfirmDialogProps { titulo: string; descripcion?: string; tono?: 'destructivo' | 'normal'; confirmar?: string; cancelar?: string; onConfirmar?: () => void; onCancelar?: () => void }
export declare function ConfirmDialog(props: ConfirmDialogProps): React.ReactElement;
/** Fuente principal o sensor, RN-XVI-06 (Configuracion/Fuente-datos). `valor: null` = «—». `mostrarValor: false` sin permiso de ver consumo. */
export interface DataSourceRowProps { nombre: string; detalle?: string; valor?: number | null; estado?: 'activo' | 'pausado' | 'sin_datos'; mostrarValor?: boolean; icono?: IconName }
export declare function DataSourceRow(props: DataSourceRowProps): React.ReactElement;
/** Invitación pendiente, solo para el administrador, RN-X-08 (Configuracion/Invitacion-pendiente). */
export interface PendingInviteProps { correo: string; vence: string; onMenu?: (() => void) | false }
export declare function PendingInvite(props: PendingInviteProps): React.ReactElement;
/** Invitación recibida, RN-X-01/RN-X-06 (Card/Invitacion). Datos: hogar_nombre, invitado_por_nombre, expira_en. */
export interface InvitationCardProps { hogar: string; invita: string; vence?: string; onAceptar?: () => void; onRechazar?: () => void }
export declare function InvitationCard(props: InvitationCardProps): React.ReactElement;
/** Marcador del pico más alto, RN-XIII-03/D5 (Grafico/Marcador-pico). Opción A en uso; B alternativa. */
export interface PeakMarkerProps { etiqueta?: string; opcion?: 'A' | 'B' }
export declare function PeakMarker(props: PeakMarkerProps): React.ReactElement;

export interface IconProps { name: IconName; size?: 16 | 20 | 24 | 32; color?: string; label?: string; className?: string }
export declare function Icon(props: IconProps): React.ReactElement;

export declare const DECIMALES: { kW: 2; kWh: 1; COP: 0; '%': 0 };
export declare function formatNumber(v: number | null, decimales?: number, opts?: { abreviar?: boolean }): string;
export declare function formatCOP(v: number | null, opts?: { abreviar?: boolean }): string;
export declare function formatPercent(v: number | null, decimales?: number): string;

declare global { interface Window { Zentheris: { Metric: typeof Metric; StatusBadge: typeof StatusBadge; Button: typeof Button; Chip: typeof Chip; TextField: typeof TextField; ProgressBar: typeof ProgressBar; ConsumptionCard: typeof ConsumptionCard; StateMessage: typeof StateMessage; InlineNotice: typeof InlineNotice; Skeleton: typeof Skeleton; AlertItem: typeof AlertItem; TipCard: typeof TipCard; PriorityTag: typeof PriorityTag; ScreenHeader: typeof ScreenHeader; BottomNav: typeof BottomNav; ZoneDonutChart: typeof ZoneDonutChart; BarChart: typeof BarChart; TipList: typeof TipList; Icon: typeof Icon; DECIMALES: typeof DECIMALES; formatNumber: typeof formatNumber; formatCOP: typeof formatCOP; formatPercent: typeof formatPercent; Select: typeof Select; OptionItem: typeof OptionItem; Requirement: typeof Requirement; ZoneTile: typeof ZoneTile; StepIndicator: typeof StepIndicator; ActionItem: typeof ActionItem; BottomSheet: typeof BottomSheet; ConfirmDialog: typeof ConfirmDialog; DataSourceRow: typeof DataSourceRow; PendingInvite: typeof PendingInvite; InvitationCard: typeof InvitationCard; PeakMarker: typeof PeakMarker } } }
