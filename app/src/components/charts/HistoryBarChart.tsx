import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import {
  Periodo,
  UnitType,
  getDataForPeriodo,
  getPeriodoMeta,
  formatValue,
} from './chartData';

interface HistoryBarChartProps {
  periodo: Periodo;
  unit: UnitType;
}

export const HistoryBarChart: React.FC<HistoryBarChartProps> = ({ periodo, unit }) => {
  const data = getDataForPeriodo(periodo);
  const meta = getPeriodoMeta(periodo, unit);
  const maxVal = Math.max(...data.map((d) => d.val)) * 1.15;
  const peakItem = data.find((d) => d.isPeak);
  const peakIndex = data.findIndex((d) => d.isPeak);

  // Posición estimada del tooltip flotante
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

        {/* Barras verticales */}
        <View style={styles.barsRow}>
          {data.map((item, index) => {
            const heightPercentage = Math.min((item.val / maxVal) * 100, 100);
            return (
              <View key={index} style={styles.barCol}>
                <View
                  style={[
                    styles.barFill,
                    {
                      height: `${heightPercentage}%`,
                      width: isDay ? '75%' : periodo === 'semana' ? 24 : 38,
                    },
                    item.isPeak ? styles.barPeak : styles.barNormal,
                  ]}
                />
              </View>
            );
          })}
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
    backgroundColor: '#0D2920',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#1F533E',
    zIndex: 10,
    transform: [{ translateX: -40 }],
  },
  tooltipText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '600',
  },
  barsRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    paddingLeft: 30,
    height: 120,
  },
  barCol: {
    flex: 1,
    height: '100%',
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingHorizontal: 1,
  },
  barFill: {
    borderRadius: 3,
  },
  barNormal: {
    backgroundColor: '#4ADE80',
  },
  barPeak: {
    backgroundColor: '#EF4444',
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

