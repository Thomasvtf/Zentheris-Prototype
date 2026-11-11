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
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

export function FuentesDatosScreen() {
  const router = useRouter();

  // Permite alternar entre el estado con datos y el estado "Sin datos" mostrado en tus diseños
  const [hasData, setHasData] = useState(true);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#071510" />

      {/* ─── Header ─────────────────────────────────────────── */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.headerBtn}
          activeOpacity={0.7}
          onPress={() => router.back()}
        >
          <Ionicons name="chevron-back" size={24} color="#E6FAF0" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Fuentes de datos</Text>
        {/* Botón sutil para alternar entre vista normal y sin datos */}
        <TouchableOpacity
          style={styles.toggleStateBtn}
          activeOpacity={0.7}
          onPress={() => setHasData(!hasData)}
        >
          <Ionicons
            name={hasData ? 'swap-horizontal' : 'refresh'}
            size={18}
            color="#5E8275"
          />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Tarjeta Informativa Superior ───────────────────── */}
        <View style={styles.infoBanner}>
          <Ionicons
            name="information-circle-outline"
            size={22}
            color="#34D399"
            style={{ marginRight: 12, marginTop: 1 }}
          />
          <Text style={styles.infoBannerText}>
            Consulta de solo lectura de la fuente principal y de los sensores de cada zona.
          </Text>
        </View>

        {/* ─── Sección: Fuente principal ──────────────────────── */}
        <Text style={styles.sectionTitle}>Fuente principal</Text>

        <View style={styles.cardItem}>
          <View style={styles.mainIconBox}>
            <Ionicons name="flash-outline" size={22} color="#34D399" />
          </View>

          <View style={styles.cardCenterContent}>
            <Text style={styles.cardTitle}>Fuente principal Casa García</Text>
            <Text style={styles.cardSubtitle}>Suma de los sensores activos</Text>
          </View>

          <View style={styles.cardRightContent}>
            <View style={styles.valueRow}>
              <Text style={styles.metricNumber}>{hasData ? '0, 52' : '—'}</Text>
              <Text style={styles.metricUnit}> kW</Text>
            </View>

            {hasData ? (
              <View style={styles.statusRow}>
                <Ionicons
                  name="checkmark-circle-outline"
                  size={15}
                  color="#34D399"
                />
                <Text style={styles.statusActiveText}>Activo</Text>
              </View>
            ) : (
              <View style={styles.statusRow}>
                <Ionicons
                  name="sparkles-outline"
                  size={14}
                  color="#8EA299"
                />
                <Text style={styles.statusMutedText}>Sin datos</Text>
              </View>
            )}
          </View>
        </View>

        {/* ─── Sección: Sensores por zona ─────────────────────── */}
        <Text style={[styles.sectionTitle, { marginTop: 20 }]}>
          Sensores por zona
        </Text>

        {/* 1. Sensor Cocina */}
        <View style={styles.cardItem}>
          <View style={styles.zoneIconBox}>
            <MaterialCommunityIcons
              name="fridge-outline"
              size={22}
              color="#8EA299"
            />
          </View>

          <View style={styles.cardCenterContent}>
            <Text style={styles.cardTitle}>Sensor Cocina</Text>
            <Text style={styles.cardSubtitle}>Cocina</Text>
          </View>

          <View style={styles.cardRightContent}>
            <View style={styles.valueRow}>
              <Text style={styles.metricNumber}>{hasData ? '0, 21' : '—'}</Text>
              <Text style={styles.metricUnit}> kW</Text>
            </View>

            {hasData ? (
              <View style={styles.statusRow}>
                <Ionicons
                  name="checkmark-circle-outline"
                  size={15}
                  color="#34D399"
                />
                <Text style={styles.statusActiveText}>Activo</Text>
              </View>
            ) : (
              <View style={styles.statusRow}>
                <Ionicons
                  name="sparkles-outline"
                  size={14}
                  color="#8EA299"
                />
                <Text style={styles.statusMutedText}>Sin datos</Text>
              </View>
            )}
          </View>
        </View>

        {/* 2. Sensor Dormitorio */}
        <View style={styles.cardItem}>
          <View style={styles.zoneIconBox}>
            <Ionicons name="bed-outline" size={22} color="#8EA299" />
          </View>

          <View style={styles.cardCenterContent}>
            <Text style={styles.cardTitle}>Sensor Dormitorio</Text>
            <Text style={styles.cardSubtitle}>Dormitorio</Text>
          </View>

          <View style={styles.cardRightContent}>
            <View style={styles.valueRow}>
              <Text style={styles.metricNumber}>{hasData ? '0, 19' : '—'}</Text>
              <Text style={styles.metricUnit}> kW</Text>
            </View>

            {hasData ? (
              <View style={styles.statusRow}>
                <Ionicons
                  name="checkmark-circle-outline"
                  size={15}
                  color="#34D399"
                />
                <Text style={styles.statusActiveText}>Activo</Text>
              </View>
            ) : (
              <View style={styles.statusRow}>
                <Ionicons
                  name="sparkles-outline"
                  size={14}
                  color="#8EA299"
                />
                <Text style={styles.statusMutedText}>Sin datos</Text>
              </View>
            )}
          </View>
        </View>

        {/* 3. Sensor Oficina (Pausado cuando hay datos) */}
        <View style={styles.cardItem}>
          <View style={styles.zoneIconBox}>
            <Ionicons name="desktop-outline" size={21} color="#8EA299" />
          </View>

          <View style={styles.cardCenterContent}>
            <Text style={styles.cardTitle}>Sensor Oficina</Text>
            <Text style={styles.cardSubtitle}>Oficina</Text>
          </View>

          <View style={styles.cardRightContent}>
            <View style={styles.valueRow}>
              <Text style={styles.metricNumber}>—</Text>
              <Text style={styles.metricUnit}> kW</Text>
            </View>

            {hasData ? (
              <View style={styles.statusRow}>
                <Ionicons
                  name="pause-circle-outline"
                  size={15}
                  color="#8EA299"
                />
                <Text style={styles.statusMutedText}>Pausado</Text>
              </View>
            ) : (
              <View style={styles.statusRow}>
                <Ionicons
                  name="sparkles-outline"
                  size={14}
                  color="#8EA299"
                />
                <Text style={styles.statusMutedText}>Sin datos</Text>
              </View>
            )}
          </View>
        </View>

        {/* 4. Sensor Sala */}
        <View style={styles.cardItem}>
          <View style={styles.zoneIconBox}>
            <MaterialCommunityIcons
              name="sofa-outline"
              size={22}
              color="#8EA299"
            />
          </View>

          <View style={styles.cardCenterContent}>
            <Text style={styles.cardTitle}>Sensor Sala</Text>
            <Text style={styles.cardSubtitle}>Sala</Text>
          </View>

          <View style={styles.cardRightContent}>
            <View style={styles.valueRow}>
              <Text style={styles.metricNumber}>{hasData ? '0, 12' : '—'}</Text>
              <Text style={styles.metricUnit}> kW</Text>
            </View>

            {hasData ? (
              <View style={styles.statusRow}>
                <Ionicons
                  name="checkmark-circle-outline"
                  size={15}
                  color="#34D399"
                />
                <Text style={styles.statusActiveText}>Activo</Text>
              </View>
            ) : (
              <View style={styles.statusRow}>
                <Ionicons
                  name="sparkles-outline"
                  size={14}
                  color="#8EA299"
                />
                <Text style={styles.statusMutedText}>Sin datos</Text>
              </View>
            )}
          </View>
        </View>

        {/* ─── Nota al pie ─────────────────────────────────────── */}
        <Text style={styles.footerNote}>
          Valores en kW de la última hora completa (14:00–15:00). «Sin datos» significa que no llegó la lectura de esa hora; no es consumo cero.
        </Text>

        <View style={{ height: 28 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#071510',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 10,
  },
  headerBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    color: '#E6FAF0',
    fontSize: 21,
    fontWeight: '700',
    letterSpacing: -0.2,
  },
  toggleStateBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    backgroundColor: '#0E241E',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 6,
  },

  // ─── Tarjeta Informativa Superior ──────────────────────────────
  infoBanner: {
    backgroundColor: '#0E241E',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#34D399',
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 18,
  },
  infoBannerText: {
    color: '#8EA299',
    fontSize: 13,
    lineHeight: 18,
    flex: 1,
  },

  // ─── Títulos de Sección ────────────────────────────────────────
  sectionTitle: {
    color: '#FFFFFF',
    fontSize: 16.5,
    fontWeight: '700',
    marginBottom: 12,
  },

  // ─── Tarjeta de Fuente / Sensor ────────────────────────────────
  cardItem: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  mainIconBox: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: '#133027',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  zoneIconBox: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: '#132822',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  cardCenterContent: {
    flex: 1,
    marginRight: 8,
  },
  cardTitle: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 3,
  },
  cardSubtitle: {
    color: '#8EA299',
    fontSize: 12.5,
  },
  cardRightContent: {
    alignItems: 'flex-end',
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: 4,
  },
  metricNumber: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  metricUnit: {
    color: '#8EA299',
    fontSize: 12.5,
    fontWeight: '500',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statusActiveText: {
    color: '#34D399',
    fontSize: 12.5,
    fontWeight: '600',
  },
  statusMutedText: {
    color: '#8EA299',
    fontSize: 12.5,
    fontWeight: '500',
  },

  // ─── Nota al Pie ───────────────────────────────────────────────
  footerNote: {
    color: '#8EA299',
    fontSize: 12.5,
    lineHeight: 18,
    marginTop: 10,
    marginBottom: 16,
  },
});

