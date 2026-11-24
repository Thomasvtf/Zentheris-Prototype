import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, {
  Path,
  Rect,
  Defs,
  LinearGradient,
  Stop,
} from 'react-native-svg';
import {
  Periodo,
  UnitType,
  getDataForPeriodo,
  getPeriodoMeta,
  formatValue,
} from './chartData';

interface HistoryAreaChartProps {
  periodo: Periodo;
  unit: UnitType;
}

export const HistoryAreaChart: React.FC<HistoryAreaChartProps> = ({ periodo, unit }) => {
  const data = getDataForPeriodo(periodo);
  const meta = getPeriodoMeta(periodo, unit);
  const maxVal = Math.max(...data.map((d) => d.val)) * 1.15;
  const peakItem = data.find((d) => d.isPeak);
  const peakIndex = data.findIndex((d) => d.isPeak);

  const svgWidth = 300;
  const svgHeight = 120;
  const padX = 10;
  const padTop = 15;
  const padBottom = 10;
  const usableHeight = svgHeight - padTop - padBottom;
  const usableWidth = svgWidth - 2 * padX;

  // Construir stepped path (gráfico de área escalonada / timeline)
  const points = data.map((d, i) => {
    const x = padX + (i / Math.max(data.length - 1, 1)) * usableWidth;
    const y = svgHeight - padBottom - (d.val / maxVal) * usableHeight;
    return { x, y, isPeak: d.isPeak, val: d.val, label: d.label };
  });

  let stepPath = '';
  if (points.length > 0) {
    stepPath = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const nextX = points[i + 1].x;
      const currentY = points[i].y;
      const nextY = points[i + 1].y;
      stepPath += ` L ${nextX} ${currentY} L ${nextX} ${nextY}`;
    }
  }

  const lastPoint = points[points.length - 1];
  const firstPoint = points[0];
  const stepAreaPath = stepPath
    ? `${stepPath} L ${lastPoint.x} ${svgHeight - padBottom} L ${firstPoint.x} ${svgHeight - padBottom} Z`
    : '';

  const tooltipLeftPercent =
    peakIndex >= 0 ? `${Math.min(Math.max((peakIndex / (data.length - 1)) * 80 + 10, 15), 75)}%` : '50%';

  const isDay = periodo === 'dia';

  return (
    <View style={styles.wrapper}>
      <View style={styles.chartContainer}>
        {/* Eje Y con líneas punteadas */}
        <View style={styles.chartGridLines}>
          {meta.yAxisLabels.map((lbl, idx) => (
            <View key={idx} style={styles.gridLineRow}>
              <Text style={styles.axisLabel} numberOfLines={1}>
                {formatValue(lbl, unit)}
              </Text>
              <View style={styles.dashedLine} />
            </View>
          ))}
          <View style={styles.gridLineRow}>
            <Text style={styles.axisLabel}>{unit}</Text>
            <View style={[styles.dashedLine, { opacity: 0 }]} />
          </View>
        </View>

        {/* Tooltip flotante para el pico */}
        {peakItem && (
          <View style={[styles.tooltipBadge, { left: tooltipLeftPercent as any }]}>
            <Text style={styles.tooltipText}>
              {peakItem.label} · {formatValue(peakItem.val, unit)} {unit}
            </Text>
          </View>
        )}

        {/* Gráfico Stepped Area */}
        <View style={styles.svgContainer}>
          <Svg
            width="100%"
            height={svgHeight}
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            preserveAspectRatio="none"
          >
            <Defs>
              <LinearGradient id="steppedGrad" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0%" stopColor="#38BDF8" stopOpacity="0.4" />
                <Stop offset="100%" stopColor="#38BDF8" stopOpacity="0.02" />
              </LinearGradient>
            </Defs>

            {/* Área escalonada con gradiente */}
            <Path d={stepAreaPath} fill="url(#steppedGrad)" />

            {/* Línea escalonada */}
            <Path
              d={stepPath}
              fill="none"
              stroke="#38BDF8"
              strokeWidth={2.5}
            />

            {/* Resaltado del pico en la zona temporal */}
            {peakIndex >= 0 && points[peakIndex] && (
              <Rect
                x={points[peakIndex].x - 6}
                y={points[peakIndex].y - 6}
                width={12}
                height={12}
                rx={3}
                fill="#EF4444"
                stroke="#FFFFFF"
                strokeWidth={2}
              />
            )}
          </Svg>
        </View>
      </View>

      {/* Etiquetas Eje X */}
      <View style={styles.xAxisRow}>
        {isDay ? (
          <>
            <Text style={styles.xAxisLabel}>00h</Text>
            <Text style={styles.xAxisLabel}>06h</Text>
            <Text style={styles.xAxisLabel}>12h</Text>
            <Text style={styles.xAxisLabel}>18h</Text>
            <Text style={styles.xAxisLabel}>24h</Text>
          </>
        ) : (
          data.map((item, index) => (
            <Text
              key={index}
              style={[
                styles.xAxisLabel,
                item.isPeak && { color: '#EF4444', fontWeight: '700' },
              ]}
            >
              {item.label}
            </Text>
          ))
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  wrapper: {
    marginTop: 12,
  },
  chartContainer: {
    height: 155,
    position: 'relative',
    justifyContent: 'flex-end',
  },
  chartGridLines: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'space-between',
  },
  gridLineRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  axisLabel: {
    color: '#657B72',
    fontSize: 10,
    width: 28,
  },
  dashedLine: {
    flex: 1,
    height: 1,
    borderWidth: 0.8,
    borderColor: '#1A3B2F',
    borderStyle: 'dashed',
    marginLeft: 4,
  },
  tooltipBadge: {
    position: 'absolute',
    top: 8,
    backgroundColor: '#0A2533',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#1A536B',
    zIndex: 10,
    transform: [{ translateX: -40 }],
  },
  tooltipText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '600',
  },
  svgContainer: {
    paddingLeft: 30,
    height: 120,
    justifyContent: 'flex-end',
  },
  xAxisRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingLeft: 30,
    marginTop: 8,
  },
  xAxisLabel: {
    color: '#657B72',
    fontSize: 11,
  },
});

