// @ts-nocheck
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle } from 'react-native-svg';
import { Gauge } from '../components/Gauge';

// ─── Helpers ─────────────────────────────────────────────────────────────────
const estadoColor = (estado?: string) => {
  switch (estado) {
    case 'Elevado':  return '#D69E2E';
    case 'Crítico':  return '#E53E3E';
    default:          return '#5DD39E';
  }
};
const estadoBadgeBg = (estado?: string) => {
  switch (estado) {
    case 'Elevado':  return '#3B2A10';
    case 'Crítico':  return '#3B1010';
    default:          return '#0E2D22';
  }
};
const estadoIcon = (estado?: string) => {
  switch (estado) {
    case 'Elevado':  return 'warning-outline';
    case 'Crítico':  return 'alert-circle-outline';
    default:          return 'checkmark-circle-outline';
  }
};

interface Zona {
  id: number;
  nombre: string;
  descripcion?: string;
  consumo?: string;    // Ej: "0.6 Kw"
  estado?: string;     // Ej: "Normal", "Elevado", "Crítico"
  porcentaje?: number; // 0-100
}


// Datos mock (se reemplazan con API cuando devuelve datos)
const ZONAS_MOCK: Zona[] = [
  { id: 1, nombre: 'Room',    consumo: '0.6 Kw',  estado: 'Normal',  porcentaje: 25 },
  { id: 2, nombre: 'Kitchen', consumo: '0.75 Kw', estado: 'Elevado', porcentaje: 75 },
  { id: 3, nombre: 'Oficine', consumo: '0.5 Kw',  estado: 'Normal',  porcentaje: 50 },
];

// ─── Componente DonutChart (SVG) ──────────────────────────────────────────────
interface DonutChartProps {
  value: number;       // ej: 7.2
  maxValue: number;    // ej: 10
  unit: 'KW' | 'COP';
  size?: number;
  strokeWidth?: number;
}

const DonutChart: React.FC<DonutChartProps> = ({
  value,
  maxValue = 10,
  unit,
  size = 200,
  strokeWidth = 26,
}) => {
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const percentage = Math.min(Math.max(value / maxValue, 0), 1);
  const strokeDashoffset = circumference - percentage * circumference;

  const displayVal = unit === 'COP' ? (value * 1200).toFixed(0) : value.toFixed(1);
  const displayUnit = unit === 'COP' ? 'COP' : 'kW';

  return (
    <View style={{ alignItems: 'center', marginTop: 16, marginBottom: 8 }}>
      <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
        <Svg width={size} height={size}>
          {/* Círculo de fondo oscuro/apagado */}
          <Circle
            cx={center}
            cy={center}
            r={radius}
            stroke="#20382E"
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Círculo de progreso coloreado (comienza arriba a las 12 en punto) */}
          <Circle
            cx={center}
            cy={center}
            r={radius}
            stroke="#F6D543"
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
        <View style={{ position: 'absolute', alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ color: '#FFFFFF', fontSize: 36, fontWeight: 'bold' }}>
            {displayVal}
          </Text>
          <Text style={{ color: '#FFFFFF', fontSize: 16, fontWeight: '500', marginTop: -2 }}>
            {displayUnit}
          </Text>
        </View>
      </View>

      {/* Subtítulo bajo la gráfica */}
      <Text style={{ color: '#F6D543', fontSize: 15, fontWeight: '500', marginTop: 14 }}>
        Por encima de lo normal
      </Text>
    </View>
  );
};


