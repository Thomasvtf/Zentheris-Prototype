import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  StatusBar,
  Image,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';

export interface HouseholdCreationErrorScreenProps {
  onRetry?: () => void;
  onBackToData?: () => void;
}

export const HouseholdCreationErrorScreen: React.FC<HouseholdCreationErrorScreenProps> = ({
  onRetry,
  onBackToData,
}) => {
  const router = useRouter();
  const params = useLocalSearchParams<{
    nombreHogar?: string;
    tipoVivienda?: string;
    zonas?: string;
  }>();

  const handleRetry = () => {
    if (onRetry) {
      onRetry();
    } else {
      router.replace({
        pathname: '/preparando-hogar',
        params: {
          nombreHogar: params.nombreHogar,
          tipoVivienda: params.tipoVivienda,
          zonas: params.zonas,
        },
      });
    }
  };

  const handleBackToData = () => {
    if (onBackToData) {
      onBackToData();
    } else {
      router.replace({
        pathname: '/onboarding',
        params: {
          nombreHogar: params.nombreHogar,
          tipoVivienda: params.tipoVivienda,
          step: '2',
        },
      });
    }
  };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0D1F1A" />

      {/* Todo el bloque centrado exactamente como en la 2da imagen */}
      <View style={styles.centeredBlock}>
        <Image
          source={require('../../assets/images/zentheris-logo.png')}
          style={styles.logoImage}
          resizeMode="contain"
        />

        {/* Tarjeta de Alerta de Error */}
        <View style={styles.alertCard}>
          <Ionicons
            name="close-circle"
            size={24}
            color="#EF4444"
            style={styles.alertCardIcon}
          />
          <View style={styles.alertCardTextContainer}>
            <Text style={styles.alertCardTitle}>No pudimos crear tu hogar</Text>
            <Text style={styles.alertCardDescription}>
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
          onPress={handleBackToData}
          activeOpacity={0.7}
        >
          <Text style={styles.backToDataButtonText}>Volver a mis datos</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

export default HouseholdCreationErrorScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D1F1A',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  centeredBlock: {
    width: '100%',
    maxWidth: 420,
    alignItems: 'stretch',
  },
  logoImage: {
    width: 44,
    height: 75,
    alignSelf: 'center',
    marginBottom: 24,
  },
  alertCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#201517',
    borderWidth: 1.2,
    borderColor: '#4A2326',
    borderRadius: 14,
    padding: 18,
    marginBottom: 24,
  },
  alertCardIcon: {
    marginRight: 12,
    marginTop: 2,
  },
  alertCardTextContainer: {
    flex: 1,
  },
  alertCardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#F59099',
    marginBottom: 6,
    letterSpacing: 0.1,
  },
  alertCardDescription: {
    fontSize: 13.5,
    color: '#C4D4CF',
    lineHeight: 20,
  },
  solidPrimaryButton: {
    backgroundColor: '#5DD39E',
    height: 52,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
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
  backToDataButton: {
    backgroundColor: '#162822',
    borderWidth: 1,
    borderColor: '#244039',
    height: 52,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  backToDataButtonText: {
    color: '#FFFFFF',
    fontSize: 15.5,
    fontWeight: '600',
  },
});
