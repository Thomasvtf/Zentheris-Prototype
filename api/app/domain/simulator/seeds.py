"""Semillas estables (A14, RN-IV-04): SHA-256 de una serialización JSON canónica.

semilla = SHA-256({dominio, fecha, hogar_id, version, zona}) como entero de 256 bits.
Nunca se usa `hash()` de Python (depende de PYTHONHASHSEED) ni una semilla global.

Dominios de sorteo:
  "humor"   -> 1 uniforme por hogar y día (zona = None)
  "ruido"   -> 24 uniformes por zona y día (épsilon = 2u - 1)
  "eventos" -> 24 × 5 uniformes por zona y día, SIEMPRE los mismos 5 por hora
               (ocurrencia, potencia, duración, minuto, fracción), aunque la
               probabilidad sea 0: así cambiar un parámetro no desplaza los demás sorteos.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import date
from uuid import UUID

# Valores que entran en la semilla: no se traducen (cambiarían todas las lecturas).
DRAW_DOMAINS = ("humor", "ruido", "eventos")


def canonical_serialization(
    hogar_id: UUID | str, day: date, version: str, zone: str | None, domain: str
) -> bytes:
    """JSON canónico (claves ordenadas, sin espacios, UTF-8) del que sale la semilla."""
    if domain not in DRAW_DOMAINS:
        raise ValueError(f"dominio desconocido: {domain}")
    data = {
        "dominio": domain,
        "fecha": day.isoformat(),
        "hogar_id": str(UUID(str(hogar_id))),
        "version": version,
        "zona": zone,
    }
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def derive_seed(
    hogar_id: UUID | str, day: date, version: str, zone: str | None, domain: str
) -> int:
    """Semilla de 256 bits del sorteo."""
    digest = hashlib.sha256(canonical_serialization(hogar_id, day, version, zone, domain)).digest()
    return int.from_bytes(digest, "big")


def uniforms(
    hogar_id: UUID | str, day: date, version: str, zone: str | None, domain: str, n: int
) -> list[float]:
    """n uniformes en [0, 1) del Mersenne Twister sembrado con un entero.

    La secuencia de `random()` para una semilla entera es estable entre versiones de CPython.
    """
    rng = random.Random(derive_seed(hogar_id, day, version, zone, domain))
    return [rng.random() for _ in range(n)]