export const DashboardScreen: React.FC = () => {
  const [unit, setUnit] = useState<'KW' | 'COP'>('KW');
  const [chartView, setChartView] = useState<'gauge' | 'donut'>('gauge'); // toggle Card 2
  const [zonaView, setZonaView] = useState<'grid' | 'list'>('list');
  const [zonas, setZonas] = useState<Zona[]>(ZONAS_MOCK);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const fetchDashboardData = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/salud/bd');
      const data = await response.json();
      if (data.zonas && data.zonas.length > 0) setZonas(data.zonas);
    } catch (error) {
      console.error('Error al cargar datos del backend:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchDashboardData(); }, []);
  const onRefresh = () => { setRefreshing(true); fetchDashboardData(); };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#5DD39E" />
      }
    >
      {/* ── HEADER ──────────────────────────────────────────────── */}
      <View style={styles.header}>
        <View style={{ width: 30 }} />
        <Text style={styles.headerTitle}>Panel Principal</Text>
        <TouchableOpacity style={styles.iconBtn}>
          <Ionicons name="notifications-outline" size={22} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      <Text style={styles.greeting}>Buenos días, Nicolás</Text>

      {/* ── CARD 1: CONSUMO ACTUAL (resumen) ────────────────────── */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <View style={styles.cardLabelRow}>
            <Ionicons name="flash-outline" size={15} color="#5DD39E" style={{ marginRight: 6 }} />
            <Text style={styles.cardSubTitle}>Panel principal · Consumo actual</Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: '#0E2D22' }]}>
            <Text style={[styles.badgeText, { color: '#5DD39E' }]}>Normal</Text>
          </View>
        </View>

        <Text style={styles.mainStatText}>2.25 Kw</Text>
        <Text style={styles.hintText}>revisar comparación según estado</Text>

        <View style={styles.statusChip}>
          <Ionicons name="checkmark-circle-outline" size={16} color="#5DD39E" />
          <Text style={styles.statusChipText}>
            {'Consumo (normal, elevado, crítico)\n'}
            <Text style={styles.statusChipSub}>Revisar consumo según state</Text>
          </Text>
        </View>
      </View>

      {/* ── CARD 2: CONSUMO ACTUAL ────────────────────────────────── */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardSubTitle}>Panel principal · Consumo actual</Text>
          <View style={styles.rightIcons}>
            {/* Botón Velocímetro */}
            <TouchableOpacity
              style={[styles.headerIconActive, chartView === 'gauge' && { backgroundColor: '#163B30' }]}
              onPress={() => setChartView('gauge')}
            >
              <Ionicons
                name="speedometer-outline"
                size={18}
                color={chartView === 'gauge' ? '#5DD39E' : '#A0AEC0'}
              />
            </TouchableOpacity>
            {/* Botón Donut / Circular */}
            <TouchableOpacity
              style={[{ marginLeft: 10, padding: 6, borderRadius: 8 }, chartView === 'donut' && { backgroundColor: '#163B30' }]}
              onPress={() => setChartView('donut')}
            >
              <Ionicons
                name="pie-chart-outline"
                size={18}
                color={chartView === 'donut' ? '#5DD39E' : '#A0AEC0'}
              />
            </TouchableOpacity>
          </View>
        </View>

        {chartView === 'gauge' ? (
          /* ── Vista velocímetro ── */
          <View style={{ alignItems: 'center', marginTop: 12 }}>
            <Gauge value={2.4} maxValue={10} size={220} strokeWidth={26} />
            <View style={{ flexDirection: 'row', alignItems: 'baseline', marginTop: -20 }}>
              <Text style={styles.gaugeValueText}>2.4</Text>
              <Text style={styles.gaugeUnitText}>{unit === 'KW' ? ' kW' : ' COP'}</Text>
            </View>
            <Text style={styles.gaugeStatusText}>Dentro de lo esperado</Text>
          </View>
        ) : (
          /* ── Vista donut circular ── */
          <DonutChart value={7.2} maxValue={10} unit={unit} />
        )}

        <View style={[styles.toggleGroup, { justifyContent: 'center', marginTop: 14 }]}>
          <TouchableOpacity
            style={[styles.toggleBtn, unit === 'KW' ? styles.toggleBtnActive : null]}
            onPress={() => setUnit('KW')}
          >
            <Ionicons name="flash-outline" size={14} color={unit === 'KW' ? '#5DD39E' : '#A0AEC0'} />
            <Text style={[styles.toggleText, unit === 'KW' ? styles.toggleTextActive : null]}>Kw</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.toggleBtn, unit === 'COP' ? styles.toggleBtnActive : null]}
            onPress={() => setUnit('COP')}
          >
            <Ionicons name="flash-outline" size={14} color={unit === 'COP' ? '#5DD39E' : '#A0AEC0'} />
            <Text style={[styles.toggleText, unit === 'COP' ? styles.toggleTextActive : null]}>COP</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* ── CARD 3: CONSUMO ACUMULADO ───────────────────────────── */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <View style={styles.cardLabelRow}>
            <Ionicons name="analytics-outline" size={15} color="#5DD39E" style={{ marginRight: 6 }} />
            <Text style={styles.cardSubTitle} numberOfLines={1}>Panel principal · Consumo acumulado · Hoy</Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: '#0E2D22' }]}>
            <Text style={[styles.badgeText, { color: '#5DD39E' }]}>Normal</Text>
          </View>
        </View>

        <Text style={styles.mainStatText}>127 KWh · COP</Text>

        <View style={styles.progressRow}>
          <Text style={styles.progressLabel}>Progreso hacia el objetivo</Text>
          <Text style={styles.progressPercent}>68%</Text>
        </View>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: '68%' }]} />
        </View>

        <View style={{ marginTop: 10 }}>
          <Text style={styles.limitLabel}>LÍMITE</Text>
          <Text style={styles.limitValue}>187 kWh</Text>
        </View>

        <View style={styles.statusChip}>
          <Ionicons name="checkmark-circle-outline" size={16} color="#5DD39E" />
          <Text style={styles.statusChipText}>
            {'Consumo de acuerdo al límite(normal, elevado,crítico)\n'}
            <Text style={styles.statusChipSub}>
              Estas por (de acuerdo al estado) del límite o consumo
            </Text>
          </Text>
        </View>
      </View>

      {/* ── SECCIÓN ZONES ───────────────────────────────────────── */}
      <View style={styles.zonesSectionHeader}>
        <Text style={styles.sectionTitle}>Zones</Text>
        <View style={styles.rightIcons}>
          <TouchableOpacity
            style={[
              styles.viewToggleBtn,
              zonaView === 'grid' && styles.viewToggleBtnActive,
            ]}
            onPress={() => setZonaView('grid')}
          >
            <Ionicons
              name="grid-outline"
              size={18}
              color={zonaView === 'grid' ? '#5DD39E' : '#A0AEC0'}
            />
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.viewToggleBtn,
              zonaView === 'list' && styles.viewToggleBtnActive,
            ]}
            onPress={() => setZonaView('list')}
          >
            <Ionicons
              name="list-outline"
              size={20}
              color={zonaView === 'list' ? '#5DD39E' : '#A0AEC0'}
            />
          </TouchableOpacity>
        </View>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color="#5DD39E" style={{ marginTop: 20 }} />
      ) : zonaView === 'grid' ? (
        /* ── VISTA GRID (compacta, 2 columnas) ── */
        <View style={styles.zonesGrid}>
          {zonas.map((zona) => {
            const color   = estadoColor(zona.estado);
            const bgBadge = estadoBadgeBg(zona.estado);
            const icon    = estadoIcon(zona.estado);
            return (
              <View key={zona.id} style={styles.zoneCardGrid}>
                {/* Fila top: icono cama + nombre + badge ícono */}
                <View style={styles.zoneTopRow}>
                  <View style={styles.zoneIconBox}>
                    <Ionicons name="bed-outline" size={15} color="#FFFFFF" />
                  </View>
                  <Text style={styles.zoneNameGrid} numberOfLines={1}>{zona.nombre}</Text>
                  <View style={{ marginLeft: 'auto' }}>
                    <Ionicons name={icon as any} size={16} color={color} />
                  </View>
                </View>

                {/* Valor con unidad en la misma línea */}
                <View style={{ flexDirection: 'row', alignItems: 'baseline', marginTop: 6 }}>
                  <Text style={[styles.zoneValueGrid, { color }]}>
                    {zona.consumo?.replace(' Kw', '') || '0.5'}
                  </Text>
                  <Text style={styles.zoneUnitGrid}> k {unit === 'COP' ? 'COP' : 'kw'}</Text>
                </View>

                {/* Estado + porcentaje en la misma línea */}
                <View style={styles.zoneBottomRow}>
                  <Text style={[styles.zoneStatusLabel, { color, fontSize: 11 }]}>
                    {zona.estado || 'Normal'}
                  </Text>
                  <Text style={styles.zonePctText}>{zona.porcentaje ?? 50}%</Text>
                </View>

                <View style={styles.progressTrack}>
                  <View
                    style={[
                      styles.progressFill,
                      { width: `${zona.porcentaje ?? 50}%`, backgroundColor: color },
                    ]}
                  />
                </View>
              </View>
            );
          })}
        </View>
      ) : (
        /* ── VISTA LISTA (detallada, 1 columna) ── */
        <View>
          {zonas.map((zona) => {
            const color   = estadoColor(zona.estado);
            const bgBadge = estadoBadgeBg(zona.estado);
            const icon    = estadoIcon(zona.estado);
            return (
              <View key={zona.id} style={styles.zoneCard}>
                {/* Fila: icono + nombre + badge */}
                <View style={styles.zoneTopRow}>
                  <View style={styles.zoneIconBox}>
                    <Ionicons name="bed-outline" size={18} color="#FFFFFF" />
                  </View>
                  <Text style={styles.zoneName}>{zona.nombre}</Text>
                  <View style={[styles.statusBadge, { backgroundColor: bgBadge, marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 4 }]}>
                    <Ionicons name={icon as any} size={12} color={color} />
                    <Text style={[styles.badgeText, { color }]}>{zona.estado || 'Normal'}</Text>
                  </View>
                </View>

                <Text style={[styles.zoneValue, { color }]}>{zona.consumo || '0.5 Kw'}</Text>
                <Text style={[styles.zoneStatusLabel, { color }]}>{zona.estado || 'Normal'}</Text>

                <View style={styles.progressTrack}>
                  <View
                    style={[
                      styles.progressFill,
                      { width: `${zona.porcentaje ?? 50}%`, backgroundColor: color },
                    ]}
                  />
                </View>
              </View>
            );
          })}
        </View>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  // ── Layout ──────────────────────────────────────────────────
  container: {
    flex: 1,
    backgroundColor: '#0D1F1A',
  },
  contentContainer: {
    padding: 20,
    paddingBottom: 40,
  },

  // ── Header ──────────────────────────────────────────────────
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    borderBottomColor: '#FFFFFF14',
    borderBottomWidth: 1,
    paddingBottom: 12,
    marginHorizontal: -20,
    paddingHorizontal: 20,
  },
  headerTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: 'bold',
    textAlign: 'center',
    flex: 1,
  },
  iconBtn: { padding: 4 },

  // ── Greeting ─────────────────────────────────────────────────
  greeting: {
    color: '#A0AEC0',
    fontSize: 15,
    textAlign: 'center',
    marginVertical: 16,
  },

  // ── Cards ────────────────────────────────────────────────────
  card: {
    backgroundColor: '#162B25',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#FFFFFF12',
    marginBottom: 16,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
  },
  cardLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    flexShrink: 1,
  },
  cardSubTitle: {
    color: '#718096',
    fontSize: 12,
    flexShrink: 1,
  },
  rightIcons: { flexDirection: 'row', alignItems: 'center' },
  headerIconActive: {
    backgroundColor: '#163B30',
    padding: 6,
    borderRadius: 8,
  },

  // ── Status badge ──────────────────────────────────────────────
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 20,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
  },

  // ── Main stat ─────────────────────────────────────────────────
  mainStatText: {
    color: '#FFFFFF',
    fontSize: 32,
    fontWeight: 'bold',
    marginTop: 10,
  },
  hintText: {
    color: '#718096',
    fontSize: 12,
    marginTop: 4,
  },

  // ── Status chip ───────────────────────────────────────────────
  statusChip: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#0D2119',
    borderRadius: 10,
    padding: 10,
    marginTop: 14,
    borderWidth: 1,
    borderColor: '#1A3B2D',
  },
  statusChipText: {
    color: '#5DD39E',
    fontSize: 12,
    fontWeight: '500',
    flex: 1,
  },
  statusChipSub: {
    color: '#718096',
    fontSize: 11,
    fontWeight: '400',
  },

  // ── Gauge ────────────────────────────────────────────────────
  gaugeValueText: {
    color: '#FFFFFF',
    fontSize: 38,
    fontWeight: 'bold',
  },
  gaugeUnitText: {
    color: '#FFFFFF',
    fontSize: 22,
    fontWeight: 'bold',
  },
  gaugeStatusText: {
    color: '#D69E2E',
    fontSize: 14,
    marginTop: 4,
    fontWeight: '500',
  },

  // ── Toggles ──────────────────────────────────────────────────
  toggleGroup: {
    flexDirection: 'row',
    gap: 10,
  },
  toggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#1A362D',
    gap: 5,
  },
  toggleBtnActive: { backgroundColor: '#163B30' },
  toggleText: { color: '#718096', fontSize: 13 },
  toggleTextActive: { color: '#5DD39E', fontWeight: '600' },

  // ── Progress bar ─────────────────────────────────────────────
  progressRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  progressLabel: { color: '#718096', fontSize: 12 },
  progressPercent: { color: '#A0AEC0', fontSize: 12, fontWeight: '600' },
  progressTrack: {
    height: 6,
    backgroundColor: '#0D2119',
    borderRadius: 4,
    marginTop: 6,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#5DD39E',
    borderRadius: 4,
  },

  // ── Límite ───────────────────────────────────────────────────
  limitLabel: {
    color: '#718096',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1,
  },
  limitValue: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
    marginTop: 2,
  },

  // ── Zones section ────────────────────────────────────────────
  zonesSectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    marginTop: 4,
  },
  sectionTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: 'bold',
  },
  zoneCard: {
    backgroundColor: '#162B25',
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#FFFFFF12',
  },
  zoneTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  zoneIconBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#0D2119',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  zoneName: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '500',
  },
  zoneValue: {
    fontSize: 24,
    fontWeight: 'bold',
    marginTop: 4,
    marginBottom: 2,
  },
  zoneStatusLabel: {
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 6,
  },

  // ── View toggle buttons (grid / list) ────────────────────────
  viewToggleBtn: {
    padding: 6,
    borderRadius: 8,
    marginLeft: 6,
  },
  viewToggleBtnActive: {
    backgroundColor: '#163B30',
  },

  // ── Grid layout (2 columnas) ──────────────────────────────────
  zonesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  zoneCardGrid: {
    backgroundColor: '#162B25',
    width: '48.5%',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#FFFFFF12',
  },
  zoneNameGrid: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
    marginHorizontal: 6,
  },
  zoneValueGrid: {
    fontSize: 22,
    fontWeight: 'bold',
  },
  zoneUnitGrid: {
    color: '#A0AEC0',
    fontSize: 12,
    fontWeight: '500',
    marginLeft: 2,
  },
  zoneBottomRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
    marginBottom: 4,
  },
  zonePctText: {
    color: '#718096',
    fontSize: 11,
  },
});