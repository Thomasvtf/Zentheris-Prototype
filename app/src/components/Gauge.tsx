// @ts-nocheck
import React from 'react';
import { View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

interface GaugeProps {
  value: number;       // Valor actual, ej: 2.4
  maxValue: number;    // Valor máximo del arco, ej: 10
  size?: number;       // Ancho/Alto del componente
  strokeWidth?: number;// Grosor de la barra del arco
}

export const Gauge: React.FC<GaugeProps> = ({
  value,
  maxValue,
  size = 220,
  strokeWidth = 26,
}) => {
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;

  // Calculamos el porcentaje consumido (limitado entre 0 y 1)
  const percentage = Math.min(Math.max(value / maxValue, 0), 1);

  // Función matemática para calcular puntos de un arco semicircular (de 180° a 0°)
  const getArcPath = (startAngleDeg: number, endAngleDeg: number) => {
    const startRad = (startAngleDeg * Math.PI) / 180;
    const endRad = (endAngleDeg * Math.PI) / 180;

    const x1 = center + radius * Math.cos(startRad);
    const y1 = center + radius * Math.sin(startRad);
    const x2 = center + radius * Math.cos(endRad);
    const y2 = center + radius * Math.sin(endRad);

    const largeArcFlag = endAngleDeg - startAngleDeg <= 180 ? '0' : '1';

    return `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`;
  };

  // Fondo oscuro del arco (180° a 360°, que equivale a de PI a 2*PI)
  const backgroundPath = getArcPath(180, 360);

  // Arco verde activo proporcional al porcentaje
  const activeEndAngle = 180 + percentage * 180;
  const activePath = percentage > 0 ? getArcPath(180, activeEndAngle) : '';

  return (
    <View style={{ alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size / 2 + strokeWidth}>
        {/* 1. Arco de fondo verde oscuro */}
        <Path
          d={backgroundPath}
          stroke="#16382C"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          fill="none"
        />

        {/* 2. Arco verde brillante activo */}
        {percentage > 0 && (
          <Path
            d={activePath}
            stroke="#5DD39E"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            fill="none"
          />
        )}
      </Svg>
    </View>
  );
};