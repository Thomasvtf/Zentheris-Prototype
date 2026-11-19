import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
  StatusBar,
  Image,
  Animated,
  Easing,
  Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path, Rect, Circle, Line } from 'react-native-svg';
import type { Schemas } from '../api/client';
import { createHouseholdOnboarding } from '../api/onboarding';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export type TipoVivienda = 'apartamento' | 'apartaestudio' | 'casa' | 'casa_campestre' | 'duplex';
export type TipoZona =
  | 'cocina'
  | 'sala'
  | 'dormitorio'
  | 'bano'
  | 'oficina'
  | 'lavanderia'
  | 'terraza'
  | 'garaje'
  | 'cuarto_servicio';

interface HousingOption {
  id: TipoVivienda;
  label: string;
}

const HOUSING_OPTIONS: HousingOption[] = [
  { id: 'apartamento', label: 'Apartamento' },
  { id: 'apartaestudio', label: 'Apartaestudio' },
  { id: 'casa', label: 'Casa' },
  { id: 'casa_campestre', label: 'Casa campestre' },
  { id: 'duplex', label: 'Dúplex' },
];

const BASIC_ZONES: TipoZona[] = ['bano', 'cocina', 'dormitorio', 'sala'];
const ADDITIONAL_ZONES: TipoZona[] = ['cuarto_servicio', 'garaje', 'lavanderia', 'oficina', 'terraza'];
const APARTAESTUDIO_ZONES: TipoZona[] = ['bano', 'cocina', 'dormitorio', 'lavanderia', 'oficina', 'sala'];

const ZONE_LABELS: Record<TipoZona, string> = {
  bano: 'Baño',
  cocina: 'Cocina',
  dormitorio: 'Dormitorio',
  sala: 'Sala',
  cuarto_servicio: 'Cuarto de servicio',
  garaje: 'Garaje',
  lavanderia: 'Lavandería',
  oficina: 'Oficina',
  terraza: 'Terraza',
};

// SVG Iconos de Zonas Vectoriales con diseño fiel
const ZoneSvgIcon: React.FC<{ type: TipoZona; size?: number; color?: string }> = ({
  type,
  size = 24,
  color = '#5DD39E',
}) => {
  switch (type) {
    case 'bano':
      // Inodoro limpio
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Rect x="5" y="3" width="7" height="9" rx="1.5" />
          <Path d="M8 12h8a4 4 0 0 1 4 4v1a2 2 0 0 1-2 2H9" />
          <Path d="M10 19v2h4v-2" />
          <Circle cx="8.5" cy="5.5" r="0.75" fill={color} />
        </Svg>
      );
    case 'cocina':
      // Nevera con división y manijas
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Rect x="6" y="2" width="12" height="20" rx="2" />
          <Line x1="6" y1="9" x2="18" y2="9" />
          <Line x1="8.5" y1="5.5" x2="8.5" y2="7.5" />
          <Line x1="8.5" y1="12" x2="8.5" y2="15" />
        </Svg>
      );
    case 'dormitorio':
      // Cama con cabecera y almohada
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M3 5v14M3 10h18a2 2 0 0 1 2 2v7M3 16h20" />
          <Path d="M7 10v4h5v-4H7z" />
        </Svg>
      );
    case 'sala':
      // Sofá / sillón
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M6 9a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v4H6V9z" />
          <Path d="M4 11a2 2 0 0 1 2-2v6a2 2 0 0 1-2-2v-2zM20 11a2 2 0 0 0-2-2v6a2 2 0 0 0 2-2v-2z" />
          <Path d="M4 15h16v2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-2z" />
          <Line x1="7" y1="18" x2="7" y2="20" />
          <Line x1="17" y1="18" x2="17" y2="20" />
        </Svg>
      );
    case 'cuarto_servicio':
      // Puerta cerrada
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16" />
          <Line x1="3" y1="21" x2="21" y2="21" />
          <Circle cx="9" cy="12" r="1.2" fill={color} />
        </Svg>
      );
    case 'garaje':
      // Coche
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M5 11l2-4h10l2 4v6H5v-6z" />
          <Circle cx="7.5" cy="17" r="1.8" />
          <Circle cx="16.5" cy="17" r="1.8" />
          <Line x1="5" y1="14" x2="19" y2="14" />
        </Svg>
      );
    case 'lavanderia':
      // Lavadora con tambor y línea diagonal
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Rect x="4" y="3" width="16" height="18" rx="2" />
          <Circle cx="12" cy="13" r="4.5" />
          <Line x1="9" y1="10.5" x2="15" y2="15.5" />
          <Circle cx="7.5" cy="6.5" r="1" fill={color} />
          <Line x1="11" y1="6.5" x2="16.5" y2="6.5" />
        </Svg>
      );
    case 'oficina':
      // Pantalla de computador / monitor
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Rect x="3" y="4" width="18" height="12" rx="2" />
          <Line x1="12" y1="16" x2="12" y2="20" />
          <Line x1="8" y1="20" x2="16" y2="20" />
        </Svg>
      );
    case 'terraza':
      // Reja de balcón / terraza
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Rect x="4" y="4" width="3.5" height="15" rx="1.5" />
          <Rect x="10.25" y="4" width="3.5" height="15" rx="1.5" />
          <Rect x="16.5" y="4" width="3.5" height="15" rx="1.5" />
          <Line x1="3" y1="8" x2="21" y2="8" />
          <Line x1="3" y1="15" x2="21" y2="15" />
        </Svg>
      );
  }
};

