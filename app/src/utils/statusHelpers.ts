export type EstadoType = 'Normal' | 'Elevado' | 'Crítico' | 'normal' | 'elevado' | 'critico' | string;

export const estadoColor = (estado?: EstadoType): string => {
  const norm = estado?.toLowerCase();
  switch (norm) {
    case 'elevado':
      return '#D69E2E';
    case 'crítico':
    case 'critico':
      return '#E53E3E';
    case 'normal':
    default:
      return '#5DD39E';
  }
};

export const estadoBadgeBg = (estado?: EstadoType): string => {
  const norm = estado?.toLowerCase();
  switch (norm) {
    case 'elevado':
      return '#3B2A10';
    case 'crítico':
    case 'critico':
      return '#3B1010';
    case 'normal':
    default:
      return '#0E2D22';
  }
};

export const estadoBorderColor = (estado?: EstadoType): string => {
  const norm = estado?.toLowerCase();
  switch (norm) {
    case 'elevado':
      return '#6B4F1B';
    case 'crítico':
    case 'critico':
      return '#6B1B1B';
    case 'normal':
    default:
      return '#194937';
  }
};

export const estadoIcon = (estado?: EstadoType): string => {
  const norm = estado?.toLowerCase();
  switch (norm) {
    case 'elevado':
      return 'warning-outline';
    case 'crítico':
    case 'critico':
      return 'alert-circle-outline';
    case 'normal':
    default:
      return 'checkmark-circle-outline';
  }
};

