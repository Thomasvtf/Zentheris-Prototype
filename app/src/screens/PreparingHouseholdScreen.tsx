import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  StatusBar,
  Image,
  Animated,
  Easing,
  TouchableOpacity,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import Svg, { Line } from 'react-native-svg';
import type { Schemas } from '../api/client';
import { createHouseholdOnboarding } from '../api/onboarding';

export interface PreparingHouseholdScreenProps {
  nombreHogar?: string;
  tipoVivienda?: string;
  zonas?: string[];
  autoRedirect?: boolean;
  onSuccess?: () => void;
  onError?: () => void;
}

export const PreparingHouseholdScreen: React.FC<PreparingHouseholdScreenProps> = ({
  nombreHogar: propNombre,
  tipoVivienda: propTipo,
  zonas: propZonas,
  autoRedirect = true,
  onSuccess,
  onError,
}) => {
  const router = useRouter();
  const params = useLocalSearchParams<{
    nombreHogar?: string;
    tipoVivienda?: string;
    zonas?: string;
  }>();

  const nombreHogar = propNombre || params.nombreHogar || 'Casa García';
  const tipoVivienda = (propTipo || params.tipoVivienda || 'apartamento') as Schemas['OnboardingCrear']['tipo_vivienda'];
  const zonas = propZonas || (params.zonas ? JSON.parse(params.zonas) : ['bano', 'cocina', 'dormitorio', 'sala']);

  // Animación continua de rotación para el spinner de rayos
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

  // Ejecución del proceso de creación y backfill
  useEffect(() => {
    if (!autoRedirect) return;

    let isMounted = true;
    const executeBackfill = async () => {
      try {
        const payload: Schemas['OnboardingCrear'] = {
          nombre_hogar: nombreHogar,
          tipo_vivienda: tipoVivienda,
          zonas,
        };

        // Simular tiempo de análisis y creación (mínimo 2 segundos)
        const minDelay = new Promise<void>((resolve) => setTimeout(resolve, 2200));
        await Promise.all([
          createHouseholdOnboarding(payload).catch(() => null),
          minDelay,
        ]);

        if (!isMounted) return;

        if (onSuccess) {
          onSuccess();
        } else {
          router.replace('/panel');
        }
      } catch {
        if (!isMounted) return;

        if (onError) {
          onError();
        } else {
          router.replace({
            pathname: '/error-crear-hogar',
            params: {
              nombreHogar,
              tipoVivienda,
              zonas: JSON.stringify(zonas),
            },
          });
        }
      }
    };

    executeBackfill();

    return () => {
      isMounted = false;
    };
  }, [autoRedirect]);

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0D1F1A" />

      {/* Contenido centrado: Logo oficial, Spinner y Título */}
      <View style={styles.centerContent}>
        <Image
          source={require('../../assets/images/zentheris-logo.png')}
          style={styles.logoImage}
          resizeMode="contain"
        />

        {/* Spinner animado con rayos verdes de 8 puntas */}
        <Animated.View style={[styles.spinnerWrapper, { transform: [{ rotate: spin }] }]}>
          <Svg width={46} height={46} viewBox="0 0 40 40">
            {[0, 45, 90, 135, 180, 225, 270, 315].map((angle, i) => (
              <Line
                key={angle}
                x1="20"
                y1="5.5"
                x2="20"
                y2="10.5"
                stroke="#5DD39E"
                strokeWidth="3.2"
                strokeLinecap="round"
                opacity={(i + 1) / 8}
                transform={`rotate(${angle} 20 20)`}
              />
            ))}
          </Svg>
        </Animated.View>

        <Text style={styles.title}>Preparando y analizando tu hogar...</Text>
      </View>

      {/* Botón sutil de prueba en prototipo para ver el estado de error */}
      <TouchableOpacity
        style={styles.devErrorButton}
        onPress={() =>
          router.replace({
            pathname: '/error-crear-hogar',
            params: {
              nombreHogar,
              tipoVivienda,
              zonas: JSON.stringify(zonas),
            },
          })
        }
      >
        <Text style={styles.devErrorText}>⚡ Simular error (Ver pantalla de error)</Text>
      </TouchableOpacity>
    </View>
  );
};

export default PreparingHouseholdScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D1F1A',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 30,
  },
  centerContent: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoImage: {
    width: 48,
    height: 82,
    marginBottom: 28,
  },
  spinnerWrapper: {
    width: 46,
    height: 46,
    marginBottom: 28,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFFFFF',
    textAlign: 'center',
    lineHeight: 30,
    maxWidth: 320,
    letterSpacing: 0.1,
  },
  devErrorButton: {
    position: 'absolute',
    bottom: 30,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  devErrorText: {
    color: '#5A7870',
    fontSize: 12,
    fontWeight: '500',
  },
});
