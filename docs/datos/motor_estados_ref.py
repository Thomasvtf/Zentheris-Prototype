"""Motor de estados de REFERENCIA (no es código de producción).

Sirve para especificar y probar la clasificación normal / elevado / crítico con el
archivo umbrales-estado.v1.json (RN-XI-02 a RN-XI-07, RN-XIII-03, RN-XIII-05).
El backend debe reproducir los mismos resultados con estos mismos casos.
Solo biblioteca estándar.
"""
import json
from pathlib import Path

U = json.loads((Path(__file__).parent / "umbrales-estado.v1.json").read_text(encoding="utf-8"))


def var_pct(valor, referencia):
    if valor is None:
        return None
    if referencia is None or referencia <= 0:
        return None
    # Redondeo a 6 decimales para que 1,20/1,00 dé 20 % exacto (evita ruido de coma flotante).
    return round((valor / referencia - 1.0) * 100.0, 6)


def _clasificar(v, cfg):
    if v >= cfg["critico_desde_pct"]:
        return "critico"
    if v >= cfg["elevado_desde_pct"]:
        return "elevado"
    return "normal"


def estado_relativo(valor, referencia, bloque, exceso_kwh=None, dias_con_dato=30):
    """Estado de consumo actual, acumulado contra promedio, zona o día completo."""
    if valor is None:
        return "sin_datos"
    if dias_con_dato < U["referencia"]["minimo_dias_con_dato"] or referencia is None or referencia <= 0:
        return "sin_referencia"
    cfg = U[bloque]
    v = var_pct(valor, referencia)
    piso = cfg.get("exceso_minimo_kwh")
    if piso is not None:
        exceso = (valor - referencia) if exceso_kwh is None else exceso_kwh
        if exceso < piso:
            return "normal"
    return _clasificar(v, cfg)


def estado_acumulado_meta(acumulado_kwh, meta_mensual_kwh, dias_mes):
    if acumulado_kwh is None:
        return "sin_datos", None
    limite = meta_mensual_kwh / dias_mes
    pct = round(acumulado_kwh / limite * 100.0, 6)
    c = U["acumulado_meta"]
    if pct >= c["critico_desde_pct_del_limite"]:
        return "critico", pct
    if pct >= c["elevado_desde_pct_del_limite"]:
        return "elevado", pct
    return "normal", pct


def referencia_hora_con_meta(meta_mensual_kwh, dias_mes, promedios_24h, hora):
    """RN-XI-03 con meta: el límite diario se reparte según el perfil horario habitual del hogar."""
    total = sum(promedios_24h)
    if total <= 0:
        return None
    return meta_mensual_kwh / dias_mes * promedios_24h[hora] / total


def comparacion_periodo(actual_kwh, anterior_kwh):
    """Devuelve (variante de mensaje, estado). anterior None = sin_anterior."""
    if anterior_kwh is None:
        return "sin_anterior", "sin_referencia"
    if anterior_kwh <= 0:
        return "sin_referencia", "sin_referencia"
    v = var_pct(actual_kwh, anterior_kwh)
    c = U["comparacion_periodo"]
    if v < c["menor_si_menor_que_pct"]:
        variante = "menor"
    elif v < c["similar_si_menor_que_pct"]:
        variante = "similar"
    elif v < c["muy_mayor_desde_pct"]:
        variante = "mayor"
    else:
        variante = "muy_mayor"
    return variante, c["estado"][variante]


def es_pico(valor, promedio):
    v = var_pct(valor, promedio)
    return v is not None and v >= U["pico"]["minimo_pct"]


def estado_pico(valor, promedio, periodo):
    bloque = U["pico"]["estado_en_dia"] if periodo == "dia" else U["pico"]["estado_en_semana_y_mes"]
    return _clasificar(var_pct(valor, promedio), U[bloque])


def variacion_hora(actual, anterior):
    if actual is None or anterior is None or anterior <= 0:
        return "sin_dato"
    v = var_pct(actual, anterior)
    if abs(v) < U["variacion_hora_anterior"]["igual_si_abs_menor_que_pct"]:
        return "igual"
    return "mas" if v > 0 else "menos"


def proyeccion_cierre(acumulado_kwh, promedios_horas_restantes_hoy, dias_completos_restantes, promedio_diario_30d):
    """RN-XIII-05: lo que llevas + lo que sueles consumir en lo que falta del periodo."""
    return acumulado_kwh + sum(promedios_horas_restantes_hoy) + dias_completos_restantes * promedio_diario_30d


def proyeccion_cop(costo_acumulado_cop, proyeccion_kwh, acumulado_kwh, precio_vigente, cargo_fijo=None, es_mes=False):
    extra = (proyeccion_kwh - acumulado_kwh) * precio_vigente
    return costo_acumulado_cop + extra + ((cargo_fijo or 0) if es_mes else 0)