// Spinner animado de rayos verdes como en la Imagen 4
const RadialRaysSpinner: React.FC = () => {
  const spinAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.timing(spinAnim, {
        toValue: 1,
        duration: 1200,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    );
    animation.start();
    return () => animation.stop();
  }, [spinAnim]);

  const spin = spinAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <Animated.View style={{ transform: [{ rotate: spin }], width: 50, height: 50 }}>
      <Svg width={50} height={50} viewBox="0 0 40 40">
        {[0, 45, 90, 135, 180, 225, 270, 315].map((angle, i) => (
          <Line
            key={angle}
            x1="20"
            y1="6"
            x2="20"
            y2="11"
            stroke="#5DD39E"
            strokeWidth="3.2"
            strokeLinecap="round"
            opacity={(i + 1) / 8}
            transform={`rotate(${angle} 20 20)`}
          />
        ))}
      </Svg>
    </Animated.View>
  );
};

export const OnboardingScreen: React.FC = () => {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const params = useLocalSearchParams<{
    step?: string;
    nombreHogar?: string;
    tipoVivienda?: string;
  }>();

  // Estados del flujo
  const [step, setStep] = useState<1 | 2 | 'loading' | 'error'>(
    params.step === '2' ? 2 : params.step === 'loading' ? 'loading' : params.step === 'error' ? 'error' : 1
  );
  const [nombreHogar, setNombreHogar] = useState(params.nombreHogar || 'Casa García');
  const [tipoVivienda, setTipoVivienda] = useState<TipoVivienda>(
    (params.tipoVivienda as TipoVivienda) || 'apartamento'
  );
  const [isInputFocused, setIsInputFocused] = useState(false);

  // Zonas elegidas (por defecto para apartamento las 4 básicas + lavandería + oficina como en Imagen 2)
  const [selectedZones, setSelectedZones] = useState<TipoZona[]>([
    'bano',
    'cocina',
    'dormitorio',
    'sala',
    'lavanderia',
    'oficina',
  ]);

  // Al cambiar a apartaestudio o vivienda estándar, ajustar zonas por RN-X-09
  const handleSelectHousingType = (type: TipoVivienda) => {
    setTipoVivienda(type);
    if (type === 'apartaestudio') {
      // Filtrar a las permitidas en apartaestudio: bano, cocina, sala, lavanderia, oficina (5 zonas como en Imagen 3)
      setSelectedZones(['bano', 'cocina', 'lavanderia', 'oficina', 'sala']);
    } else {
      // Asegurar que las 4 básicas siempre estén incluidas
      setSelectedZones((prev) => {
        const set = new Set([...prev, ...BASIC_ZONES]);
        return Array.from(set);
      });
    }
  };

  // Alternar selección de zona
  const handleToggleZone = (zone: TipoZona) => {
    if (tipoVivienda === 'apartaestudio') {
      if (selectedZones.includes(zone)) {
        // Validación de mínimo 3 zonas en apartaestudio
        if (selectedZones.length <= 3) {
          Alert.alert('Mínimo requerido', 'En apartaestudio debes mantener al menos 3 zonas.');
          return;
        }
        // Validar que al menos 3 queden básicas
        const remaining = selectedZones.filter((z) => z !== zone);
        const remainingBasics = remaining.filter((z) => BASIC_ZONES.includes(z)).length;
        if (remainingBasics < 3 && BASIC_ZONES.includes(zone)) {
          Alert.alert('Zonas básicas requeridas', 'Al menos 3 zonas deben ser básicas (Baño, Cocina, Dormitorio, Sala).');
          return;
        }
        setSelectedZones(remaining);
      } else {
        // Máximo 5 zonas en apartaestudio
        if (selectedZones.length >= 5) {
          Alert.alert('Máximo alcanzado', 'Llegaste al máximo de 5 zonas para apartaestudio. Quita una para elegir otra.');
          return;
        }
        setSelectedZones([...selectedZones, zone]);
      }
    } else {
      // Vivienda estándar: las 4 básicas están bloqueadas (incluidas)
      if (BASIC_ZONES.includes(zone)) {
        Alert.alert('Zona básica', 'Las 4 zonas básicas vienen incluidas y no se pueden quitar en este tipo de vivienda.');
        return;
      }
      if (selectedZones.includes(zone)) {
        setSelectedZones(selectedZones.filter((z) => z !== zone));
      } else {
        setSelectedZones([...selectedZones, zone]);
      }
    }
  };

  // Confirmar cierre de sesión (RN-IX-08)
  const handleSignOut = () => {
    Alert.alert(
      '¿Cerrar sesión?',
      'Se cancelará la creación del hogar y no se guardará ningún dato.',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Cerrar sesión',
          style: 'destructive',
          onPress: () => router.replace('/login'),
        },
      ]
    );
  };

  // Crear hogar y ejecutar backfill (RN-X-03) navegando a la pantalla de Carga / Backfill
  const handleCreateHousehold = () => {
    router.push({
      pathname: '/preparando-hogar',
      params: {
        nombreHogar: nombreHogar.trim() || 'Mi Hogar',
        tipoVivienda,
        zonas: JSON.stringify(selectedZones),
      },
    });
  };

  // Reintentar desde la pantalla de error
  const handleRetry = () => {
    handleCreateHousehold();
  };

  /* ========================================================================= */
  /* VISTA: CARGA / BACKFILL (Imagen 4)                                         */
  /* ========================================================================= */
  if (step === 'loading') {
    return (
      <View style={[styles.fullContainer, styles.centeredLoading]}>
        <StatusBar barStyle="light-content" backgroundColor="#0D1F1A" />
        <Image
          source={require('../../assets/images/zentheris-logo.png')}
          style={styles.logoCentered}
          resizeMode="contain"
        />
        <View style={styles.spinnerContainer}>
          <RadialRaysSpinner />
        </View>
        <Text style={styles.loadingHeading}>Preparando y analizando tu hogar...</Text>

        {/* Control dev para probar el estado de error de la Imagen 5 */}
        <TouchableOpacity
          style={styles.devSimulateErrorBtn}
          onPress={() => setStep('error')}
        >
          <Text style={styles.devSimulateErrorText}>⚡ Simular error (Ver Imagen 5)</Text>
        </TouchableOpacity>
      </View>
    );
  }

  /* ========================================================================= */
  /* VISTA: ERROR AL CREAR HOGAR (Imagen 5)                                    */
  /* ========================================================================= */
  if (step === 'error') {
    return (
      <View style={[styles.fullContainer, styles.errorContainerCentered]}>
        <StatusBar barStyle="light-content" backgroundColor="#0D1F1A" />
        <View style={styles.errorCenteredBlock}>
          <Image
            source={require('../../assets/images/zentheris-logo.png')}
            style={styles.logoCentered}
            resizeMode="contain"
          />

          {/* Tarjeta de Error */}
          <View style={styles.errorAlertCard}>
            <Ionicons
              name="close-circle"
              size={24}
              color="#EF4444"
              style={styles.errorCardIcon}
            />
            <View style={styles.errorCardTextContainer}>
              <Text style={styles.errorCardTitle}>No pudimos crear tu hogar</Text>
              <Text style={styles.errorCardDescription}>
                No se guardó ningún dato. Revisa tu conexión e inténtalo de nuevo.
              </Text>
            </View>
          </View>

          {/* Botones centrados directamente debajo de la tarjeta */}
          <TouchableOpacity
            style={styles.solidPrimaryButton}
            onPress={handleRetry}
            activeOpacity={0.85}
          >
            <Text style={styles.solidPrimaryButtonText}>Reintentar</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.backToDataButton}
            onPress={() => setStep(2)}
            activeOpacity={0.7}
          >
            <Text style={styles.backToDataButtonText}>Volver a mis datos</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  /* ========================================================================= */
  /* VISTA: PASO 1 (Imagen 1)                                                  */
  /* ========================================================================= */
  if (step === 1) {
    return (
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.fullContainer}
      >
        <StatusBar barStyle="light-content" backgroundColor="#0D1F1A" />
        <ScrollView
          style={styles.scrollArea}
          contentContainerStyle={[
            styles.scrollContent,
            { paddingTop: Math.max(insets.top, 16) + 12 },
          ]}
          keyboardShouldPersistTaps="handled"
        >
          {/* Logo en esquina superior izquierda */}
          <View style={styles.step1LogoWrapper}>
            <Image
              source={require('../../assets/images/zentheris-logo.png')}
              style={styles.step1LogoImage}
              resizeMode="contain"
            />
          </View>

          {/* Indicador de pasos: Paso 1 de 2 */}
          <View style={styles.stepIndicatorContainer}>
            <Text style={styles.stepIndicatorText}>Paso 1 de 2</Text>
            <View style={styles.progressBarContainer}>
              <View style={[styles.progressSegment, styles.progressSegmentActive]} />
              <View style={[styles.progressSegment, styles.progressSegmentInactive]} />
            </View>
          </View>

          {/* Título principal */}
          <Text style={styles.mainTitle}>Crea tu hogar</Text>

          {/* Campo: Nombre del hogar */}
          <View style={styles.fieldSection}>
            <Text style={styles.fieldLabel}>Nombre del hogar</Text>
            <View
              style={[
                styles.textInputContainer,
                isInputFocused && styles.textInputContainerFocused,
              ]}
            >
              <TextInput
                style={styles.textInput}
                placeholder="Ej. Casa García"
                placeholderTextColor="#5A7870"
                value={nombreHogar}
                onChangeText={setNombreHogar}
                onFocus={() => setIsInputFocused(true)}
                onBlur={() => setIsInputFocused(false)}
              />
            </View>
          </View>

          {/* Selector: Tipo de vivienda */}
          <View style={styles.fieldSection}>
            <Text style={styles.fieldLabel}>Tipo de vivienda</Text>
            <View style={styles.chipsRow}>
              {HOUSING_OPTIONS.map((opt) => {
                const isSelected = tipoVivienda === opt.id;
                return (
                  <TouchableOpacity
                    key={opt.id}
                    style={[
                      styles.chip,
                      isSelected ? styles.chipSelected : styles.chipUnselected,
                    ]}
                    onPress={() => handleSelectHousingType(opt.id)}
                    activeOpacity={0.8}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        isSelected ? styles.chipTextSelected : styles.chipTextUnselected,
                      ]}
                    >
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Tarjeta de Información */}
          <View style={styles.infoCard}>
            <Ionicons
              name="information-circle-outline"
              size={22}
              color="#5DD39E"
              style={styles.infoCardIcon}
            />
            <View style={styles.infoCardTextContainer}>
              <Text style={styles.infoCardTitle}>El tipo de vivienda define tus zonas</Text>
              <Text style={styles.infoCardDescription}>
                En el siguiente paso verás las zonas disponibles para tu vivienda.
              </Text>
            </View>
          </View>
        </ScrollView>

        {/* Acciones inferiores */}
        <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) + 16 }]}>
          <TouchableOpacity
            style={[
              styles.solidPrimaryButton,
              !nombreHogar.trim() && styles.buttonDisabled,
            ]}
            onPress={() => setStep(2)}
            disabled={!nombreHogar.trim()}
            activeOpacity={0.85}
          >
            <Text style={styles.solidPrimaryButtonText}>Continuar</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.signOutLink}
            onPress={handleSignOut}
            activeOpacity={0.7}
          >
            <Text style={styles.signOutLinkText}>Cerrar sesión</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    );
  }

  /* ========================================================================= */
  /* VISTA: PASO 2 (Imagen 2 e Imagen 3)                                       */
  /* ========================================================================= */
  const isApartaestudio = tipoVivienda === 'apartaestudio';
  const totalCount = selectedZones.length;

  return (
    <View style={styles.fullContainer}>
      <StatusBar barStyle="light-content" backgroundColor="#0D1F1A" />

      {/* Barra de cabecera */}
      <View style={[styles.step2HeaderBar, { paddingTop: Math.max(insets.top, 16) + 8 }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => setStep(1)}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          activeOpacity={0.7}
        >
          <Ionicons name="chevron-back" size={26} color="#C4D4CF" />
        </TouchableOpacity>
        <Text style={styles.step2HeaderTitle}>Crea tu hogar</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollArea}
        contentContainerStyle={styles.scrollContentStep2}
        keyboardShouldPersistTaps="handled"
      >
        {/* Indicador de pasos: Paso 2 de 2 */}
        <View style={styles.stepIndicatorContainer}>
          <Text style={styles.stepIndicatorText}>Paso 2 de 2</Text>
          <View style={styles.progressBarContainer}>
            <View style={[styles.progressSegment, styles.progressSegmentActive]} />
            <View style={[styles.progressSegment, styles.progressSegmentActive]} />
          </View>
        </View>

        {/* Título y subtítulo */}
        <Text style={styles.mainTitle}>Elige las zonas de tu hogar</Text>

        {isApartaestudio ? (
          <Text style={styles.step2Subtitle}>
            En apartaestudio eliges de 3 a 5 zonas; al menos 3 deben ser básicas. Las zonas no se pueden cambiar después.
          </Text>
        ) : (
          <Text style={styles.step2Subtitle}>
            Las zonas no se pueden cambiar después de crear el hogar.
          </Text>
        )}

        {/* Contador de zonas elegidas */}
        <View style={styles.badgeContainer}>
          {isApartaestudio ? (
            <View
              style={[
                styles.badgePill,
                totalCount === 5 ? styles.badgePillFull : styles.badgePillNormal,
              ]}
            >
              <Text
                style={[
                  styles.badgeText,
                  totalCount === 5 ? styles.badgeTextFull : styles.badgeTextNormal,
                ]}
              >
                {totalCount} de 5 zonas
              </Text>
            </View>
          ) : (
            <View style={[styles.badgePill, styles.badgePillNormal]}>
              <Text style={[styles.badgeText, styles.badgeTextNormal]}>
                {totalCount} zonas elegidas
              </Text>
            </View>
          )}
        </View>

        {/* =================================================================== */}
        {/* CASO A: VIVIENDA ESTÁNDAR (Apartamento, Casa, etc.) -> IMAGEN 2     */}
        {/* =================================================================== */}
        {!isApartaestudio && (
          <>
            {/* Sección 1: Básicas · incluidas */}
            <Text style={styles.sectionHeading}>Básicas · incluidas</Text>
            <View style={styles.zonesGrid}>
              {BASIC_ZONES.map((zone) => (
                <View key={zone} style={[styles.zoneCard, styles.zoneCardBasicIncluded]}>
                  <View style={styles.zoneCardTopRow}>
                    <ZoneSvgIcon type={zone} size={24} color="#5DD39E" />
                    <Ionicons name="lock-closed" size={16} color="#5DD39E" />
                  </View>
                  <View style={styles.zoneCardBottom}>
                    <Text style={styles.zoneCardTitleSelected}>{ZONE_LABELS[zone]}</Text>
                    <Text style={styles.zoneCardSubtitle}>Básica</Text>
                  </View>
                </View>
              ))}
            </View>

            {/* Sección 2: Adicionales */}
            <Text style={[styles.sectionHeading, { marginTop: 20 }]}>Adicionales</Text>
            <View style={styles.zonesGrid}>
              {ADDITIONAL_ZONES.map((zone) => {
                const isSelected = selectedZones.includes(zone);
                return (
                  <TouchableOpacity
                    key={zone}
                    style={[
                      styles.zoneCard,
                      isSelected ? styles.zoneCardSelected : styles.zoneCardUnselected,
                    ]}
                    onPress={() => handleToggleZone(zone)}
                    activeOpacity={0.8}
                  >
                    <View style={styles.zoneCardTopRow}>
                      <ZoneSvgIcon
                        type={zone}
                        size={24}
                        color={isSelected ? '#5DD39E' : '#C4D4CF'}
                      />
                      {isSelected ? (
                        <Ionicons name="checkmark-circle" size={17} color="#5DD39E" />
                      ) : (
                        <View style={{ width: 17, height: 17 }} />
                      )}
                    </View>
                    <View style={styles.zoneCardBottom}>
                      <Text
                        style={
                          isSelected ? styles.zoneCardTitleSelected : styles.zoneCardTitleUnselected
                        }
                      >
                        {ZONE_LABELS[zone]}
                      </Text>
                      <Text style={styles.zoneCardSubtitle}>
                        {isSelected ? 'Elegida' : 'Agregar'}
                      </Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Tarjeta de Información Básicas */}
            <View style={styles.infoCard}>
              <Ionicons
                name="information-circle-outline"
                size={22}
                color="#5DD39E"
                style={styles.infoCardIcon}
              />
              <View style={styles.infoCardTextContainer}>
                <Text style={styles.infoCardTitle}>Las 4 zonas básicas vienen incluidas</Text>
                <Text style={styles.infoCardDescription}>
                  En apartamento, casa, dúplex y casa campestre no se pueden quitar.
                </Text>
              </View>
            </View>
          </>
        )}

        {/* =================================================================== */}
        {/* CASO B: APARTAESTUDIO -> IMAGEN 3                                   */}
        {/* =================================================================== */}
        {isApartaestudio && (
          <>
            <View style={styles.zonesGrid}>
              {APARTAESTUDIO_ZONES.map((zone) => {
                const isSelected = selectedZones.includes(zone);
                const isMaxReached = selectedZones.length >= 5 && !isSelected;

                return (
                  <TouchableOpacity
                    key={zone}
                    style={[
                      styles.zoneCard,
                      isSelected
                        ? styles.zoneCardSelected
                        : isMaxReached
                        ? styles.zoneCardDisabled
                        : styles.zoneCardUnselected,
                    ]}
                    onPress={() => handleToggleZone(zone)}
                    activeOpacity={0.8}
                  >
                    <View style={styles.zoneCardTopRow}>
                      <ZoneSvgIcon
                        type={zone}
                        size={24}
                        color={
                          isSelected
                            ? '#5DD39E'
                            : isMaxReached
                            ? '#4E6E66'
                            : '#C4D4CF'
                        }
                      />
                      {isSelected ? (
                        <Ionicons name="checkmark-circle" size={17} color="#5DD39E" />
                      ) : (
                        <View style={{ width: 17, height: 17 }} />
                      )}
                    </View>
                    <View style={styles.zoneCardBottom}>
                      <Text
                        style={
                          isSelected
                            ? styles.zoneCardTitleSelected
                            : isMaxReached
                            ? styles.zoneCardTitleDisabled
                            : styles.zoneCardTitleUnselected
                        }
                      >
                        {ZONE_LABELS[zone]}
                      </Text>
                      <Text style={styles.zoneCardSubtitle}>
                        {isSelected
                          ? 'Elegida'
                          : isMaxReached
                          ? 'No disponible'
                          : 'Agregar'}
                      </Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Tarjeta de Información Apartaestudio */}
            <View style={styles.infoCard}>
              <Ionicons
                name="information-circle-outline"
                size={22}
                color="#5DD39E"
                style={styles.infoCardIcon}
              />
              <View style={styles.infoCardTextContainer}>
                <Text style={styles.infoCardTitle}>
                  {totalCount === 5
                    ? 'Llegaste al máximo de 5 zonas'
                    : 'Selecciona entre 3 y 5 zonas'}
                </Text>
                <Text style={styles.infoCardDescription}>
                  {totalCount === 5
                    ? 'Quita una zona para elegir otra. Terraza, garaje y cuarto de servicio no aplican a apartaestudio.'
                    : 'Al menos 3 deben ser zonas básicas (Baño, Cocina, Dormitorio, Sala).'}
                </Text>
              </View>
            </View>
          </>
        )}
      </ScrollView>

      {/* Botón inferior: Crear mi hogar */}
      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) + 16 }]}>
        <TouchableOpacity
          style={styles.solidPrimaryButton}
          onPress={handleCreateHousehold}
          activeOpacity={0.85}
        >
          <Text style={styles.solidPrimaryButtonText}>Crear mi hogar</Text>
        </TouchableOpacity>

        {/* Selector de modo rápido para probar en prototipo */}
        <TouchableOpacity
          style={styles.devPillSwitcher}
          onPress={() =>
            handleSelectHousingType(
              tipoVivienda === 'apartamento' ? 'apartaestudio' : 'apartamento'
            )
          }
        >
          <Text style={styles.devPillSwitcherText}>
            👁️ Alternar vista: {isApartaestudio ? 'Apartamento (Imagen 2)' : 'Apartaestudio (Imagen 3)'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.devPillSwitcher, { marginTop: 2 }]}
          onPress={() => router.push('/preparando-hogar')}
        >
          <Text style={styles.devPillSwitcherText}>
            ⚡ Probar pantalla: Preparando y analizando tu hogar
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.devPillSwitcher, { marginTop: 2 }]}
          onPress={() => router.push('/error-crear-hogar')}
        >
          <Text style={styles.devPillSwitcherText}>
            ⚡ Probar pantalla: Error al crear hogar
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

