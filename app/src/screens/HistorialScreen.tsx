// @ts-nocheck
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  SafeAreaView,
  StatusBar,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

// Componentes reutilizables
import { StatusBadge } from '../components/StatusBadge';
import { StatusChip } from '../components/StatusChip';
import { HistoryBarChart } from '../components/charts/HistoryBarChart';
import { HistoryLineChart } from '../components/charts/HistoryLineChart';
import { HistoryAreaChart } from '../components/charts/HistoryAreaChart';
import {
  Periodo,
  UnitType,
  getPeriodoMeta,
  formatValue,
} from '../components/charts/chartData';

// ─── Tipos ────────────────────────────────────────────────────────────────────
type ChartType = 'bar' | 'line' | 'time';
type Zona = 'general' | 'cuartos' | 'cocina' | 'oficina' | 'sala';
type Estado = 'normal' | 'elevado' | 'critico';

export function HistorialScreen() {
  const router = useRouter();

  // Estados interactivos
  const [periodo, setPeriodo] = useState<Periodo>('dia');
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [unit, setUnit] = useState<UnitType>('KW');
  const [selectedZona, setSelectedZona] = useState<Zona>('general');
  const [estado, setEstado] = useState<Estado>('normal');

  // Datos calculados según el período y la unidad seleccionada
  const meta = getPeriodoMeta(periodo, unit);

  // Textos descriptivos según el período
  const periodoLabel =
    periodo === 'dia' ? 'Día' : periodo === 'semana' ? 'Semana' : 'Mes';

  const compareLabelThis =
    periodo === 'dia'
      ? 'ESTE DÍA'
      : periodo === 'semana'
      ? 'ESTA SEMANA'
      : 'ESTE MES';

  const compareLabelPrev =
    periodo === 'dia'
      ? 'DÍA ANTERIOR'
      : periodo === 'semana'
      ? 'SEMANA ANTERIOR'
      : 'MES ANTERIOR';

  const compareSubtitle =
    periodo === 'dia'
      ? 'Este día vs ayer'
      : periodo === 'semana'
      ? 'Esta semana vs anterior'
      : 'Este mes vs mes anterior';

  const costSubtitle =
    periodo === 'dia'
      ? 'Día actual'
      : periodo === 'semana'
      ? 'Semana actual'
      : 'Mes actual';

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#06120E" />

      {/* ─── Header Superior ────────────────────────────────────── */}
      <View style={styles.topHeader}>
        <View style={{ width: 28 }} />
        <Text style={styles.headerTitle}>Historial</Text>
        <TouchableOpacity
          style={styles.headerIconBtn}
          activeOpacity={0.7}
          onPress={() => console.log('Descargar historial')}
        >
          <Ionicons name="download-outline" size={22} color="#D1FAE5" />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Saludo ───────────────────────────────────────────── */}
        <Text style={styles.greeting}>Buenos días, Nicolás</Text>

        {/* ─── Selector de Período (Día / Semana / Mes) ─────────── */}
        <View style={styles.periodSelectorContainer}>
          <TouchableOpacity
            style={[
              styles.periodTab,
              periodo === 'dia' && styles.periodTabActive,
            ]}
            onPress={() => setPeriodo('dia')}
          >
            <Ionicons
              name="calendar-outline"
              size={15}
              color={periodo === 'dia' ? '#5DD39E' : '#718096'}
            />
            <Text
              style={[
                styles.periodTabText,
                periodo === 'dia' && styles.periodTabTextActive,
              ]}
            >
              Día
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.periodTab,
              periodo === 'semana' && styles.periodTabActive,
            ]}
            onPress={() => setPeriodo('semana')}
          >
            <Ionicons
              name="calendar-outline"
              size={15}
              color={periodo === 'semana' ? '#5DD39E' : '#718096'}
            />
            <Text
              style={[
                styles.periodTabText,
                periodo === 'semana' && styles.periodTabTextActive,
              ]}
            >
              Semana
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.periodTab,
              periodo === 'mes' && styles.periodTabActive,
            ]}
            onPress={() => setPeriodo('mes')}
          >
            <Ionicons
              name="calendar-outline"
              size={15}
              color={periodo === 'mes' ? '#5DD39E' : '#718096'}
            />
            <Text
              style={[
                styles.periodTabText,
                periodo === 'mes' && styles.periodTabTextActive,
              ]}
            >
              Mes
            </Text>
          </TouchableOpacity>
        </View>

        {/* ─── CARD 1: Pico del período ─────────────────────────── */}
        <View style={styles.card}>
          <View style={styles.cardHeaderRow}>
            <View style={styles.cardLabelRow}>
              <View style={styles.iconMiniBox}>
                <Ionicons name="trending-up" size={14} color="#5DD39E" />
              </View>
              <Text style={styles.cardSubTitle}>
                Historial · Pico del período · {periodoLabel}
              </Text>
            </View>
            <StatusBadge estado={estado} />
          </View>

          <View style={styles.metricRow}>
            <Text style={styles.bigNumber}>{formatValue(meta.peakVal, unit)}</Text>
            <Text style={styles.unitText}> {unit}</Text>
          </View>
          <Text style={styles.hintText}>{meta.peakText}</Text>

          {/* Notificación de estado reutilizable */}
          <StatusChip
            title="Pico dentro del promedio"
            subtitle="Sigue así para mantener un consumo eficiente"
            estado={estado}
          />
        </View>

        {/* ─── CARD 2: Consumo día | semana | mes (Gráfico y Filtros) ── */}
        <View style={styles.card}>
          <View style={styles.cardHeaderRow}>
            <Text style={styles.cardSubTitle}>
              Historial · Consumo del {periodoLabel.toLowerCase()}
            </Text>
            <View style={styles.rightIconsGroup}>
              {/* Botón Gráfica de Barras */}
              <TouchableOpacity
                style={[
                  styles.chartIconBtn,
                  chartType === 'bar' && styles.chartIconBtnActive,
                ]}
                onPress={() => setChartType('bar')}
              >
                <Ionicons
                  name="bar-chart-outline"
                  size={16}
                  color={chartType === 'bar' ? '#5DD39E' : '#718096'}
                />
              </TouchableOpacity>

              {/* Botón Gráfica de Líneas */}
              <TouchableOpacity
                style={[
                  styles.chartIconBtn,
                  chartType === 'line' && styles.chartIconBtnActive,
                ]}
                onPress={() => setChartType('line')}
              >
                <Ionicons
                  name="stats-chart-outline"
                  size={16}
                  color={chartType === 'line' ? '#5DD39E' : '#718096'}
                />
              </TouchableOpacity>

              {/* Botón Gráfica Temporal / Stepped Area */}
              <TouchableOpacity
                style={[
                  styles.chartIconBtn,
                  chartType === 'time' && styles.chartIconBtnActive,
                ]}
                onPress={() => setChartType('time')}
              >
                <Ionicons
                  name="time-outline"
                  size={16}
                  color={chartType === 'time' ? '#5DD39E' : '#718096'}
                />
              </TouchableOpacity>
            </View>
          </View>

          {/* Renderizado dinámico según el botón de gráfica presionado */}
          {chartType === 'bar' && (
            <HistoryBarChart periodo={periodo} unit={unit} />
          )}
          {chartType === 'line' && (
            <HistoryLineChart periodo={periodo} unit={unit} />
          )}
          {chartType === 'time' && (
            <HistoryAreaChart periodo={periodo} unit={unit} />
          )}

          {/* Selector de Unidades: Kw / COP */}
          <View style={styles.unitToggleGroup}>
            <TouchableOpacity
              style={[
                styles.unitToggleBtn,
                unit === 'KW' && styles.unitToggleBtnActive,
              ]}
              onPress={() => setUnit('KW')}
            >
              <Ionicons
                name="flash"
                size={14}
                color={unit === 'KW' ? '#5DD39E' : '#718096'}
              />
              <Text
                style={[
                  styles.unitToggleText,
                  unit === 'KW' && styles.unitToggleTextActive,
                ]}
              >
                Kw
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.unitToggleBtn,
                unit === 'COP' && styles.unitToggleBtnActive,
              ]}
              onPress={() => setUnit('COP')}
            >
              <Ionicons
                name="cash-outline"
                size={14}
                color={unit === 'COP' ? '#5DD39E' : '#718096'}
              />
              <Text
                style={[
                  styles.unitToggleText,
                  unit === 'COP' && styles.unitToggleTextActive,
                ]}
              >
                COP
              </Text>
            </TouchableOpacity>
          </View>

          {/* Filtrar por zona */}
          <Text style={styles.filterSectionTitle}>Filtrar por zona:</Text>
          <View style={styles.zoneChipsWrapper}>
            {[
              { id: 'general', label: 'General', icon: 'apps-outline' },
              { id: 'cuartos', label: 'Cuartos', icon: 'bed-outline' },
              { id: 'cocina', label: 'Cocina', icon: 'restaurant-outline' },
              { id: 'oficina', label: 'Oficina', icon: 'laptop-outline' },
              { id: 'sala', label: 'Sala', icon: 'car-outline' },
            ].map((z) => {
              const isSelected = selectedZona === z.id;
              return (
                <TouchableOpacity
                  key={z.id}
                  style={[styles.zoneChip, isSelected && styles.zoneChipActive]}
                  onPress={() => setSelectedZona(z.id as Zona)}
                >
                  <Ionicons
                    name={z.icon as any}
                    size={14}
                    color={isSelected ? '#5DD39E' : '#718096'}
                  />
                  <Text
                    style={[
                      styles.zoneChipText,
                      isSelected && styles.zoneChipTextActive,
                    ]}
                  >
                    {z.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* ─── CARD 3: Comparación (Este período vs anterior) ─────── */}
        <View style={styles.card}>
          <View style={styles.cardHeaderRow}>
            <View style={styles.cardLabelRow}>
              <View style={styles.iconMiniBox}>
                <Ionicons name="calendar-outline" size={14} color="#5DD39E" />
              </View>
              <Text style={styles.cardSubTitle}>
                Historial · Comparación · {compareSubtitle}
              </Text>
            </View>
            <StatusBadge estado={estado} />
          </View>

          {/* Comparativa a dos columnas con línea divisoria */}
          <View style={styles.compareRow}>
            <View style={styles.compareCol}>
              <Text style={styles.compareLabel}>{compareLabelThis}</Text>
              <View style={styles.metricRowInline}>
                <Text style={styles.compareBigNumber}>
                  {formatValue(meta.thisPeriodCompare, unit)}
                </Text>
                <Text style={styles.compareUnitText}> {unit}</Text>
              </View>
            </View>

            <View style={styles.verticalDivider} />

            <View style={styles.compareCol}>
              <Text style={styles.compareLabel}>{compareLabelPrev}</Text>
              <View style={styles.metricRowInline}>
                <Text style={styles.compareBigNumber}>
                  {formatValue(meta.prevPeriodCompare, unit)}
                </Text>
                <Text style={styles.compareUnitText}> {unit}</Text>
              </View>
            </View>
          </View>

          {/* Notificación de estado */}
          <StatusChip
            title={meta.compareDesc}
            subtitle="Información comparativa frente al ciclo anterior"
            estado={estado}
          />
        </View>

        {/* ─── CARD 4: Costo estimado (Período actual) ───────────── */}
        <View style={styles.card}>
          <View style={styles.cardHeaderRow}>
            <View style={styles.cardLabelRow}>
              <View style={styles.iconMiniBox}>
                <Ionicons name="cash-outline" size={14} color="#5DD39E" />
              </View>
              <Text style={styles.cardSubTitle}>
                Historial · Costo estimado · {costSubtitle}
              </Text>
            </View>
            <StatusBadge estado={estado} />
          </View>

          <View style={styles.metricRow}>
            <Text style={styles.bigNumber}>
              {formatValue(meta.costEstimated, unit)}
            </Text>
            <Text style={styles.unitText}> {unit}</Text>
          </View>
          <Text style={styles.hintText}>
            Proyección estimada al cierre: {formatValue(meta.costProjection, unit)} {unit}
          </Text>

          {/* Notificación de impacto económico */}
          <StatusChip
            title={meta.costDesc}
            subtitle="Revisar impacto económico según el período seleccionado"
            estado={estado}
          />
        </View>

        {/* ─── BOTÓN DE ACCIÓN: Ver consejos ───────────────────── */}
        <TouchableOpacity
          style={styles.ctaButton}
          activeOpacity={0.85}
          onPress={() => router.push('/consejos')}
        >
          <Text style={styles.ctaButtonText}>Ver consejos</Text>
        </TouchableOpacity>

        {/* Espacio extra inferior para scroll */}
        <View style={{ height: 20 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Estilos ──────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#06120E',
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 8,
  },
  headerTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '700',
  },
  headerIconBtn: {
    padding: 6,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  greeting: {
    color: '#9EAEA8',
    fontSize: 14,
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 16,
  },

  // ─── Selector Período ───────────────────────────────────────
  periodSelectorContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 10,
    marginBottom: 18,
  },
  periodTab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: '#18382C',
    backgroundColor: '#0A1E17',
    gap: 6,
  },
  periodTabActive: {
    backgroundColor: '#113E2E',
    borderColor: '#246A4F',
  },
  periodTabText: {
    color: '#718096',
    fontSize: 13,
    fontWeight: '500',
  },
  periodTabTextActive: {
    color: '#5DD39E',
    fontWeight: '600',
  },

  // ─── Estilos Comunes de Cards ──────────────────────────────
  card: {
    backgroundColor: '#0B1D17',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#153328',
    padding: 16,
    marginBottom: 16,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  iconMiniBox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    backgroundColor: '#0E2E23',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  cardSubTitle: {
    color: '#8BA198',
    fontSize: 12,
    fontWeight: '500',
  },

  // ─── Métricas ───────────────────────────────────────────────
  metricRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginTop: 12,
  },
  metricRowInline: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginTop: 6,
  },
  bigNumber: {
    color: '#FFFFFF',
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  unitText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 4,
  },
  hintText: {
    color: '#73877F',
    fontSize: 12,
    marginTop: 4,
  },

  // ─── Gráfico de Consumo ─────────────────────────────────────
  rightIconsGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  chartIconBtn: {
    padding: 6,
    borderRadius: 6,
  },
  chartIconBtnActive: {
    backgroundColor: '#163B30',
  },

  // ─── Selector Unidad Kw / COP ───────────────────────────────
  unitToggleGroup: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
    marginTop: 16,
  },
  unitToggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#1B3F31',
    backgroundColor: '#0A1C16',
    gap: 6,
  },
  unitToggleBtnActive: {
    backgroundColor: '#123D2E',
    borderColor: '#267355',
  },
  unitToggleText: {
    color: '#718096',
    fontSize: 13,
    fontWeight: '500',
  },
  unitToggleTextActive: {
    color: '#5DD39E',
    fontWeight: '600',
  },

  // ─── Filtros de Zona ────────────────────────────────────────
  filterSectionTitle: {
    color: '#D1FAE5',
    fontSize: 13,
    fontWeight: '600',
    marginTop: 18,
    marginBottom: 10,
  },
  zoneChipsWrapper: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  zoneChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#1B3F31',
    backgroundColor: '#0A1C16',
    gap: 6,
  },
  zoneChipActive: {
    backgroundColor: '#123D2E',
    borderColor: '#267355',
  },
  zoneChipText: {
    color: '#718096',
    fontSize: 12,
    fontWeight: '500',
  },
  zoneChipTextActive: {
    color: '#5DD39E',
    fontWeight: '600',
  },

  // ─── Comparación Columnas ───────────────────────────────────
  compareRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 14,
  },
  compareCol: {
    flex: 1,
  },
  verticalDivider: {
    width: 1,
    height: 45,
    backgroundColor: '#1A3B2F',
    marginHorizontal: 12,
  },
  compareLabel: {
    color: '#7E9289',
    fontSize: 10,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  compareBigNumber: {
    color: '#FFFFFF',
    fontSize: 32,
    fontWeight: '700',
  },
  compareUnitText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
    marginLeft: 6,
  },

  // ─── Botón CTA ──────────────────────────────────────────────
  ctaButton: {
    backgroundColor: '#57D49D',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 6,
  },
  ctaButtonText: {
    color: '#061D15',
    fontSize: 15,
    fontWeight: '700',
  },
});
