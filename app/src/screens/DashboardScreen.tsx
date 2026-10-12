import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator, RefreshControl, ListRenderItem } from 'react-native';

interface Zona {
  id: number;
  nombre: string;
  descripcion?: string;
}

export const DashboardScreen: React.FC = () => {
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [cargando, setCargando] = useState<boolean>(true);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/salud/bd')
      .then((res) => res.json())
      .then((data) => {
        setZonas(data.zonas || []);
        setCargando(false);
      })
      .catch((err) => {
        console.error(err);
        setCargando(false);
      });
  }, []);

  if (cargando) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#00E676" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.titulo}>Panel Principal</Text>
      <FlatList
        data={zonas}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.cardTitulo}>{item.nombre}</Text>
          </View>
        )}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0D1F1A', padding: 20 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#05110E' },
  titulo: { fontSize: 24, fontWeight: 'bold', color: '#FFFFFF', marginBottom: 15 },
  card: { backgroundColor: '#071A15', padding: 15, borderRadius: 10, marginBottom: 10 },
  cardTitulo: { color: '#00E676', fontSize: 16, fontWeight: 'bold' },
});