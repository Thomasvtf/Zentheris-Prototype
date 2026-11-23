"""Validación estricta de un conjunto de `perfiles_simulacion`.

Valida estructura y coherencia (sección 5 y tabla 12 de las reglas más las convenciones A05–A08
y CT01–CT05). Pasar la validación NO significa que el conjunto esté calibrado. Los códigos de
error son los de la referencia (Avance 03): no se traducen.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.domain.simulator.constants import (
    BASE_COLUMNS,
    CURVE_SUM_TOLERANCE,
    NOISE_KEYS,
    OPTIONAL_FIELDS,
    PEAK_KEYS,
    REQUIRED_FIELDS,
    SLOT_KEYS,
)
from app.domain.zone_rules import PERSONALITIES, ZONE_TYPES

ProfileError = tuple[str, str]  # (código, mensaje)


class ProfileParameterError(ValueError):
    """Conjunto rechazado; `errors` lista (código, mensaje)."""

    def __init__(self, errors: Iterable[ProfileError]) -> None:
        self.errors: list[ProfileError] = list(errors)
        super().__init__("; ".join(f"{code}: {message}" for code, message in self.errors))


# ---------------------------------------------------------------- lectura JSON
def _without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise ProfileParameterError([("clave_duplicada", f"claves repetidas: {repeated}")])
    return dict(pairs)


def _invalid_constant(name: str) -> None:
    raise ProfileParameterError([("no_finito", f"valor no permitido en JSON: {name}")])


def load_strict_json(text: str) -> Any:
    """`json.loads` que rechaza claves duplicadas, NaN e Infinity."""
    return json.loads(text, object_pairs_hook=_without_duplicates, parse_constant=_invalid_constant)


# ------------------------------------------------------------------ utilidades
def is_number(value: Any) -> bool:
    """Número JSON finito; los booleanos no cuentan como número."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_uuid_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _fits_numeric(value: float, scale: int, integer_digits: int) -> bool:
    """Cabe en NUMERIC(integer_digits + scale, scale) sin perder dígitos."""
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return False
    if number.as_tuple().exponent < -scale:
        return False
    return abs(number) < Decimal(10) ** integer_digits


def effective_probabilities(config: Mapping[str, Any]) -> list[float]:
    """Probabilidad por hora tras aplicar franjas [desde, hasta) (A05)."""
    probabilities = [float(config["probabilidad"])] * 24
    for slot in config["franjas"]:
        for hour in range(int(slot["desde"]), int(slot["hasta"])):
            probabilities[hour] = float(config["probabilidad"]) * float(slot["multiplicador"])
    return probabilities


def noise_margin(profile: Mapping[str, Any]) -> float:
    """σ/(1−φ): cota de |n|. < 1 evita denominadores nulos (A08/CT05)."""
    noise = profile["ruido_config"]
    return noise["intensidad"] / (1 - noise["memoria"])


