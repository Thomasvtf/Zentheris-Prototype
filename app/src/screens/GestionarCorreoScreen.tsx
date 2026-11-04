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

export function GestionarCorreoScreen() {
  const router = useRouter();

  // Estados de inputs
  const [correoActual, setCorreoActual] = useState('usuario@zentheris.com');
  const [nuevoCorreo, setNuevoCorreo] = useState('');
  const [confirmarCorreo, setConfirmarCorreo] = useState('');

  // Validación
  const isValidEmail = (email: string) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const isValid =
    nuevoCorreo.trim().length > 0 &&
    confirmarCorreo.trim().length > 0 &&
    nuevoCorreo.trim() === confirmarCorreo.trim() &&
    isValidEmail(nuevoCorreo.trim());

  const handleContinuar = () => {
    if (!nuevoCorreo.trim()) {
      Alert.alert('Error', 'Por favor ingresa tu nuevo correo electrónico.');
      return;
    }
    if (!isValidEmail(nuevoCorreo.trim())) {
      Alert.alert('Formato inválido', 'Ingresa una dirección de correo válida.');
      return;
    }
    if (nuevoCorreo.trim() !== confirmarCorreo.trim()) {
      Alert.alert('Error', 'Los correos electrónicos no coinciden.');
      return;
    }
    if (nuevoCorreo.trim() === correoActual.trim()) {
      Alert.alert(
        'Mismo correo',
        'El nuevo correo debe ser diferente al actual.'
      );
      return;
    }

    Alert.alert(
      'Código de verificación enviado',
      `Hemos enviado un código de verificación a ${nuevoCorreo.trim()}. Por favor revisa tu bandeja de entrada para confirmar el cambio.`,
      [
        {
          text: 'Entendido',
          onPress: () => router.back(),
        },
      ]
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
        <Text style={styles.headerTitle}>Gestionar Correo</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Tarjeta: Correo de acceso ──────────────────────── */}
        <View style={styles.bannerCard}>
          <View style={styles.bannerIconBox}>
            <Ionicons name="person-outline" size={22} color="#34D399" />
          </View>
          <View style={styles.bannerTextContainer}>
            <Text style={styles.bannerTitle}>Correo de acceso</Text>
            <Text style={styles.bannerSubtitle}>
              Este correo se utiliza para iniciar sesión y recibir avisos de tu cuenta.
            </Text>
          </View>
        </View>

        {/* ─── Tarjeta: Formulario ────────────────────────────── */}
        <View style={styles.formCard}>
          {/* Campo 1: Correo actual */}
          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Correo actual</Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.textInput}
                value={correoActual}
                onChangeText={setCorreoActual}
                placeholder="nuevo@correo.com"
                placeholderTextColor="#64748B"
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>
          </View>

          {/* Campo 2: Nuevo correo */}
          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Nuevo correo</Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.textInput}
                value={nuevoCorreo}
                onChangeText={setNuevoCorreo}
                placeholder="nuevo@correo.com"
                placeholderTextColor="#64748B"
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>
          </View>

          {/* Campo 3: Confirmar correo */}
          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Confirmar correo</Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.textInput}
                value={confirmarCorreo}
                onChangeText={setConfirmarCorreo}
                placeholder="Repite el nuevo correo"
                placeholderTextColor="#64748B"
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>
          </View>

          {/* Caja Informativa: Verificación de correo */}
          <View style={styles.infoBox}>
            <View style={styles.stepBadge}>
              <Text style={styles.stepBadgeText}>Paso siguiente</Text>
            </View>
            <View style={styles.infoTextContainer}>
              <Text style={styles.infoTitle}>Verificación de correo</Text>
              <Text style={styles.infoSubtitle}>
                Enviaremos un código al nuevo correo antes de guardar el cambio.
              </Text>
            </View>
          </View>

          <View style={styles.divider} />

          {/* Botón Continuar */}
          <TouchableOpacity
            style={[
              styles.btnContinuar,
              isValid && styles.btnContinuarActive,
            ]}
            activeOpacity={0.85}
            onPress={handleContinuar}
          >
            <Text
              style={[
                styles.btnContinuarText,
                isValid && styles.btnContinuarTextActive,
              ]}
            >
              Continuar
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
    backgroundColor: '#091913',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1C3F33',
    paddingHorizontal: 14,
    height: 50,
    justifyContent: 'center',
  },
  textInput: {
    color: '#FFFFFF',
    fontSize: 14.5,
  },

  // ─── Caja Informativa ──────────────────────────────────────────
  infoBox: {
    backgroundColor: '#091A14',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#16362B',
    padding: 14,
    marginTop: 6,
    marginBottom: 6,
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  stepBadge: {
    backgroundColor: '#D1E7DD',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 5,
    marginRight: 12,
    marginTop: 2,
  },
  stepBadgeText: {
    color: '#0D2B22',
    fontSize: 11,
    fontWeight: '700',
  },
  infoTextContainer: {
    flex: 1,
  },
  infoTitle: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 3,
  },
  infoSubtitle: {
    color: '#8EA299',
    fontSize: 12,
    lineHeight: 17,
  },

  // ─── Divider y Botón Continuar ────────────────────────────────
  divider: {
    height: 1,
    backgroundColor: '#16362B',
    marginVertical: 18,
  },
  btnContinuar: {
    backgroundColor: '#102821',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1B3F34',
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnContinuarActive: {
    backgroundColor: '#34D399',
    borderColor: '#34D399',
  },
  btnContinuarText: {
    color: '#4B6B5F',
    fontSize: 14.5,
    fontWeight: '600',
  },
  btnContinuarTextActive: {
    color: '#062218',
    fontWeight: '700',
  },
});