export default OnboardingScreen;

const styles = StyleSheet.create({
  fullContainer: {
    flex: 1,
    backgroundColor: '#0D1F1A',
  },
  scrollArea: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  scrollContentStep2: {
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 20,
  },

  /* Paso 1 Logo */
  step1LogoWrapper: {
    width: 38,
    height: 62,
    marginBottom: 20,
  },
  step1LogoImage: {
    width: '100%',
    height: '100%',
  },

  /* Indicador de pasos */
  stepIndicatorContainer: {
    marginBottom: 16,
  },
  stepIndicatorText: {
    fontSize: 14,
    color: '#E8F1EE',
    marginBottom: 8,
    fontWeight: '500',
  },
  progressBarContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  progressSegment: {
    flex: 1,
    height: 3,
    borderRadius: 2,
  },
  progressSegmentActive: {
    backgroundColor: '#5DD39E',
  },
  progressSegmentInactive: {
    backgroundColor: '#2F453E',
  },

  /* Título principal */
  mainTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.2,
    marginBottom: 20,
  },

  /* Formulario Paso 1 */
  fieldSection: {
    marginBottom: 20,
  },
  fieldLabel: {
    fontSize: 14.5,
    fontWeight: '500',
    color: '#FFFFFF',
    marginBottom: 10,
  },
  textInputContainer: {
    backgroundColor: '#162B25',
    borderWidth: 1.5,
    borderColor: '#244039',
    borderRadius: 14,
    height: 52,
    paddingHorizontal: 16,
    justifyContent: 'center',
  },
  textInputContainerFocused: {
    borderColor: '#5DD39E',
  },
  textInput: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '500',
  },

  /* Chips de vivienda */
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  chip: {
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipSelected: {
    backgroundColor: '#5DD39E',
  },
  chipUnselected: {
    backgroundColor: '#162B25',
    borderWidth: 1,
    borderColor: '#244039',
  },
  chipText: {
    fontSize: 14,
  },
  chipTextSelected: {
    color: '#0D1F1A',
    fontWeight: '600',
  },
  chipTextUnselected: {
    color: '#C4D4CF',
    fontWeight: '500',
  },

  /* Tarjeta de información */
  infoCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#132E27',
    borderWidth: 1,
    borderColor: '#2F8A68',
    borderRadius: 14,
    padding: 16,
    marginTop: 18,
  },
  infoCardIcon: {
    marginRight: 12,
    marginTop: 2,
  },
  infoCardTextContainer: {
    flex: 1,
  },
  infoCardTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#5DD39E',
    marginBottom: 4,
  },
  infoCardDescription: {
    fontSize: 13.5,
    color: '#C4D4CF',
    lineHeight: 19,
  },

  /* Paso 2 Cabecera */
  step2HeaderBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  backButton: {
    width: 32,
    alignItems: 'flex-start',
    justifyContent: 'center',
  },
  step2HeaderTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 20,
    fontWeight: '700',
    color: '#E8F1EE',
  },
  headerSpacer: {
    width: 32,
  },
  step2Subtitle: {
    fontSize: 14,
    color: '#C4D4CF',
    lineHeight: 20,
    marginBottom: 12,
  },

  /* Contador de zonas */
  badgeContainer: {
    marginBottom: 16,
  },
  badgePill: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 14,
    alignSelf: 'flex-start',
  },
  badgePillNormal: {
    backgroundColor: '#163B30',
  },
  badgePillFull: {
    backgroundColor: '#E8F1EE',
  },
  badgeText: {
    fontSize: 12,
  },
  badgeTextNormal: {
    color: '#5DD39E',
    fontWeight: '600',
  },
  badgeTextFull: {
    color: '#162B25',
    fontWeight: '700',
  },

  /* Grid de Zonas */
  sectionHeading: {
    fontSize: 14,
    fontWeight: '600',
    color: '#C4D4CF',
    marginBottom: 12,
  },
  zonesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  zoneCard: {
    width: (SCREEN_WIDTH - 40 - 20) / 3,
    height: 96,
    borderRadius: 14,
    padding: 10,
    justifyContent: 'space-between',
  },
  zoneCardBasicIncluded: {
    backgroundColor: '#142C24',
    borderWidth: 1.5,
    borderColor: '#5DD39E',
  },
  zoneCardSelected: {
    backgroundColor: '#142C24',
    borderWidth: 1.5,
    borderColor: '#5DD39E',
  },
  zoneCardUnselected: {
    backgroundColor: '#162822',
    borderWidth: 1,
    borderColor: '#244039',
  },
  zoneCardDisabled: {
    backgroundColor: '#14211D',
    borderWidth: 1,
    borderColor: '#1C312B',
    opacity: 0.6,
  },
  zoneCardTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  zoneCardBottom: {
    marginTop: 4,
  },
  zoneCardTitleSelected: {
    fontSize: 13.5,
    fontWeight: '600',
    color: '#5DD39E',
    marginBottom: 2,
  },
  zoneCardTitleUnselected: {
    fontSize: 13.5,
    fontWeight: '600',
    color: '#FFFFFF',
    marginBottom: 2,
  },
  zoneCardTitleDisabled: {
    fontSize: 13.5,
    fontWeight: '600',
    color: '#718C84',
    marginBottom: 2,
  },
  zoneCardSubtitle: {
    fontSize: 11.5,
    color: '#8CA59C',
  },

  /* Botones comunes y Footer */
  footer: {
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  solidPrimaryButton: {
    backgroundColor: '#5DD39E',
    height: 52,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#5DD39E',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
  },
  solidPrimaryButtonText: {
    color: '#0D1F1A',
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  signOutLink: {
    alignItems: 'center',
    paddingVertical: 12,
  },
  signOutLinkText: {
    color: '#5DD39E',
    fontSize: 14.5,
    fontWeight: '600',
  },

  /* Vista de Carga (Imagen 4) */
  centeredLoading: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 28,
  },
  logoCentered: {
    width: 48,
    height: 82,
    alignSelf: 'center',
    marginBottom: 32,
  },
  spinnerContainer: {
    marginVertical: 16,
  },
  loadingHeading: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFFFFF',
    textAlign: 'center',
    marginTop: 18,
    lineHeight: 28,
  },
  devSimulateErrorBtn: {
    marginTop: 40,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  devSimulateErrorText: {
    color: '#5A7870',
    fontSize: 12,
    fontWeight: '500',
  },

  /* Vista de Error (Imagen 5) */
  errorContainerCentered: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  errorCenteredBlock: {
    width: '100%',
    maxWidth: 420,
    alignItems: 'stretch',
  },
  errorAlertCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#201517',
    borderWidth: 1.2,
    borderColor: '#4A2326',
    borderRadius: 14,
    padding: 18,
    marginBottom: 24,
  },
  errorCardIcon: {
    marginRight: 12,
    marginTop: 2,
  },
  errorCardTextContainer: {
    flex: 1,
  },
  errorCardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#F59099',
    marginBottom: 6,
  },
  errorCardDescription: {
    fontSize: 13.5,
    color: '#C4D4CF',
    lineHeight: 20,
  },
  backToDataButton: {
    backgroundColor: '#162822',
    borderWidth: 1,
    borderColor: '#244039',
    height: 52,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 12,
  },
  backToDataButtonText: {
    color: '#FFFFFF',
    fontSize: 15.5,
    fontWeight: '600',
  },

  /* Dev Switcher Pill */
  devPillSwitcher: {
    marginTop: 8,
    alignItems: 'center',
    paddingVertical: 6,
  },
  devPillSwitcherText: {
    color: '#5A7870',
    fontSize: 11.5,
    fontWeight: '500',
  },
});
