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

export function EditarPerfilScreen() {
  const router = useRouter();

  // Estados de datos del usuario
  const [nombre, setNombre] = useState('Zentheris Usuario');
  const [correo, setCorreo] = useState('usuario@zentheris.com');
  const [telefono, setTelefono] = useState('+57 300 123 4567');

  // Estados temporales para el modal de edición
  const [isEditing, setIsEditing] = useState(false);
  const [tempNombre, setTempNombre] = useState(nombre);
  const [tempCorreo, setTempCorreo] = useState(correo);
  const [tempTelefono, setTempTelefono] = useState(telefono);

  const openEditModal = () => {
    setTempNombre(nombre);
    setTempCorreo(correo);
    setTempTelefono(telefono);
    setIsEditing(true);
  };

  const saveChanges = () => {
    setNombre(tempNombre);
    setCorreo(tempCorreo);
    setTelefono(tempTelefono);
    setIsEditing(false);
    Alert.alert('Éxito', 'Información de perfil actualizada correctamente.');
  };

  const handleCerrarSesion = () => {
    Alert.alert(
      'Cerrar sesión',
      '¿Estás seguro de que deseas salir de tu cuenta en este dispositivo?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Cerrar',
          style: 'destructive',
          onPress: () => {
            console.log('Sesión cerrada');
            router.push('/');
          },
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
        <Text style={styles.headerTitle}>Editar Perfil</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Avatar con botón de edición ───────────────────── */}
        <View style={styles.avatarSection}>
          <View style={styles.avatarWrapper}>
            <View style={styles.avatarCircle}>
              <Ionicons name="person" size={48} color="#265848" />
            </View>
            <TouchableOpacity
              style={styles.editBadge}
              activeOpacity={0.8}
              onPress={openEditModal}
            >
              <Ionicons name="pencil" size={15} color="#062218" />
            </TouchableOpacity>
          </View>
          <Text style={styles.avatarName}>{nombre}</Text>
          <Text style={styles.avatarEmail}>{correo}</Text>
        </View>

        {/* ─── Tarjeta: Información personal ─────────────────── */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Información personal</Text>
          <Text style={styles.cardSubtitle}>
            Datos principales asociados a tu cuenta
          </Text>

          <View style={styles.divider} />

          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Nombre completo</Text>
            <Text style={styles.fieldValue}>{nombre}</Text>
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Correo</Text>
            <Text style={styles.fieldValue}>{correo}</Text>
          </View>

          <View style={[styles.fieldGroup, { marginBottom: 0 }]}>
            <Text style={styles.fieldLabel}>Teléfono</Text>
            <Text style={styles.fieldValue}>{telefono}</Text>
          </View>
        </View>

        {/* ─── Tarjeta: Acciones ─────────────────────────────── */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Acciones</Text>
          <Text style={styles.cardSubtitle}>
            Gestiona tu perfil y consulta tu actividad
          </Text>

          <View style={[styles.divider, { marginBottom: 14 }]} />

          {/* Opción 1: Editar información */}
          <TouchableOpacity
            style={styles.actionRow}
            activeOpacity={0.7}
            onPress={openEditModal}
          >
            <View style={styles.iconBox}>
              <Ionicons name="create-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.actionTextContainer}>
              <Text style={styles.actionTitle}>Editar información</Text>
              <Text style={styles.actionSubtitle}>
                Actualiza tus datos personales
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>

          <View style={styles.divider} />

          {/* Opción 2: Historial de consumo */}
          <TouchableOpacity
            style={styles.actionRow}
            activeOpacity={0.7}
            onPress={() => router.push('/historial')}
          >
            <View style={styles.iconBox}>
              <Ionicons name="calendar-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.actionTextContainer}>
              <Text style={styles.actionTitle}>Historial de consumo</Text>
              <Text style={styles.actionSubtitle}>
                Consulta tu actividad energética
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>

          <View style={styles.divider} />

          {/* Opción 3: Cerrar sesión */}
          <View style={styles.actionRow}>
            <View style={styles.actionTextContainer}>
              <Text style={[styles.actionTitle, styles.actionTitleDanger]}>
                Cerrar sesión
              </Text>
              <Text style={styles.actionSubtitle}>
                Sal de tu cuenta en este dispositivo
              </Text>
            </View>
            <TouchableOpacity
              style={styles.btnCerrar}
              activeOpacity={0.8}
              onPress={handleCerrarSesion}
            >
              <Text style={styles.btnCerrarText}>Cerrar</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={{ height: 32 }} />
      </ScrollView>

      {/* ─── Modal para Editar Información ─────────────────── */}
      <Modal
        visible={isEditing}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setIsEditing(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Editar Información</Text>
            <Text style={styles.modalSubtitle}>
              Modifica los datos de tu cuenta
            </Text>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Nombre completo</Text>
              <TextInput
                style={styles.textInput}
                value={tempNombre}
                onChangeText={setTempNombre}
                placeholderTextColor="#64748B"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Correo electrónico</Text>
              <TextInput
                style={styles.textInput}
                value={tempCorreo}
                onChangeText={setTempCorreo}
                keyboardType="email-address"
                autoCapitalize="none"
                placeholderTextColor="#64748B"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Teléfono</Text>
              <TextInput
                style={styles.textInput}
                value={tempTelefono}
                onChangeText={setTempTelefono}
                keyboardType="phone-pad"
                placeholderTextColor="#64748B"
              />
            </View>

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.btnModalCancel}
                onPress={() => setIsEditing(false)}
              >
                <Text style={styles.btnModalCancelText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.btnModalSave}
                onPress={saveChanges}
              >
                <Text style={styles.btnModalSaveText}>Guardar</Text>
              </TouchableOpacity>
            </View>
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

  // ─── Avatar ────────────────────────────────────────────────────
  avatarSection: {
    alignItems: 'center',
    marginBottom: 22,
    marginTop: 6,
  },
  avatarWrapper: {
    position: 'relative',
    marginBottom: 12,
  },
  avatarCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: '#112B23',
    borderWidth: 1.5,
    borderColor: '#1D4537',
    alignItems: 'center',
    justifyContent: 'center',
  },
  editBadge: {
    position: 'absolute',
    bottom: 2,
    right: 2,
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#34D399',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#071510',
  },
  avatarName: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: -0.2,
    marginBottom: 4,
  },
  avatarEmail: {
    color: '#8EA299',
    fontSize: 13.5,
  },

  // ─── Cards ─────────────────────────────────────────────────────
  card: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 18,
    marginBottom: 16,
  },
  cardTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 3,
  },
  cardSubtitle: {
    color: '#8EA299',
    fontSize: 13,
  },
  divider: {
    height: 1,
    backgroundColor: '#16362B',
    marginVertical: 14,
  },

  // ─── Información Personal ──────────────────────────────────────
  fieldGroup: {
    marginBottom: 14,
  },
  fieldLabel: {
    color: '#8EA299',
    fontSize: 12.5,
    marginBottom: 4,
  },
  fieldValue: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },

  // ─── Acciones ──────────────────────────────────────────────────
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconBox: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: '#133027',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  actionTextContainer: {
    flex: 1,
    marginRight: 10,
  },
  actionTitle: {
    color: '#FFFFFF',
    fontSize: 14.5,
    fontWeight: '600',
    marginBottom: 3,
  },
  actionTitleDanger: {
    color: '#F87171',
  },
  actionSubtitle: {
    color: '#8EA299',
    fontSize: 12,
    lineHeight: 16,
  },
  btnCerrar: {
    backgroundColor: '#242020',
    borderWidth: 1,
    borderColor: '#452A2A',
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderRadius: 8,
  },
  btnCerrarText: {
    color: '#D1D5DB',
    fontSize: 13,
    fontWeight: '600',
  },

  // ─── Modal ─────────────────────────────────────────────────────
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  modalContent: {
    backgroundColor: '#0E241E',
    borderRadius: 20,
    padding: 22,
    borderWidth: 1,
    borderColor: '#1F4D3E',
  },
  modalTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 4,
  },
  modalSubtitle: {
    color: '#8EA299',
    fontSize: 13,
    marginBottom: 18,
  },
  inputGroup: {
    marginBottom: 14,
  },
  inputLabel: {
    color: '#8EA299',
    fontSize: 12,
    marginBottom: 6,
  },
  textInput: {
    backgroundColor: '#133027',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1D4537',
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: '#FFFFFF',
    fontSize: 14,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    marginTop: 10,
  },
  btnModalCancel: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#163328',
  },
  btnModalCancelText: {
    color: '#8EA299',
    fontSize: 13.5,
    fontWeight: '600',
  },
  btnModalSave: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#34D399',
  },
  btnModalSaveText: {
    color: '#062218',
    fontSize: 13.5,
    fontWeight: '700',
  },
});