# ------------------------------------------------------------------ validación
def validate_profile(profile: Any, require_noise_margin: bool = True) -> list[ProfileError]:
    """Lista de errores (vacía si el conjunto es estructuralmente válido)."""
    if not isinstance(profile, Mapping):
        return [("tipo", "el conjunto debe ser un objeto JSON")]
    errors: list[ProfileError] = []

    unknown = sorted(set(profile) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
    if unknown:
        errors.append(("clave_desconocida", f"campos fuera del contrato: {unknown}"))
    missing = [field for field in REQUIRED_FIELDS if field not in profile]
    if missing:
        errors.append(("campo_faltante", f"faltan: {missing}"))

    errors += _validate_identity(profile)
    errors += _validate_numbers(profile)
    if "curva_horaria" in profile:
        errors += _validate_curves(profile["curva_horaria"])
    if "ruido_config" in profile:
        errors += _validate_noise(profile["ruido_config"], require_noise_margin)
    if "picos_config" in profile:
        errors += _validate_peaks(profile["picos_config"])
    return errors


def _validate_identity(profile: Mapping[str, Any]) -> list[ProfileError]:
    errors: list[ProfileError] = []
    if "nombre" in profile and profile["nombre"] not in PERSONALITIES:
        errors.append(("nombre", f"nombre fuera de los cinco exactos: {profile['nombre']!r}"))
    if "activo" in profile and not isinstance(profile["activo"], bool):
        errors.append(("activo", "activo debe ser booleano"))
    if "id" in profile and not _is_uuid_text(profile["id"]):
        errors.append(("id", "id debe ser un UUID en texto"))
    for field in ("created_at", "updated_at"):
        if field in profile:
            try:
                datetime.fromisoformat(profile[field])
            except TypeError, ValueError:
                errors.append((field, f"{field} debe ser fecha ISO 8601"))
    return errors


def _validate_numbers(profile: Mapping[str, Any]) -> list[ProfileError]:
    errors: list[ProfileError] = []
    # bases NUMERIC(10,4) >= 0
    for column in BASE_COLUMNS.values():
        if column not in profile:
            continue
        value = profile[column]
        if not is_number(value):
            errors.append(("base_tipo", f"{column} debe ser número finito"))
        elif value < 0:
            errors.append(("base_negativa", f"{column} < 0"))
        elif not _fits_numeric(value, 4, 6):
            errors.append(("base_precision", f"{column} excede NUMERIC(10,4)"))

    # humor y factor NUMERIC(6,4)
    for field in ("humor_min", "humor_max", "factor_fin_semana"):
        if field in profile:
            value = profile[field]
            if not is_number(value):
                errors.append((f"{field}_tipo", f"{field} debe ser número finito"))
            elif not _fits_numeric(value, 4, 2):
                errors.append((f"{field}_precision", f"{field} excede NUMERIC(6,4)"))
    if all(is_number(profile.get(field)) for field in ("humor_min", "humor_max")):
        if profile["humor_min"] < 0:
            errors.append(("humor_negativo", "humor_min < 0"))
        if profile["humor_min"] > profile["humor_max"]:
            errors.append(("humor_invertido", "humor_min > humor_max"))
    if is_number(profile.get("factor_fin_semana")) and profile["factor_fin_semana"] <= 0:
        errors.append(("factor_no_positivo", "factor_fin_semana debe ser > 0"))
    return errors


def _validate_curves(curves: Any) -> list[ProfileError]:
    if not isinstance(curves, Mapping):
        return [("curva_tipo", "curva_horaria debe ser objeto")]
    errors: list[ProfileError] = []
    if "base" not in curves:
        errors.append(("curva_base", "curva_horaria.base es obligatoria"))
    for key, curve in curves.items():
        if key != "base" and key not in ZONE_TYPES:
            errors.append(("curva_clave", f"curva_horaria.{key} no es zona del catálogo"))
        elif not isinstance(curve, list) or len(curve) != 24:
            errors.append(("curva_longitud", f"curva {key}: exactamente 24 valores"))
        elif not all(is_number(value) for value in curve):
            errors.append(("curva_valor", f"curva {key}: valores numéricos finitos"))
        elif any(value < 0 for value in curve):
            errors.append(("curva_negativa", f"curva {key}: valores >= 0"))
        elif abs(math.fsum(curve) - 1.0) > CURVE_SUM_TOLERANCE:
            errors.append(("curva_suma", f"curva {key}: suma {math.fsum(curve)!r} != 1"))
    return errors


def _validate_noise(noise: Any, require_margin: bool) -> list[ProfileError]:
    if not isinstance(noise, Mapping):
        return [("ruido_tipo", "ruido_config debe ser objeto")]
    errors: list[ProfileError] = []
    extra = sorted(set(noise) - set(NOISE_KEYS))
    if extra:
        errors.append(
            ("ruido_clave", f"ruido_config solo admite memoria e intensidad; sobran {extra}")
        )
    memory, intensity = noise.get("memoria"), noise.get("intensidad")
    memory_ok = is_number(memory) and 0 <= memory < 1
    intensity_ok = is_number(intensity) and intensity >= 0
    if not memory_ok:
        errors.append(("ruido_memoria", "memoria debe estar en [0, 1)"))
    if not intensity_ok:
        errors.append(("ruido_intensidad", "intensidad debe ser >= 0"))
    if require_margin and memory_ok and intensity_ok and intensity / (1 - memory) >= 1:
        errors.append(("ruido_margen", "se exige intensidad/(1-memoria) < 1 (A08/CT05)"))
    return errors


def _validate_peaks(peaks: Any) -> list[ProfileError]:
    if not isinstance(peaks, Mapping):
        return [("picos_tipo", "picos_config debe ser objeto")]
    errors: list[ProfileError] = []
    for zone, config in peaks.items():
        errors += _validate_peak(zone, config)
    return errors


def _validate_peak(zone: str, config: Any) -> list[ProfileError]:
    path = f"picos_config.{zone}"
    if zone not in ZONE_TYPES:
        return [("pico_clave", f"{path} no es zona del catálogo")]
    if not isinstance(config, Mapping):
        return [("pico_tipo", f"{path} debe ser objeto")]
    errors: list[ProfileError] = []
    extra = sorted(set(config) - set(PEAK_KEYS))
    missing = [key for key in PEAK_KEYS if key not in config]
    if extra:
        errors.append(("pico_clave_desconocida", f"{path}: sobran {extra}"))
    if missing:
        return errors + [("pico_campo_faltante", f"{path}: faltan {missing}")]
    probability = config["probabilidad"]
    if not is_number(probability) or not 0 <= probability <= 1:
        errors.append(("pico_probabilidad", f"{path}.probabilidad en [0, 1]"))
    errors += _validate_range(config, "potencia_w", path, minimum=0)
    errors += _validate_range(config, "duracion_min", path, minimum=0)
    errors += _validate_range(config, "minuto_inicio", path, minimum=0, maximum=59, integer=True)
    errors += _validate_range(config, "fraccion_uso", path, minimum=0, maximum=1)
    slots = config["franjas"]
    if not isinstance(slots, list):
        return errors + [("franja_tipo", f"{path}.franjas debe ser lista")]
    errors += _validate_slots(slots, path)
    if not errors:
        bad = [h for h, p in enumerate(effective_probabilities(config)) if not 0 <= p <= 1]
        if bad:
            message = f"{path}: probabilidad efectiva fuera de [0,1] en horas {bad}"
            errors.append(("pico_probabilidad_efectiva", message))
    return errors


def _validate_range(
    config: Mapping[str, Any],
    key: str,
    path: str,
    minimum: float | None = None,
    maximum: float | None = None,
    integer: bool = False,
) -> list[ProfileError]:
    values = config.get(key)
    if not (isinstance(values, list) and len(values) == 2 and all(map(is_number, values))):
        return [("pico_rango", f"{path}.{key}: [min, max] numéricos")]
    low, high = values
    errors: list[ProfileError] = []
    if low > high:
        errors.append(("pico_rango_invertido", f"{path}.{key}: min > max"))
    if integer and not all(float(value).is_integer() for value in values):
        errors.append(("pico_rango_entero", f"{path}.{key}: valores enteros"))
    if minimum is not None and min(low, high) < minimum:
        errors.append(("pico_rango_limite", f"{path}.{key}: valor < {minimum}"))
    if maximum is not None and max(low, high) > maximum:
        errors.append(("pico_rango_limite", f"{path}.{key}: valor > {maximum}"))
    return errors


def _validate_slots(slots: list[Any], path: str) -> list[ProfileError]:
    errors: list[ProfileError] = []
    hours: set[int] = set()
    for slot in slots:
        if not isinstance(slot, Mapping) or set(slot) != set(SLOT_KEYS):
            message = f"{path}: franja con claves desde/hasta/multiplicador"
            errors.append(("franja_claves", message))
            continue
        start, end, multiplier = slot["desde"], slot["hasta"], slot["multiplicador"]
        if not all(map(is_number, (start, end, multiplier))) or not (
            float(start).is_integer() and float(end).is_integer()
        ):
            message = f"{path}: desde/hasta enteros, multiplicador numérico"
            errors.append(("franja_valor", message))
            continue
        if not 0 <= start < end <= 24:
            message = f"{path}: se exige 0 <= desde < hasta <= 24 ({start}, {end})"
            errors.append(("franja_limites", message))
            continue
        if multiplier < 0:
            errors.append(("franja_multiplicador", f"{path}: multiplicador >= 0"))
        new_hours = set(range(int(start), int(end)))
        if hours & new_hours:
            message = f"{path}: franjas solapadas en {sorted(hours & new_hours)}"
            errors.append(("franja_solapada", message))
        hours |= new_hours
    return errors


def validate_or_raise(
    profile: Mapping[str, Any], require_noise_margin: bool = True
) -> Mapping[str, Any]:
    """Devuelve el mismo perfil si es válido; si no, `ProfileParameterError`."""
    errors = validate_profile(profile, require_noise_margin)
    if errors:
        raise ProfileParameterError(errors)
    return profile


def validate_profile_set(profiles: Sequence[Mapping[str, Any]]) -> list[ProfileError]:
    """CT01: exactamente cinco conjuntos válidos, nombres exactos y sin colisiones."""
    errors: list[ProfileError] = []
    names = [profile.get("nombre") for profile in profiles]
    if sorted(names) != sorted(PERSONALITIES):
        errors.append(("cinco_nombres", f"se esperan los cinco nombres exactos; hay {names}"))
    for profile in profiles:
        errors += [
            (code, f"[{profile.get('nombre')}] {message}")
            for code, message in validate_profile(profile)
        ]
    ids = [profile["id"] for profile in profiles if "id" in profile]
    if len(ids) != len(set(ids)):
        errors.append(("id_duplicado", "ids repetidos entre conjuntos"))
    return errors
