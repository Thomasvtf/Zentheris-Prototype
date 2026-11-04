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
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

export function CambiarContrasenaScreen() {
  const router = useRouter();

  // Estados de inputs
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [confirmar, setConfirmar] = useState('');

  // Visibilidad de contraseñas
  const [showActual, setShowActual] = useState(false);
  const [showNueva, setShowNueva] = useState(false);
  const [showConfirmar, setShowConfirmar] = useState(false);

  // Validación de requisitos en tiempo real
  const hasMinLen = nueva.length >= 8;
  const hasUpperCase = /[A-Z]/.test(nueva);
  const hasNumber = /[0-9]/.test(nueva);
  const isDifferent = nueva.length > 0 && actual.length > 0 && nueva !== actual;

  const isValid =
    actual.length > 0 &&
    hasMinLen &&
    hasUpperCase &&
    hasNumber &&
    isDifferent &&
    nueva === confirmar;

  const handleGuardar = () => {
    if (!actual) {
      Alert.alert('Error', 'Por favor ingresa tu contraseña actual.');
      return;
    }
    if (!hasMinLen || !hasUpperCase || !hasNumber) {
      Alert.alert(
        'Contraseña no segura',
        'La nueva contraseña debe cumplir con todos los requisitos de seguridad.'
      );
      return;
    }
    if (nueva !== confirmar) {
      Alert.alert('Error', 'Las contraseñas no coinciden.');
      return;
    }

    Alert.alert(
      'Contraseña actualizada',
      'Tu contraseña ha sido cambiada exitosamente.',
      [{ text: 'Aceptar', onPress: () => router.back() }]
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#071510" />

      {/* ─── Header ─────────────────────────────────────────── */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.backButton}
          activeOpacity={0.7}
          onPress={() => router.back()}
        >
          <Ionicons name="chevron-back" size={24} color="#E6FAF0" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Cambiar contraseña</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Tarjeta: Protege tu cuenta ─────────────────────── */}
        <View style={styles.bannerCard}>
          <View style={styles.bannerIconBox}>
            <Ionicons name="shield-outline" size={24} color="#34D399" />
          </View>
          <View style={styles.bannerTextContainer}>
            <Text style={styles.bannerTitle}>Protege tu cuenta</Text>
            <Text style={styles.bannerSubtitle}>
              Verifica tu contraseña actual antes de crear una nueva.
            </Text>
          </View>
        </View>

        {/* ─── Tarjeta: Formulario de contraseñas ─────────────── */}
        <View style={styles.formCard}>
          {/* Campo 1: Contraseña actual */}
          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Contraseña actual</Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.textInput}
                value={actual}
                onChangeText={setActual}
                placeholder="**********"
                placeholderTextColor="#64748B"
                secureTextEntry={!showActual}
                autoCapitalize="none"
              />
              <TouchableOpacity
                style={styles.eyeBtn}
                onPress={() => setShowActual(!showActual)}
                activeOpacity={0.7}
              >
                <Ionicons
                  name={showActual ? 'eye-outline' : 'eye-off-outline'}
                  size={20}
                  color="#8EA299"
                />
              </TouchableOpacity>
            </View>
          </View>

          {/* Campo 2: Nueva contraseña */}
          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Nueva contraseña</Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.textInput}
                value={nueva}
                onChangeText={setNueva}
                placeholder="**********"
                placeholderTextColor="#64748B"
                secureTextEntry={!showNueva}
                autoCapitalize="none"
              />
              <TouchableOpacity
                style={styles.eyeBtn}
                onPress={() => setShowNueva(!showNueva)}
                activeOpacity={0.7}
              >
                <Ionicons
                  name={showNueva ? 'eye-outline' : 'eye-off-outline'}
                  size={20}
                  color="#8EA299"
                />
              </TouchableOpacity>
            </View>
          </View>

          {/* Campo 3: Confirmar contraseña */}
          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Confirmar contraseña</Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.textInput}
                value={confirmar}
                onChangeText={setConfirmar}
                placeholder="**********"
                placeholderTextColor="#64748B"
                secureTextEntry={!showConfirmar}
                autoCapitalize="none"
              />
              <TouchableOpacity
                style={styles.eyeBtn}
                onPress={() => setShowConfirmar(!showConfirmar)}
                activeOpacity={0.7}
              >
                <Ionicons
                  name={showConfirmar ? 'eye-outline' : 'eye-off-outline'}
                  size={20}
                  color="#8EA299"
                />
              </TouchableOpacity>
            </View>
          </View>

          {/* Requisitos de la contraseña */}
          <View style={styles.requirementsBox}>
            <Text style={styles.requirementsTitle}>
              Tu contraseña debe incluir:
            </Text>
            <View style={styles.chipsRow}>
              <View
                style={[
                  styles.reqChip,
                  hasMinLen && styles.reqChipSatisfied,
                ]}
              >
                <Text
                  style={[
                    styles.reqChipText,
                    hasMinLen && styles.reqChipTextSatisfied,
                  ]}
                >
                  8 caracteres
                </Text>
              </View>

              <View
                style={[
                  styles.reqChip,
                  hasUpperCase && styles.reqChipSatisfied,
                ]}
              >
                <Text
                  style={[
                    styles.reqChipText,
                    hasUpperCase && styles.reqChipTextSatisfied,
                  ]}
                >
                  Una mayúscula
                </Text>
              </View>

              <View
                style={[
                  styles.reqChip,
                  hasNumber && styles.reqChipSatisfied,
                ]}
              >
                <Text
                  style={[
                    styles.reqChipText,
                    hasNumber && styles.reqChipTextSatisfied,
                  ]}
                >
                  Un número
                </Text>
              </View>

              <View
                style={[
                  styles.reqChip,
                  isDifferent && styles.reqChipSatisfied,
                ]}
              >
                <Text
                  style={[
                    styles.reqChipText,
                    isDifferent && styles.reqChipTextSatisfied,
                  ]}
                >
                  Ser diferente
                </Text>
              </View>
            </View>
          </View>

          <View style={styles.divider} />

          {/* Botón Guardar nueva contraseña */}
          <TouchableOpacity
            style={[
              styles.btnGuardar,
              isValid && styles.btnGuardarActive,
            ]}
            activeOpacity={0.85}
            onPress={handleGuardar}
          >
            <Text
              style={[
                styles.btnGuardarText,
                isValid && styles.btnGuardarTextActive,
              ]}
            >
              Guardar nueva contraseña
            </Text>
          </TouchableOpacity>
        </View>

        <View style={{ height: 32 }} />
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
  backButton: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerSpacer: {
    width: 36,
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
    paddingTop: 8,
  },

  // ─── Banner Superior ───────────────────────────────────────────
  bannerCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  bannerIconBox: {
    width: 46,
    height: 46,
    borderRadius: 14,
    backgroundColor: '#133027',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  bannerTextContainer: {
    flex: 1,
  },
  bannerTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 3,
  },
  bannerSubtitle: {
    color: '#8EA299',
    fontSize: 12.5,
    lineHeight: 17,
  },

  // ─── Tarjeta Formulario ────────────────────────────────────────
  formCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 18,
  },
  fieldGroup: {
    marginBottom: 16,
  },
  fieldLabel: {
    color: '#E2E8F0',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#091913',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1C3F33',
    paddingHorizontal: 14,
    height: 50,
  },
  textInput: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 15,
    letterSpacing: 1.5,
  },
  eyeBtn: {
    padding: 6,
  },

  // ─── Requisitos Box ───────────────────────────────────────────
  requirementsBox: {
    backgroundColor: '#091A14',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#16362B',
    padding: 14,
    marginTop: 4,
    marginBottom: 6,
  },
  requirementsTitle: {
    color: '#8EA299',
    fontSize: 12.5,
    marginBottom: 10,
    fontWeight: '500',
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  reqChip: {
    backgroundColor: '#0E241E',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#1E3E33',
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  reqChipSatisfied: {
    backgroundColor: '#102E24',
    borderColor: '#26654F',
  },
  reqChipText: {
    color: '#8EA299',
    fontSize: 11.5,
    fontWeight: '500',
  },
  reqChipTextSatisfied: {
    color: '#34D399',
    fontWeight: '600',
  },

  // ─── Divider y Botón Guardar ──────────────────────────────────
  divider: {
    height: 1,
    backgroundColor: '#16362B',
    marginVertical: 18,
  },
  btnGuardar: {
    backgroundColor: '#102821',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1B3F34',
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnGuardarActive: {
    backgroundColor: '#34D399',
    borderColor: '#34D399',
  },
  btnGuardarText: {
    color: '#4B6B5F',
    fontSize: 14.5,
    fontWeight: '600',
  },
  btnGuardarTextActive: {
    color: '#062218',
    fontWeight: '700',
  },
});

