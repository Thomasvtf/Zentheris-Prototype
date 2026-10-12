import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface Zona {
  id: number;
  nombre: string;
  descripcion?: string;
  consumo?: string; // Ej: "0.5 kW"
  estado?: string;  // Ej: "Normal", "Alto", "Bajo"
}

export const DashboardScreen: React.FC = () => {
  const [unit, setUnit] = useState<'KW' | 'COP'>('KW');
  
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const fetchDashboardData = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/salud/bd');
      const data = await response.json();
      setZonas(data.zonas || []);
    } catch (error) {
      console.error('Error al cargar datos del backend:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchDashboardData();
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#00E676" />
      }
    >
      {/* 1. HEADER / ENCABEZADO */}
      <View style={styles.header}>
        
        <Text style={[styles.headerTitle, { textAlign: 'center'}]}>
          Panel principal
        </Text>
        
        <TouchableOpacity style={styles.iconBtn}>
          <Ionicons name="notifications-outline" size={22} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      <Text style={styles.greeting}>Buenos días, Nicolás</Text>

      {/* 2. CARD: CONSUMO ACUMULADO HOY */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardSubTitle}>Consumo acumulado hoy</Text>
          <Ionicons name="flash-outline" size={24} color="#A0AEC0" />
        </View>
        <Text style={styles.mainStatText}>12.5 kW</Text>
        <Text style={styles.goalText}>Meta 15.0 kWh</Text>
      </View>

      {/* 3. CARD: CONSUMO TOTAL ACTUAL */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardTitleText}>Consumo total actual:</Text>
          <View style={styles.rightIcons}>
            <Ionicons name="options-outline" size={20} color="#A0AEC0" style={{ marginRight: 10 }} />
            <Ionicons name="speedometer-outline" size={20} color="#A0AEC0" />
          </View>
        </View>

        {/* SEMÁFORO / LICES DE ESTADO */}
        <View style={styles.trafficLightContainer}>
          <View style={[styles.lightCircle, styles.lightGreenActive]} />
          <View style={[styles.lightCircle, styles.lightYellowOff]} />
          <View style={[styles.lightCircle, styles.lightRedOff]} />
        </View>

        <Text style={[styles.mainStatText, { textAlign: 'center', marginTop: 10 }]}>6 kW</Text>

        {/* INTERVALO CADA */}
        <Text style={[styles.sectionLabel, { textAlign: 'center', marginTop: 15 }]}>
        </Text>
        <View style={[styles.toggleGroup, { justifyContent: 'center', marginTop: 8 }]}>
          <TouchableOpacity
            style={[styles.toggleBtn, unit === 'KW' && styles.toggleBtnActive]}
            onPress={() => setUnit('KW')}
          >
            <Ionicons name="flash-outline" size={14} color={unit === 'KW' ? '#00E676' : '#A0AEC0'} />
            <Text style={[styles.toggleText, unit === 'KW' && styles.toggleTextActive]}>kW</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.toggleBtn, unit === 'COP' && styles.toggleBtnActive]}
            onPress={() => setUnit('COP')}
          >
            <Ionicons name="flash-outline" size={14} color={unit === 'COP' ? '#00E676' : '#A0AEC0'} />
            <Text style={[styles.toggleText, unit === 'COP' && styles.toggleTextActive]}>COP</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* 4. SECCIÓN ZONAS ACTIVAS */}
      <Text style={styles.sectionTitle}>Zonas activas</Text>

      {loading ? (
        <ActivityIndicator size="large" color="#00E676" style={{ marginTop: 20 }} />
      ) : (
        <View style={styles.zonesGrid}>
          {zonas.map((zona) => (
            <View key={zona.id} style={styles.zoneCard}>
              <View style={styles.zoneHeader}>
                <Ionicons name="tv-outline" size={18} color="#FFFFFF" />
                <Text style={styles.zoneName}>{zona.nombre}</Text>
              </View>
              <Text style={styles.zoneValue}>{zona.consumo || '0.5 kW'}</Text>
              <Text
                style={[
                  styles.zoneStatus,
                  zona.estado === 'Alto' ? { color: '#E53E3E' } : { color: '#81C784' },
                ]}
              >
                {zona.estado || 'Normal'}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D1F1A',
  },
  contentContainer: {
    padding: 20,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    borderBottomColor: '#FFFFFF14',
    borderBottomWidth: 1,
    paddingBottom: 10,
  },
  headerTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: 'bold',
    textAlign: 'center',
    marginLeft: 'auto',
    marginRight: 'auto',
  },
  iconBtn: {
    padding: 4,
    position: 'relative',
  },
  badge: {
    position: 'absolute',
    right: -2,
    top: -2,
    backgroundColor: '#E53E3E',
    borderRadius: 8,
    width: 16,
    height: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  badgeText: {
    color: '#FFF',
    fontSize: 10,
    fontWeight: 'bold',
  },
  greeting: {
    color: '#E2E8F0',
    fontSize: 16,
    textAlign: 'center',
    marginVertical: 18,
  },
  sectionRow: {
    marginBottom: 15,
  },
  sectionLabel: {
    color: '#718096',
    fontSize: 11,
    fontWeight: 'bold',
    marginBottom: 6,
  },
  toggleGroup: {
    flexDirection: 'row',
    gap: 10,
  },
  toggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#1A362D',
    gap: 4,
  },
  toggleBtnActive: {
    backgroundColor: '#163B30',
  },
  toggleText: {
    color: '#718096',
    fontSize: 13,
  },
  toggleTextActive: {
    color: '#5DD39E',
    fontWeight: '600',
  },
  card: {
    backgroundColor: '#162B25',
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: '#FFFFFF14',
    marginBottom: 16,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardSubTitle: {
    color: '#A0AEC0',
    fontSize: 14,
  },
  cardTitleText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  rightIcons: {
    flexDirection: 'row',
  },
  mainStatText: {
    color: '#00E676',
    fontSize: 32,
    fontWeight: 'bold',
    marginTop: 8,
  },
  goalText: {
    color: '#D69E2E',
    fontSize: 13,
    marginTop: 6,
  },
  trafficLightContainer: {
    flexDirection: 'row',
    backgroundColor: '#05110E',
    borderRadius: 40,
    padding: 10,
    justifyContent: 'space-around',
    alignItems: 'center',
    marginTop: 15,
    borderWidth: 1,
    borderColor: '#0E2A22',
  },
  lightCircle: {
    width: 50,
    height: 50,
    borderRadius: 25,
  },
  lightGreenActive: {
    backgroundColor: '#00E676',
    shadowColor: '#00E676',
    shadowOpacity: 0.8,
    shadowRadius: 10,
    elevation: 8,
  },
  lightYellowOff: {
    backgroundColor: '#383214',
  },
  lightRedOff: {
    backgroundColor: '#381A1A',
  },
  sectionTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: 'bold',
    marginTop: 10,
    marginBottom: 12,
  },
  zonesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  zoneCard: {
    backgroundColor: '#0B1F19',
    width: '48%',
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#13332A',
  },
  zoneHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  zoneName: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '500',
  },
  zoneValue: {
    color: '#00E676',
    fontSize: 22,
    fontWeight: 'bold',
    marginVertical: 6,
  },
  zoneStatus: {
    fontSize: 12,
  },
}); 