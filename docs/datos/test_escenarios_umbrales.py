"""Pruebas de escenarios de umbrales (normal, pico/elevado, crítico) y de reglas de borde.

Uso: python -I test_escenarios_umbrales.py <ruta_avance03>
Datos 100 % simulados. Usa un hogar de referencia Consumo familiar (casa, 6 zonas).
"""
import sys, json, unittest, statistics as st
from pathlib import Path
from datetime import date

AV = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None
sys.path.insert(0, str(Path(__file__).parent))
import motor_estados_ref as M

class Simulado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(AV / "codigo"))
        from zentheris_sim.almacen import crear_hogar
        from zentheris_sim.simulador import simular_hogar
        p = json.loads((AV / "parametros_finales" / "consumo_familiar.json").read_text(encoding="utf-8"))
        Z = ["cocina", "sala", "dormitorio", "bano", "oficina", "lavanderia"]
        h = crear_hogar("escenarios-umbrales", "casa", Z)
        d = date(2026, 11, 3).toordinal()
        s = simular_hogar(h, p, (d - 31) * 24, (d + 1) * 24)
        cls.L = {z: [f[3] for f in v] for z, v in s.items()}
        cls.di = 31

    def prom(self, z, t):
        return st.mean(self.L[z][q * 24 + t] for q in range(self.di - 30, self.di))

    def test_escenario_normal(self):
        # Sin alteración: la mayoría de horas de hoy son normales para la cocina.
        estados = [M.estado_relativo(self.L["cocina"][self.di * 24 + t], self.prom("cocina", t), "zona_estado") for t in range(24)]
        self.assertGreaterEqual(estados.count("normal"), 20)

    def test_escenario_elevado(self):
        t = 19; ref = self.prom("cocina", t)
        valor = ref * 1.45  # +45 %
        self.assertGreaterEqual(valor - ref, 0.05)
        self.assertEqual(M.estado_relativo(valor, ref, "zona_estado"), "elevado")

    def test_escenario_critico(self):
        t = 19; ref = self.prom("cocina", t)
        valor = ref + 0.8  # freidora 1.200 W x 40 min aprox.
        self.assertEqual(M.estado_relativo(valor, ref, "zona_estado"), "critico")

    def test_piso_absoluto_evita_ruido(self):
        t = 3; ref = self.prom("dormitorio", t)
        self.assertLess(ref, 0.05)
        self.assertEqual(M.estado_relativo(ref * 3, ref, "zona_estado"), "normal" if ref * 2 < 0.05 else "critico")

class Reglas(unittest.TestCase):
    def test_bordes_consumo_actual(self):
        self.assertEqual(M.estado_relativo(1.199, 1.0, "consumo_actual"), "normal")
        self.assertEqual(M.estado_relativo(1.20, 1.0, "consumo_actual"), "elevado")
        self.assertEqual(M.estado_relativo(1.40, 1.0, "consumo_actual"), "critico")

    def test_sin_datos_no_es_cero(self):
        self.assertEqual(M.estado_relativo(None, 1.0, "consumo_actual"), "sin_datos")
        self.assertEqual(M.estado_relativo(0.0, 1.0, "consumo_actual"), "normal")

    def test_sin_referencia(self):
        self.assertEqual(M.estado_relativo(1.0, 1.0, "consumo_actual", dias_con_dato=6), "sin_referencia")
        self.assertEqual(M.estado_relativo(1.0, 0.0, "consumo_actual"), "sin_referencia")

    def test_acumulado_meta(self):
        self.assertEqual(M.estado_acumulado_meta(7.9, 300, 30)[0], "normal")
        self.assertEqual(M.estado_acumulado_meta(8.0, 300, 30)[0], "elevado")
        self.assertEqual(M.estado_acumulado_meta(10.0, 300, 30)[0], "critico")

    def test_comparacion(self):
        self.assertEqual(M.comparacion_periodo(94, 100), ("menor", "normal"))
        self.assertEqual(M.comparacion_periodo(95, 100), ("similar", "normal"))
        self.assertEqual(M.comparacion_periodo(110, 100), ("mayor", "elevado"))
        self.assertEqual(M.comparacion_periodo(125, 100), ("muy_mayor", "critico"))
        self.assertEqual(M.comparacion_periodo(10, None), ("sin_anterior", "sin_referencia"))

    def test_pico(self):
        self.assertFalse(M.es_pico(1.09, 1.0))
        self.assertTrue(M.es_pico(1.10, 1.0))
        self.assertEqual(M.estado_pico(1.15, 1.0, "dia"), "normal")
        self.assertEqual(M.estado_pico(1.15, 1.0, "semana"), "elevado")

    def test_variacion_hora(self):
        self.assertEqual(M.variacion_hora(1.004, 1.0), "igual")
        self.assertEqual(M.variacion_hora(1.02, 1.0), "mas")
        self.assertEqual(M.variacion_hora(1.0, None), "sin_dato")

    def test_referencia_meta_hora(self):
        prom = [1.0] * 24
        self.assertAlmostEqual(M.referencia_hora_con_meta(300, 30, prom, 5), 10 / 24)

    def test_proyeccion(self):
        self.assertAlmostEqual(M.proyeccion_cierre(10, [0.5, 0.5], 2, 4), 19)
        self.assertAlmostEqual(M.proyeccion_cop(1000, 19, 10, 800, cargo_fijo=12000, es_mes=True), 1000 + 7200 + 12000)
        self.assertAlmostEqual(M.proyeccion_cop(1000, 19, 10, 800, cargo_fijo=12000, es_mes=False), 1000 + 7200)

if __name__ == "__main__":
    unittest.main(verbosity=1)
