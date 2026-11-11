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
  Switch,
  Alert,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

export function ConfiguracionScreen() {
  const router = useRouter();

  // Estados para los switches de configuración
  const [notifAlertas, setNotifAlertas] = useState(true);
  const [notifConsejos, setNotifConsejos] = useState(true);
  const [metaConsumoActiva, setMetaConsumoActiva] = useState(true);

  const handleCerrarSesion = () => {
    Alert.alert(
      'Cerrar sesión',
      '¿Estás seguro de que deseas finalizar tu sesión en este dispositivo?',
      [
        { text: 'Cancelar', style: 'cancel' },
        { text: 'Cerrar sesión', style: 'destructive', onPress: () => console.log('Sesión cerrada') },
      ]
    );
  };

  const handleEliminarCuenta = () => {
    Alert.alert(
      'Eliminar cuenta',
      'Esta acción es definitiva y no se puede deshacer. ¿Deseas continuar?',
      [
        { text: 'Cancelar', style: 'cancel' },
        { text: 'Eliminar', style: 'destructive', onPress: () => console.log('Cuenta eliminada') },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#071510" />

      {/* ─── Header ─────────────────────────────────────────── */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Configuración</Text>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Perfil / Avatar ────────────────────────────────── */}
        <TouchableOpacity
          style={styles.avatarSection}
          activeOpacity={0.8}
          onPress={() => router.push('/editar-perfil')}
        >
          <View style={styles.avatarCircle}>
            <Ionicons name="person" size={38} color="#2A5C4D" />
          </View>
          <Text style={styles.avatarName}>Zentheris</Text>
        </TouchableOpacity>

        {/* ─── 1. CUENTA ──────────────────────────────────────── */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionHeader}>CUENTA</Text>

          <TouchableOpacity
            style={styles.rowItem}
            activeOpacity={0.7}
            onPress={() => router.push('/editar-perfil')}
          >
            <View style={styles.iconBox}>
              <Ionicons name="person-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Editar perfil</Text>
              <Text style={styles.rowSubtitle}>Actualiza tu información personal</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>

          <View style={styles.divider} />

          <TouchableOpacity
            style={styles.rowItem}
            activeOpacity={0.7}
            onPress={() => router.push('/cambiar-contrasena')}
          >
            <View style={styles.iconBox}>
              <Ionicons name="shield-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Cambiar contraseña</Text>
              <Text style={styles.rowSubtitle}>Contraseña y autenticación</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>

          <View style={styles.divider} />

          <TouchableOpacity
            style={styles.rowItem}
            activeOpacity={0.7}
            onPress={() => router.push('/gestionar-correo')}
          >
            <View style={styles.iconBox}>
              <Ionicons name="mail-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Correo electrónico</Text>
              <Text style={styles.rowSubtitle}>Gestiona tu correo de acceso</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>
        </View>

        {/* ─── 2. NOTIFICACIONES ──────────────────────────────── */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionHeader}>NOTIFICACIONES</Text>

          <View style={styles.rowItem}>
            <View style={styles.iconBox}>
              <Ionicons name="notifications-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Alertas</Text>
              <Text style={styles.rowSubtitle}>Consumo y sobreconsumo</Text>
            </View>
            <Switch
              value={notifAlertas}
              onValueChange={setNotifAlertas}
              trackColor={{ false: '#163328', true: '#5DD39E' }}
              thumbColor="#FFFFFF"
              ios_backgroundColor="#163328"
            />
          </View>

          <View style={styles.divider} />

          <View style={styles.rowItem}>
            <View style={styles.iconBox}>
              <Ionicons name="notifications-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Consejos</Text>
              <Text style={styles.rowSubtitle}>recibe recomendaciones personalizadas</Text>
            </View>
            <Switch
              value={notifConsejos}
              onValueChange={setNotifConsejos}
              trackColor={{ false: '#163328', true: '#5DD39E' }}
              thumbColor="#FFFFFF"
              ios_backgroundColor="#163328"
            />
          </View>
        </View>

        {/* ─── 3. ENERGÍA Y CONSUMO ───────────────────────────── */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionHeader}>ENERGÍA Y CONSUMO</Text>

          <View style={styles.rowItem}>
            <View style={styles.iconBox}>
              <Ionicons name="notifications-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Meta de consumo</Text>
              <Text style={styles.rowSubtitle}>Activa o desactiva si quieres una meta de consumo</Text>
            </View>
            <Switch
              value={metaConsumoActiva}
              onValueChange={setMetaConsumoActiva}
              trackColor={{ false: '#163328', true: '#5DD39E' }}
              thumbColor="#FFFFFF"
              ios_backgroundColor="#163328"
            />
          </View>

          <View style={styles.divider} />

          <TouchableOpacity
            style={styles.rowItem}
            activeOpacity={0.7}
            onPress={() => router.push('/establecer-meta')}
          >
            <View style={styles.iconBox}>
              <Ionicons name="locate-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Establecer una meta de consumo</Text>
              <Text style={styles.rowSubtitle}>Define tu objetivo mensual</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>

          <View style={styles.divider} />

          <TouchableOpacity style={styles.rowItem} activeOpacity={0.7}>
            <View style={styles.iconBox}>
              <Ionicons name="leaf-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Configurar tarifa eléctrica</Text>
              <Text style={styles.rowSubtitle}>Personaliza el cálculo de consumo</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>

          <View style={styles.divider} />

          <TouchableOpacity style={styles.rowItem} activeOpacity={0.7}>
            <View style={styles.iconBox}>
              <Ionicons name="hardware-chip-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Conectar medidores</Text>
              <Text style={styles.rowSubtitle}>Vincula tus dispositivos de medición</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>
        </View>

        {/* ─── 4. FAMILIA Y ACCESO ────────────────────────────── */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionHeader}>FAMILIA Y ACCESO</Text>

          <TouchableOpacity style={styles.rowItem} activeOpacity={0.7}>
            <View style={styles.iconBox}>
              <Ionicons name="people-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Administrar miembros del hogar</Text>
              <Text style={styles.rowSubtitle}>Gestiona el acceso compartido</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>
        </View>

        {/* ─── 5. HOGAR Y TRANSICIÓN ENERGÉTICA ───────────────── */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionHeader}>HOGAR Y TRANSICIÓN ENERGÉTICA</Text>

          <TouchableOpacity style={styles.rowItem} activeOpacity={0.7}>
            <View style={styles.iconBox}>
              <Ionicons name="leaf-outline" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>
                Información del hogar y datos de transición energética
              </Text>
              <Text style={styles.rowSubtitle}>
                Datos del hogar e integrantes para planificar tu transición a renovables
              </Text>
            </View>
            <View style={styles.badgeProximamente}>
              <Text style={styles.badgeProximamenteText}>Próximamente</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>

          <View style={styles.divider} />

          <TouchableOpacity style={styles.rowItem} activeOpacity={0.7}>
            <View style={styles.iconBox}>
              <MaterialCommunityIcons name="foot-print" size={20} color="#34D399" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Mi huella de carbono</Text>
              <Text style={styles.rowSubtitle}>
                Conoce el impacto ambiental de tu consumo
              </Text>
            </View>
            <View style={styles.badgeProximamente}>
              <Text style={styles.badgeProximamenteText}>Próximamente</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#4E7063" />
          </TouchableOpacity>
        </View>

        {/* ─── 6. OTROS ───────────────────────────────────────── */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionHeader}>OTROS</Text>

          <View style={styles.rowItem}>
            <View style={[styles.iconBox, styles.iconBoxDanger]}>
              <Ionicons name="close-circle-outline" size={20} color="#F87171" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Cerrar sesión</Text>
              <Text style={styles.rowSubtitle}>Finaliza la sesión en este dispositivo</Text>
            </View>
            <TouchableOpacity
              style={styles.btnActionSecondary}
              activeOpacity={0.8}
              onPress={handleCerrarSesion}
            >
              <Text style={styles.btnActionSecondaryText}>Cerrar</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* ─── 7. ZONA DE RIESGO ──────────────────────────────── */}
        <View style={styles.sectionCard}>
          <Text style={[styles.sectionHeader, styles.sectionHeaderDanger]}>
            ZONA DE RIESGO
          </Text>

          <View style={styles.rowItem}>
            <View style={[styles.iconBox, styles.iconBoxDanger]}>
              <Ionicons name="trash-outline" size={20} color="#F87171" />
            </View>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>Eliminar cuenta</Text>
              <Text style={styles.rowSubtitle}>Esta acción no se puede deshacer</Text>
            </View>
            <TouchableOpacity
              style={styles.btnActionDanger}
              activeOpacity={0.8}
              onPress={handleEliminarCuenta}
            >
              <Text style={styles.btnActionDangerText}>Eliminar</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Espacio final para no quedar tapado por el tab bar */}
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
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
  },
  headerTitle: {
    color: '#E6FAF0',
    fontSize: 22,
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
    marginBottom: 20,
    marginTop: 4,
  },
  avatarCircle: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: '#122D24',
    borderWidth: 1.5,
    borderColor: '#1D4537',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  avatarName: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: 0.1,
  },

  // ─── Tarjetas de Sección ───────────────────────────────────────
  sectionCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    color: '#34D399',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginBottom: 14,
  },
  sectionHeaderDanger: {
    color: '#EF4444',
  },

  // ─── Filas ────────────────────────────────────────────────────
  rowItem: {
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
  iconBoxDanger: {
    backgroundColor: '#261616',
  },
  rowTextContainer: {
    flex: 1,
    marginRight: 10,
  },
  rowTitle: {
    color: '#FFFFFF',
    fontSize: 14.5,
    fontWeight: '600',
    marginBottom: 3,
  },
  rowSubtitle: {
    color: '#8EA299',
    fontSize: 12,
    lineHeight: 16,
  },
  divider: {
    height: 1,
    backgroundColor: '#16362B',
    marginVertical: 12,
  },

  // ─── Badge Próximamente ────────────────────────────────────────
  badgeProximamente: {
    backgroundColor: '#1A332B',
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginRight: 8,
  },
  badgeProximamenteText: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '500',
  },

  // ─── Botones de Acción ─────────────────────────────────────────
  btnActionSecondary: {
    backgroundColor: '#242323',
    borderWidth: 1,
    borderColor: '#3D3535',
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderRadius: 8,
  },
  btnActionSecondaryText: {
    color: '#D1D5DB',
    fontSize: 13,
    fontWeight: '600',
  },
  btnActionDanger: {
    backgroundColor: '#281313',
    borderWidth: 1,
    borderColor: '#6B2121',
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderRadius: 8,
  },
  btnActionDangerText: {
    color: '#EF4444',
    fontSize: 13,
    fontWeight: '600',
  },
});
