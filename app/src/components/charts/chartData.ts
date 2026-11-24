export type Periodo = 'dia' | 'semana' | 'mes';
export type UnitType = 'KW' | 'COP';

export interface DataPoint {
  label: string;
  val: number; // En kW
  isPeak?: boolean;
}

// Factor de conversión kW a COP
export const COP_MULTIPLIER = 1200;

export const formatValue = (val: number, unit: UnitType): string => {
  if (unit === 'COP') {
    const copVal = val * COP_MULTIPLIER;
    return copVal >= 1000 ? `${(copVal / 1000).toFixed(0)}k` : `${copVal.toFixed(0)}`;
  }
  return `${val.toFixed(val % 1 === 0 ? 0 : 1)}`;
};

export const getDisplayNumber = (val: number, unit: UnitType): number => {
  return unit === 'COP' ? Math.round(val * COP_MULTIPLIER) : Number(val.toFixed(1));
};

// ── Datos por Período ─────────────────────────────────────────────────────────

// Día: 24 horas (0 a 23)
export const DIA_DATA: DataPoint[] = [
  { label: '00h', val: 5 },
  { label: '01h', val: 4 },
  { label: '02h', val: 3 },
  { label: '03h', val: 4 },
  { label: '04h', val: 6 },
  { label: '05h', val: 8 },
  { label: '06h', val: 12 },
  { label: '07h', val: 15 },
  { label: '08h', val: 18 },
  { label: '09h', val: 20 },
  { label: '10h', val: 22 },
  { label: '11h', val: 25, isPeak: true },
  { label: '12h', val: 23 },
  { label: '13h', val: 21 },
  { label: '14h', val: 19 },
  { label: '15h', val: 20 },
  { label: '16h', val: 22 },
  { label: '17h', val: 18 },
  { label: '18h', val: 16 },
  { label: '19h', val: 14 },
  { label: '20h', val: 12 },
  { label: '21h', val: 10 },
  { label: '22h', val: 8 },
  { label: '23h', val: 6 },
];

// Semana: 7 días
export const SEMANA_DATA: DataPoint[] = [
  { label: 'Lun', val: 22 },
  { label: 'Mar', val: 24 },
  { label: 'Mié', val: 19 },
  { label: 'Jue', val: 26 },
  { label: 'Vie', val: 28 },
  { label: 'Sáb', val: 32, isPeak: true },
  { label: 'Dom', val: 20 },
];

// Mes: 4 semanas
export const MES_DATA: DataPoint[] = [
  { label: 'Sem 1', val: 110 },
  { label: 'Sem 2', val: 125 },
  { label: 'Sem 3', val: 145, isPeak: true },
  { label: 'Sem 4', val: 100 },
];

export const getDataForPeriodo = (periodo: Periodo): DataPoint[] => {
  switch (periodo) {
    case 'semana':
      return SEMANA_DATA;
    case 'mes':
      return MES_DATA;
    case 'dia':
    default:
      return DIA_DATA;
  }
};

export const getPeriodoMeta = (periodo: Periodo, unit: UnitType) => {
  switch (periodo) {
    case 'semana':
      return {
        peakText: 'Pico reportado el Sábado',
        peakVal: 32,
        peakLabel: 'Sáb · 32',
        thisPeriodCompare: 182,
        prevPeriodCompare: 196,
        compareDesc: '7% menos que la semana anterior',
        costEstimated: 94,
        costProjection: 105,
        costDesc: 'Impacto económico por debajo de lo normal esta semana',
        yAxisLabels: [35, 25, 15],
      };
    case 'mes':
      return {
        peakText: 'Pico reportado en la Semana 3',
        peakVal: 145,
        peakLabel: 'Sem 3 · 145',
        thisPeriodCompare: 740,
        prevPeriodCompare: 810,
        compareDesc: '8.6% menos que el mes anterior',
        costEstimated: 480,
        costProjection: 790,
        costDesc: 'Impacto económico dentro del objetivo presupuestado',
        yAxisLabels: [160, 110, 60],
      };
    case 'dia':
    default:
      return {
        peakText: 'Pico reportado a las 11:00h',
        peakVal: 25,
        peakLabel: '11h · 25',
        thisPeriodCompare: 28,
        prevPeriodCompare: 19,
        compareDesc: '47% más que el día de ayer',
        costEstimated: 24,
        costProjection: 30,
        costDesc: 'Consumo elevado en horas pico de la mañana',
        yAxisLabels: [30, 20, 10],
      };
  }
};

