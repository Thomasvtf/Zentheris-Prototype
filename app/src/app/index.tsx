import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
const API_URL = process.env.EXPO_PUBLIC_API_URL;
export default function Pantalla() {
  const [estado, setEstado] = useState("Consultando...");
  const [zonas, setZonas] = useState<number | null>(null);
  useEffect(() => {
    fetch(`${API_URL}/salud/bd`)
      .then((r) => r.json())
      .then((datos) => {
        setEstado(datos.base_de_datos);
        setZonas(datos.zonas_registradas);
      })
      .catch((e) => setEstado(`Error: ${e.message}`));
  }, []);
  return (
    <View style={estilos.contenedor}>
      <Text style={estilos.titulo}>Zentheris</Text>
      <Text style={estilos.texto}>Base de datos: {estado}</Text>
      {zonas !== null && (
        <Text style={estilos.metrica}>{zonas} zonas registradas</Text>
      )}
    </View>
  );
}
const estilos = StyleSheet.create({
  contenedor: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#0D1117",
    gap: 12,
  },
  titulo: { fontSize: 32, fontWeight: "700", color: "#FFFFFF" },
  texto: { fontSize: 16, color: "#9BA1A6" },
  metrica: { fontSize: 24, fontWeight: "600", color: "#4ADE80" },
});
