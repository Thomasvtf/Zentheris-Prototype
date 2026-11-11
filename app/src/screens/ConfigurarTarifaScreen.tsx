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
  TextInput,
  Modal,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

const OPERADORES_COLOMBIA = [
  'Enel Colombia',
  'EPM (Empresas Públicas de Medellín)',
  'Celsia',
  'Air-e',
  'Afinia',
  'Electrificadora de Santander (ESSA)',
  'Chec Grupo EPM',
  'Otro operador',
];

const MESES_VIGENCIA = [
  'Julio de 2026',
  'Agosto de 2026',
  'Septiembre de 2026',
  'Octubre de 2026',
  'Noviembre de 2026',
  'Diciembre de 2026',
];

export function ConfigurarTarifaScreen() {
  const router = useRouter();

  // Estados de la tarifa activa
  const [tarifaActiva, setTarifaActiva] = useState({
    operador: 'Enel Colombia',
    tipo: 'Residencial',
    valor: '892',
    vigencia: 'septiembre de 2026',
    fuente: 'valor de mi factura',
  });

  // Estados del formulario editable
  const [operador, setOperador] = useState('Enel Colombia');
  const [valorKwh, setValorKwh] = useState('892');
  const [vigenteDesde, setVigenteDesde] = useState('Septiembre de 2026');

  // Modales de selección
  const [showOperadorModal, setShowOperadorModal] = useState(false);
  const [showVigenciaModal, setShowVigenciaModal] = useState(false);

  const handleGuardar = () => {
    if (!valorKwh.trim() || isNaN(Number(valorKwh.replace(/,/g, '')))) {
      Alert.alert('Valor inválido', 'Por favor ingresa un valor numérico válido por kWh.');
      return;
    }

    setTarifaActiva({
      operador,
      tipo: 'Residencial',
      valor: valorKwh.trim(),
      vigencia: vigenteDesde.toLowerCase(),
      fuente: 'valor de mi factura',
    });

    Alert.alert(
      'Tarifa actualizada',
      `Se ha configurado la tarifa de $${valorKwh.trim()} / kWh para ${operador} vigente desde ${vigenteDesde}.`,
      [{ text: 'Entendido', onPress: () => router.back() }]
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
        <Text style={styles.headerTitle}>Configurar tarifa</Text>
        <View style={styles.headerBtn} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Tarjeta Destacada: Tarifa Activa ───────────────── */}
        <View style={styles.activeCard}>
          <View style={styles.activeTopRow}>
            <View>
              <Text style={styles.activeTitle}>Tarifa activa</Text>
              <Text style={styles.activeSubtitle}>
                {tarifaActiva.operador} · {tarifaActiva.tipo}
              </Text>
            </View>
            <View style={styles.badgeActiva}>
              <View style={styles.badgeDot} />
              <Text style={styles.badgeActivaText}>Activa</Text>
            </View>
          </View>

          {/* Métrica Grande: $892 / kWh */}
          <View style={styles.metricRow}>
            <Text style={styles.metricCurrency}>${tarifaActiva.valor}</Text>
            <Text style={styles.metricSlash}> / </Text>
            <Text style={styles.metricUnit}>kWh</Text>
          </View>

          <Text style={styles.activeInfoText}>
            Vigente desde {tarifaActiva.vigencia}
          </Text>
          <Text style={styles.activeInfoText}>
            Fuente: {tarifaActiva.fuente}
          </Text>

          <TouchableOpacity
            style={styles.btnEditarTarifa}
            activeOpacity={0.7}
            onPress={() => {
              Alert.alert('Modo edición', 'Puedes modificar los campos de abajo y pulsar "Guardar tarifa".');
            }}
          >
            <Text style={styles.btnEditarTarifaText}>Editar tarifa</Text>
          </TouchableOpacity>
        </View>

        {/* ─── Sección: Actualizar tarifa ─────────────────────── */}
        <Text style={styles.sectionTitle}>Actualizar tarifa</Text>
        <Text style={styles.sectionSubtitle}>
          Usaremos esta información para estimar el costo de tu consumo.
        </Text>

        {/* Campo 1: Operador o comercializador */}
        <View style={styles.fieldHeaderRow}>
          <Text style={styles.fieldLabel}>Operador o comercializador</Text>
          <Text style={styles.fieldOptional}>Opcional</Text>
        </View>
        <TouchableOpacity
          style={styles.selectInput}
          activeOpacity={0.7}
          onPress={() => setShowOperadorModal(true)}
        >
          <Text style={styles.selectInputText}>{operador}</Text>
          <Ionicons name="chevron-forward" size={18} color="#4E7063" />
        </TouchableOpacity>

        {/* Campo 2: Valor aplicado de energía* */}
        <Text style={[styles.fieldLabel, { marginTop: 14 }]}>
          Valor aplicado de energía*
        </Text>
        <View style={styles.textInputBox}>
          <Text style={styles.inputPrefix}>$</Text>
          <TextInput
            style={styles.textInput}
            value={valorKwh}
            onChangeText={setValorKwh}
            keyboardType="numeric"
            placeholder="892"
            placeholderTextColor="#64748B"
          />
          <Text style={styles.inputSuffix}>/ kWh</Text>
        </View>
        <Text style={styles.fieldHint}>
          Consulta el valor aplicado por kWh en tu factura.
        </Text>

        {/* Campo 3: Vigente desde* */}
        <Text style={[styles.fieldLabel, { marginTop: 14 }]}>
          Vigente desde*
        </Text>
        <TouchableOpacity
          style={styles.selectInput}
          activeOpacity={0.7}
          onPress={() => setShowVigenciaModal(true)}
        >
          <View style={styles.selectLeftGroup}>
            <Ionicons
              name="calendar-outline"
              size={19}
              color="#8EA299"
              style={{ marginRight: 10 }}
            />
            <Text style={styles.selectInputText}>{vigenteDesde}</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#4E7063" />
        </TouchableOpacity>

        {/* Campo 4: Cargo fijo mensual / Aviso */}
        <Text style={[styles.fieldLabel, { marginTop: 16 }]}>
          Cargo fijo mensual
        </Text>
        <View style={styles.noticeCard}>
          <Ionicons
            name="help-circle-outline"
            size={18}
            color="#8EA299"
            style={{ marginRight: 10, marginTop: 2 }}
          />
          <Text style={styles.noticeText}>
            Zentheris calcula una estimación según tu consumo y tarifa. El
            valor final de tu factura puede incluir subsidios, contribuciones u
            otros cobros.
          </Text>
        </View>

        {/* ─── Botón: Guardar tarifa ──────────────────────────── */}
        <TouchableOpacity
          style={styles.btnGuardar}
          activeOpacity={0.85}
          onPress={handleGuardar}
        >
          <Text style={styles.btnGuardarText}>Guardar tarifa</Text>
        </TouchableOpacity>

        <View style={{ height: 28 }} />
      </ScrollView>

      {/* ─── Modal Selección de Operador ─────────────────────── */}
      <Modal
        visible={showOperadorModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowOperadorModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Selecciona un operador</Text>
            {OPERADORES_COLOMBIA.map((item) => (
              <TouchableOpacity
                key={item}
                style={[
                  styles.modalItem,
                  operador === item && styles.modalItemActive,
                ]}
                onPress={() => {
                  setOperador(item);
                  setShowOperadorModal(false);
                }}
              >
                <Text
                  style={[
                    styles.modalItemText,
                    operador === item && styles.modalItemTextActive,
                  ]}
                >
                  {item}
                </Text>
                {operador === item && (
                  <Ionicons name="checkmark" size={18} color="#34D399" />
                )}
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </Modal>

      {/* ─── Modal Selección de Vigencia ─────────────────────── */}
      <Modal
        visible={showVigenciaModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowVigenciaModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Vigencia de la tarifa</Text>
            {MESES_VIGENCIA.map((item) => (
              <TouchableOpacity
                key={item}
                style={[
                  styles.modalItem,
                  vigenteDesde === item && styles.modalItemActive,
                ]}
                onPress={() => {
                  setVigenteDesde(item);
                  setShowVigenciaModal(false);
                }}
              >
                <Text
                  style={[
                    styles.modalItemText,
                    vigenteDesde === item && styles.modalItemTextActive,
                  ]}
                >
                  {item}
                </Text>
                {vigenteDesde === item && (
                  <Ionicons name="checkmark" size={18} color="#34D399" />
                )}
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </Modal>
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

  // ─── Tarjeta Activa ───────────────────────────────────────────
  activeCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#34D399',
    padding: 18,
    marginBottom: 20,
  },
  activeTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  activeTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 3,
  },
  activeSubtitle: {
    color: '#8EA299',
    fontSize: 13,
  },
  badgeActiva: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#12382B',
    borderRadius: 14,
    paddingHorizontal: 10,
    paddingVertical: 4,
    gap: 6,
  },
  badgeDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: '#34D399',
  },
  badgeActivaText: {
    color: '#34D399',
    fontSize: 12,
    fontWeight: '600',
  },
  metricRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: 10,
  },
  metricCurrency: {
    color: '#5DD39E',
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  metricSlash: {
    color: '#5DD39E',
    fontSize: 26,
    fontWeight: '600',
  },
  metricUnit: {
    color: '#5DD39E',
    fontSize: 26,
    fontWeight: '600',
  },
  activeInfoText: {
    color: '#8EA299',
    fontSize: 12.5,
    lineHeight: 18,
  },
  btnEditarTarifa: {
    backgroundColor: '#0E241E',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1C4235',
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 14,
  },
  btnEditarTarifaText: {
    color: '#5DD39E',
    fontSize: 14,
    fontWeight: '700',
  },

  // ─── Sección Actualizar ────────────────────────────────────────
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
  fieldHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  fieldLabel: {
    color: '#E2E8F0',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  fieldOptional: {
    color: '#8EA299',
    fontSize: 12,
  },
  selectInput: {
    backgroundColor: '#091913',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1C3F33',
    height: 50,
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  selectLeftGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  selectInputText: {
    color: '#FFFFFF',
    fontSize: 14.5,
  },
  textInputBox: {
    backgroundColor: '#091913',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1C3F33',
    height: 50,
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
  },
  inputPrefix: {
    color: '#8EA299',
    fontSize: 15,
    marginRight: 6,
  },
  textInput: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  inputSuffix: {
    color: '#8EA299',
    fontSize: 13.5,
    marginLeft: 6,
  },
  fieldHint: {
    color: '#8EA299',
    fontSize: 12,
    marginTop: 6,
    marginBottom: 2,
  },

  // ─── Notice Box ────────────────────────────────────────────────
  noticeCard: {
    backgroundColor: '#0E241E',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1F4A3C',
    padding: 14,
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 22,
  },
  noticeText: {
    color: '#8EA299',
    fontSize: 12,
    lineHeight: 17,
    flex: 1,
  },

  // ─── Botón Guardar ─────────────────────────────────────────────
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

  // ─── Modal ─────────────────────────────────────────────────────
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#0E241E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: '#1F4D3E',
    maxHeight: '70%',
  },
  modalTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
    marginBottom: 16,
  },
  modalItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#16362B',
  },
  modalItemActive: {
    backgroundColor: '#133027',
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  modalItemText: {
    color: '#8EA299',
    fontSize: 14.5,
  },
  modalItemTextActive: {
    color: '#34D399',
    fontWeight: '700',
  },
});

