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

export interface Consejo {
  id: string;
  titulo: string;
  descripcion: string;
  prioridad: 'alta' | 'media' | 'baja';
  completado: boolean;
}

const CONSEJOS_INICIALES: Consejo[] = [
  {
    id: '1',
    titulo: 'Apaga el aire acondicionado al salir',
    descripcion: 'Antes de salir, comprueba que el equipo quede apagado.',
    prioridad: 'alta',
    completado: false,
  },
  {
    id: '2',
    titulo: 'Programa el termostato para horario nocturno',
    descripcion: 'Configura un horario acorde con tu rutina de descanso.',
    prioridad: 'media',
    completado: false,
  },
  {
    id: '3',
    titulo: 'Revisa el consumo del refrigerador',
    descripcion: 'Consulta su consumo y revisa los ajustes del equipo.',
    prioridad: 'media',
    completado: true,
  },
  {
    id: '4',
    titulo: 'Cambia bombillas a LED en la cocina',
    descripcion: 'Revisa las bombillas de la cocina y sustitúyelas por LED.',
    prioridad: 'media',
    completado: false,
  },
];

export function ConsejosScreen() {
  const [consejos, setConsejos] = useState<Consejo[]>(CONSEJOS_INICIALES);

  const toggleCompletado = (id: string) => {
    setConsejos((prev) =>
      prev.map((c) => (c.id === id ? { ...c, completado: !c.completado } : c))
    );
  };

  const pendientesCount = consejos.filter((c) => !c.completado).length;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#07130F" />

      {/* ─── Header ─────────────────────────────────────────── */}
      <View style={styles.header}>
        <View style={styles.headerSpacer} />
        <Text style={styles.headerTitle}>Consejos</Text>
        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.sparkleBtn}
          onPress={() => console.log('Sugerencias IA')}
        >
          <MaterialCommunityIcons
            name="creation-outline"
            size={24}
            color="#3B6758"
          />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Tarjeta Superior de Estado (¡Todo bajo control!) ── */}
        <View style={styles.bannerCard}>
          <View style={styles.bannerIconWrapper}>
            <MaterialCommunityIcons
              name="thumb-up-outline"
              size={28}
              color="#34D399"
            />
          </View>
          <Text style={styles.bannerTitle}>¡Todo bajo control!</Text>
          <Text style={styles.bannerSubtitle}>
            {pendientesCount === 0
              ? 'No tienes consejos pendientes por ahora. Revisa más tarde para nuevas recomendaciones de ahorro.'
              : 'No tienes consejos pendientes por ahora. Revisa más tarde para nuevas recomendaciones de ahorro.'}
          </Text>
        </View>

        {/* ─── Lista de Consejos ──────────────────────────────── */}
        <View style={styles.listContainer}>
          {consejos.map((item) => {
            const isCompleted = item.completado;

            return (
              <TouchableOpacity
                key={item.id}
                style={[
                  styles.consejoCard,
                  isCompleted && styles.consejoCardCompleted,
                ]}
                activeOpacity={0.85}
                onPress={() => toggleCompletado(item.id)}
              >
                {/* Checkbox táctil */}
                <TouchableOpacity
                  style={[
                    styles.checkbox,
                    isCompleted && styles.checkboxChecked,
                  ]}
                  activeOpacity={0.7}
                  onPress={() => toggleCompletado(item.id)}
                >
                  {isCompleted && (
                    <Ionicons name="checkmark-sharp" size={17} color="#34D399" />
                  )}
                </TouchableOpacity>

                {/* Contenido del Consejo */}
                <View style={styles.cardContent}>
                  <Text
                    style={[
                      styles.cardTitle,
                      isCompleted && styles.cardTitleCompleted,
                    ]}
                  >
                    {item.titulo}
                  </Text>
                  <Text
                    style={[
                      styles.cardDesc,
                      isCompleted && styles.cardDescCompleted,
                    ]}
                  >
                    {item.descripcion}
                  </Text>

                  {/* Badge de Prioridad / Completado */}
                  <View style={styles.badgeRow}>
                    {isCompleted ? (
                      <View style={[styles.badge, styles.badgeCompleted]}>
                        <Text style={[styles.badgeText, styles.badgeTextCompleted]}>
                          Completado
                        </Text>
                      </View>
                    ) : item.prioridad === 'alta' ? (
                      <View style={[styles.badge, styles.badgeAlta]}>
                        <Text style={[styles.badgeText, styles.badgeTextAlta]}>
                          Alta prioridad
                        </Text>
                      </View>
                    ) : item.prioridad === 'media' ? (
                      <View style={[styles.badge, styles.badgeMedia]}>
                        <Text style={[styles.badgeText, styles.badgeTextMedia]}>
                          Media prioridad
                        </Text>
                      </View>
                    ) : (
                      <View style={[styles.badge, styles.badgeBaja]}>
                        <Text style={[styles.badgeText, styles.badgeTextBaja]}>
                          Baja prioridad
                        </Text>
                      </View>
                    )}
                  </View>
                </View>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Espaciado inferior para no solapar la barra de navegación */}
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
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 10,
  },
  headerSpacer: {
    width: 28,
  },
  headerTitle: {
    color: '#E6FAF0',
    fontSize: 22,
    fontWeight: '700',
    letterSpacing: -0.2,
  },
  sparkleBtn: {
    width: 28,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 8,
  },

  // ─── Tarjeta Superior ──────────────────────────────────────────
  bannerCard: {
    backgroundColor: '#0E241E',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#193C31',
    alignItems: 'center',
    paddingVertical: 28,
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  bannerIconWrapper: {
    width: 60,
    height: 60,
    borderRadius: 18,
    backgroundColor: '#153A2E',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 18,
  },
  bannerTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 10,
    letterSpacing: -0.2,
  },
  bannerSubtitle: {
    color: '#8EA299',
    fontSize: 13.5,
    lineHeight: 20,
    textAlign: 'center',
    maxWidth: 290,
  },

  // ─── Lista de Tarjetas ─────────────────────────────────────────
  listContainer: {
    gap: 12,
  },
  consejoCard: {
    backgroundColor: '#0E241E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#17392E',
    padding: 16,
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  consejoCardCompleted: {
    opacity: 0.85,
  },
  checkbox: {
    width: 26,
    height: 26,
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: '#2D4B40',
    backgroundColor: '#0A1A14',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
    marginTop: 2,
  },
  checkboxChecked: {
    backgroundColor: '#153D30',
    borderColor: '#34D399',
  },
  cardContent: {
    flex: 1,
  },
  cardTitle: {
    color: '#FFFFFF',
    fontSize: 15.5,
    fontWeight: '600',
    lineHeight: 21,
    marginBottom: 5,
  },
  cardTitleCompleted: {
    color: '#7B8E85',
  },
  cardDesc: {
    color: '#8EA299',
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 12,
  },
  cardDescCompleted: {
    color: '#556C62',
  },

  // ─── Badges de Prioridad ───────────────────────────────────────
  badgeRow: {
    flexDirection: 'row',
  },
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
  },
  badgeText: {
    fontSize: 11.5,
    fontWeight: '600',
    letterSpacing: 0.1,
  },

  // Alta prioridad
  badgeAlta: {
    backgroundColor: '#261616',
    borderColor: '#5C2828',
  },
  badgeTextAlta: {
    color: '#F87171',
  },

  // Media prioridad
  badgeMedia: {
    backgroundColor: '#241F10',
    borderColor: '#54441B',
  },
  badgeTextMedia: {
    color: '#FBBF24',
  },

  // Baja prioridad
  badgeBaja: {
    backgroundColor: '#12242B',
    borderColor: '#1C4A57',
  },
  badgeTextBaja: {
    color: '#38BDF8',
  },

  // Completado
  badgeCompleted: {
    backgroundColor: '#112C23',
    borderColor: '#1D5946',
  },
  badgeTextCompleted: {
    color: '#34D399',
  },
});

