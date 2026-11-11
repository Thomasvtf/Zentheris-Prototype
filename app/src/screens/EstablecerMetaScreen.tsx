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
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

type Unidad = 'kWh' | 'COP';
type TipoMeta = 'ahorro' | 'eficiencia' | 'presupuesto';

export function EstablecerMetaScreen() {
  const router = useRouter();

  // Estados interactivos
  const [unidad, setUnidad] = useState<Unidad>('kWh');
  const [metaKwh, setMetaKwh] = useState<number>(330);
  const [metaCop, setMetaCop] = useState<number>(280000);
  const [tipoMeta, setTipoMeta] = useState<TipoMeta>('ahorro');

  // Ajustes de valor
  const handleDecrementar = () => {
    if (unidad === 'kWh') {
      setMetaKwh((prev) => Math.max(50, prev - 10));
    } else {
      setMetaCop((prev) => Math.max(50000, prev - 10000));
    }
  };

  const handleIncrementar = () => {
    if (unidad === 'kWh') {
      setMetaKwh((prev) => prev + 10);
    } else {
      setMetaCop((prev) => prev + 10000);
    }
  };

  // Cálculo de promedio diario
  const promedioDiario =
    unidad === 'kWh'
      ? `${(metaKwh / 30).toFixed(1)} kWh por día`
      : `$ ${Math.round(metaCop / 30).toLocaleString('es-CO')} COP por día`;

  const handleGuardar = () => {
    const valorTexto =
      unidad === 'kWh'
        ? `${metaKwh} kWh`
        : `$ ${metaCop.toLocaleString('es-CO')} COP`;

    Alert.alert(
      'Meta establecida',
      `Tu nueva meta mensual de ${valorTexto} (${tipoMeta}) ha sido guardada exitosamente.`,
      [{ text: 'Entendido', onPress: () => router.back() }]
    );
  };

  const handleAyuda = () => {
    Alert.alert(
      'Acerca de las metas de consumo',
      'Definir una meta te ayuda a mantener el consumo dentro de un rango planificado. Te enviaremos alertas si tu proyección mensual supera el objetivo fijado.'
    );
  };

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
        <Text style={styles.headerTitle}>Establecer meta</Text>
        <TouchableOpacity
          style={styles.headerBtn}
          activeOpacity={0.7}
          onPress={handleAyuda}
        >
          <Ionicons
            name="help-circle-outline"
            size={24}
            color="#5E8275"
          />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Tarjeta: Consumo promedio actual ───────────────── */}
        <View style={styles.avgCard}>
          <View style={styles.avgTopRow}>
            <Text style={styles.avgLabel}>Consumo promedio actual</Text>
            <Text style={styles.avgPeriod}>Últimos 30 días</Text>
          </View>
          <Text style={styles.avgValue}>
            {unidad === 'kWh' ? '14.2  kWh/día' : '$ 12.800 COP/día'}
          </Text>
          <View style={styles.avgBadge}>
            <Text style={styles.avgBadgeText}>Referencia de tu consumo</Text>
          </View>
        </View>

        {/* ─── Sección: Define tu meta ────────────────────────── */}
        <Text style={styles.sectionTitle}>Define tu meta</Text>
        <Text style={styles.sectionSubtitle}>
          Elige cómo quieres medir tus objetivos de consumo.
        </Text>

        {/* Selector de Unidad */}
        <View style={styles.unitCard}>
          <View style={styles.unitTextContainer}>
            <Text style={styles.unitTitle}>Unidad de la meta</Text>
            <Text style={styles.unitSubtitle}>
              La misma unidad se aplicará a la meta diaria y mensual.
            </Text>
          </View>

          <View style={styles.unitToggleGroup}>
            <TouchableOpacity
              style={[
                styles.unitToggleBtn,
                unidad === 'kWh' && styles.unitToggleBtnActive,
              ]}
              activeOpacity={0.8}
              onPress={() => setUnidad('kWh')}
            >
              <Text
                style={[
                  styles.unitToggleText,
                  unidad === 'kWh' && styles.unitToggleTextActive,
                ]}
              >
                kWh
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.unitToggleBtn,
                unidad === 'COP' && styles.unitToggleBtnActive,
              ]}
              activeOpacity={0.8}
              onPress={() => setUnidad('COP')}
            >
              <Text
                style={[
                  styles.unitToggleText,
                  unidad === 'COP' && styles.unitToggleTextActive,
                ]}
              >
                COP
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Tarjeta Destacada: Meta mensual */}
        <View style={styles.metaCard}>
          <View style={styles.metaTopRow}>
            <Text style={styles.metaTitle}>Meta mensual</Text>
            <View style={styles.metaBadge}>
              <Text style={styles.metaBadgeText}>Por mes</Text>
            </View>
          </View>

          {/* Contador interactivo */}
          <View style={styles.counterRow}>
            <TouchableOpacity
              style={styles.counterBtn}
              activeOpacity={0.7}
              onPress={handleDecrementar}
            >
              <Ionicons name="remove" size={24} color="#FFFFFF" />
            </TouchableOpacity>

            <View style={styles.valueWrapper}>
              <Text style={styles.counterValue}>
                {unidad === 'kWh'
                  ? metaKwh
                  : `$ ${metaCop.toLocaleString('es-CO')}`}
              </Text>
              {unidad === 'kWh' && (
                <Text style={styles.counterUnit}>kWh</Text>
              )}
            </View>

            <TouchableOpacity
              style={styles.counterBtn}
              activeOpacity={0.7}
              onPress={handleIncrementar}
            >
              <Ionicons name="add" size={24} color="#FFFFFF" />
            </TouchableOpacity>
          </View>

          <View style={styles.metaDivider} />

          <Text style={styles.metaEquivText}>
            Equivale a un promedio de {promedioDiario}
          </Text>
        </View>

        {/* ─── Sección: Tipo de meta ──────────────────────────── */}
        <Text style={[styles.sectionTitle, { marginTop: 8 }]}>Tipo de meta</Text>
        <Text style={styles.sectionSubtitle}>
          Selecciona el enfoque que quieres priorizar.
        </Text>

        <View style={styles.tipoMetaCard}>
          <View style={styles.tipoMetaPillsRow}>
            <TouchableOpacity
              style={[
                styles.tipoPill,
                tipoMeta === 'ahorro' && styles.tipoPillActive,
              ]}
              activeOpacity={0.8}
              onPress={() => setTipoMeta('ahorro')}
            >
              <Text
                style={[
                  styles.tipoPillText,
                  tipoMeta === 'ahorro' && styles.tipoPillTextActive,
                ]}
              >
                Ahorro
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.tipoPill,
                tipoMeta === 'eficiencia' && styles.tipoPillActive,
              ]}
              activeOpacity={0.8}
              onPress={() => setTipoMeta('eficiencia')}
            >
              <Text
                style={[
                  styles.tipoPillText,
                  tipoMeta === 'eficiencia' && styles.tipoPillTextActive,
                ]}
              >
                Eficiencia
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.tipoPill,
                tipoMeta === 'presupuesto' && styles.tipoPillActive,
              ]}
              activeOpacity={0.8}
              onPress={() => setTipoMeta('presupuesto')}
            >
              <Text
                style={[
                  styles.tipoPillText,
                  tipoMeta === 'presupuesto' && styles.tipoPillTextActive,
                ]}
              >
                Presupuesto
              </Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.tipoDescText}>
            {tipoMeta === 'ahorro' &&
              'Reduce tu consumo con respecto al promedio de los últimos 30 días.'}
            {tipoMeta === 'eficiencia' &&
              'Optimiza las horas de uso y minimiza los picos de consumo diario.'}
            {tipoMeta === 'presupuesto' &&
              'Controla tu costo monetario proyectado para la factura del período.'}
          </Text>
        </View>

        {/* ─── Botón: Guardar meta ────────────────────────────── */}
        <TouchableOpacity
          style={styles.btnGuardar}
          activeOpacity={0.85}
          onPress={handleGuardar}
        >
          <Text style={styles.btnGuardarText}>Guardar meta</Text>
        </TouchableOpacity>

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
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 6,
  },

  // ─── Tarjeta Consumo Promedio ──────────────────────────────────
  avgCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 18,
    marginBottom: 20,
  },
  avgTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  avgLabel: {
    color: '#8EA299',
    fontSize: 13,
  },
  avgPeriod: {
    color: '#8EA299',
    fontSize: 13,
  },
  avgValue: {
    color: '#5DD39E',
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  avgBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#123027',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1E473B',
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  avgBadgeText: {
    color: '#8EA299',
    fontSize: 11.5,
    fontWeight: '500',
  },

  // ─── Secciones ─────────────────────────────────────────────────
  sectionTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
    marginBottom: 4,
  },
  sectionSubtitle: {
    color: '#8EA299',
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 14,
  },

  // ─── Unidad de la Meta ─────────────────────────────────────────
  unitCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  unitTextContainer: {
    flex: 1,
    marginRight: 12,
  },
  unitTitle: {
    color: '#FFFFFF',
    fontSize: 14.5,
    fontWeight: '600',
    marginBottom: 3,
  },
  unitSubtitle: {
    color: '#8EA299',
    fontSize: 12,
    lineHeight: 16,
  },
  unitToggleGroup: {
    flexDirection: 'row',
    backgroundColor: '#0A1C16',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 3,
  },
  unitToggleBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
  },
  unitToggleBtnActive: {
    backgroundColor: '#5DD39E',
  },
  unitToggleText: {
    color: '#8EA299',
    fontSize: 12.5,
    fontWeight: '600',
  },
  unitToggleTextActive: {
    color: '#062218',
    fontWeight: '700',
  },

  // ─── Meta Mensual (Destacada) ──────────────────────────────────
  metaCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#34D399',
    padding: 18,
    marginBottom: 20,
  },
  metaTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  metaTitle: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  metaBadge: {
    backgroundColor: '#12382B',
    borderRadius: 12,
    paddingHorizontal: 9,
    paddingVertical: 3,
  },
  metaBadgeText: {
    color: '#34D399',
    fontSize: 11,
    fontWeight: '600',
  },
  counterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 10,
  },
  counterBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#0A1F18',
    borderWidth: 1,
    borderColor: '#1C4235',
    alignItems: 'center',
    justifyContent: 'center',
  },
  valueWrapper: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginHorizontal: 18,
  },
  counterValue: {
    color: '#5DD39E',
    fontSize: 36,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  counterUnit: {
    color: '#5DD39E',
    fontSize: 22,
    fontWeight: '600',
    marginLeft: 8,
  },
  metaDivider: {
    height: 1,
    backgroundColor: '#16362B',
    marginTop: 18,
    marginBottom: 14,
  },
  metaEquivText: {
    color: '#8EA299',
    fontSize: 12.5,
    textAlign: 'center',
  },

  // ─── Tipo de Meta ──────────────────────────────────────────────
  tipoMetaCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 16,
    marginBottom: 24,
  },
  tipoMetaPillsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  tipoPill: {
    backgroundColor: '#0A1C16',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#1C3F33',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  tipoPillActive: {
    backgroundColor: '#5DD39E',
    borderColor: '#5DD39E',
  },
  tipoPillText: {
    color: '#8EA299',
    fontSize: 12.5,
    fontWeight: '600',
  },
  tipoPillTextActive: {
    color: '#062218',
    fontWeight: '700',
  },
  tipoDescText: {
    color: '#8EA299',
    fontSize: 12.5,
    lineHeight: 18,
    marginTop: 14,
  },

  // ─── Botón Guardar Meta ────────────────────────────────────────
  btnGuardar: {
    backgroundColor: '#5DD39E',
    borderRadius: 12,
    height: 50,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnGuardarText: {
    color: '#062218',
    fontSize: 15.5,
    fontWeight: '700',
  },
});

