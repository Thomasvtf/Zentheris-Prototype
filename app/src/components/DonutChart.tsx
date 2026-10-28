import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

export interface DonutChartProps {
  value: number;       // ej: 7.2
  maxValue?: number;   // ej: 10
  unit?: 'KW' | 'COP';
  size?: number;
  strokeWidth?: number;
  color?: string;
  trackColor?: string;
  subtitle?: string;
  subtitleColor?: string;
  style?: ViewStyle;
}

export const DonutChart: React.FC<DonutChartProps> = ({
  value,
  maxValue = 10,
  unit = 'KW',
  size = 200,
  strokeWidth = 26,
  color = '#F6D543',
  trackColor = '#20382E',
  subtitle = 'Por encima de lo normal',
  subtitleColor = '#F6D543',
  style,
}) => {
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const percentage = Math.min(Math.max(value / maxValue, 0), 1);
  const strokeDashoffset = circumference - percentage * circumference;

  const displayVal = unit === 'COP' ? (value * 1200).toFixed(0) : value.toFixed(1);
  const displayUnit = unit === 'COP' ? 'COP' : 'kW';

  return (
    <View style={[styles.container, style]}>
      <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
        <Svg width={size} height={size}>
          {/* Círculo de fondo oscuro */}
          <Circle
            cx={center}
            cy={center}
            r={radius}
            stroke={trackColor}
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Círculo de progreso coloreado (comienza arriba a las 12 en punto) */}
          <Circle
            cx={center}
            cy={center}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={`${circumference} ${circumference}`}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="butt"
            fill="none"
            rotation="-90"
            origin={`${center}, ${center}`}
          />
        </Svg>

        {/* Texto central en el hueco del donut */}
        <View style={styles.centerTextContainer}>
          <Text style={styles.valueText}>
            {displayVal}
          </Text>
          <Text style={styles.unitText}>
            {displayUnit}
          </Text>
        </View>
      </View>

      {/* Subtítulo bajo la gráfica */}
      {subtitle ? (
        <Text style={[styles.subtitle, { color: subtitleColor }]}>
          {subtitle}
        </Text>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    marginTop: 16,
    marginBottom: 8,
  },
  centerTextContainer: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
  },
  valueText: {
    color: '#FFFFFF',
    fontSize: 36,
    fontWeight: 'bold',
  },
  unitText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '500',
    marginTop: -2,
  },
  subtitle: {
    fontSize: 15,
    fontWeight: '500',
    marginTop: 14,
  },
});

