"""Los datos copiados del Avance 03 en `data/` son los originales (SHA-256 del MANIFEST).

Si alguien los edita, las pruebas de equivalencia dejarían de comparar contra la referencia; por
eso fallan aquí primero. Se normaliza el salto de línea al del original: los JSON usan LF
(`.gitattributes` lo fija) y los CSV, CRLF (los escribió el módulo `csv`; `.gitattributes` no
fija *.csv, así que git puede dejarlos en LF según la plataforma).
"""

import hashlib

import pytest

from tests.simulator.support import DATA_DIR

# Valores de `MANIFEST.sha256` del zip `docs/datos/referencia/…Avance_03…zip`.
MANIFEST_SHA256 = {
    "prueba_amplio.json": "fefdf747aecbee653c3cb7de4b748272b26ed1febc07c8364cc8cb620812eab2",
    "prueba_compacto.json": "d247b73315a24092adab2a4e38ffde1724bf880f2212e8b26d0a0b868c4be4f2",
    "prueba_eficiente.json": "29489294360f24fde05396a07aa985d95da17e535a188e9a17c9ccb47f1ad547",
    "prueba_familiar.json": "3b34a4ec9b2980d3423cd237d8b6975f83bbe803f6c31622e4f7480106dca4b7",
    "prueba_intermedio.json": "476f98b93aea9ba82423c3496c9aed075e27d0b5e8467256fbcb8589319c7380",
    "validacion_perfil_horario.csv": (
        "b22b08dfe30607605362695b3965152909df51f9a5ce1d101e61fefdfed122f6"
    ),
    "validacion_totales_por_semilla.csv": (
        "865c8859928fa250347ccb35e541fe4a1d679ca723ea0fbca83c598e78634918"
    ),
}
# Extracto de `congelamiento/congelamiento.json` (MANIFEST a8baa786…cea8f376b2): solo las
# referencias y criterios que usan las pruebas. No es copia exacta; se fija su propio SHA-256.
EXTRACT_SHA256 = {
    "congelamiento_referencias.json": (
        "2b8734c4f638abffd2536c7ff73681af747695536c4ccff4f6a3c61ac5c0efdf"
    ),
}


def normalized_sha256(name: str) -> str:
    content = (DATA_DIR / name).read_bytes().replace(b"\r\n", b"\n")
    if name.endswith(".csv"):
        content = content.replace(b"\n", b"\r\n")
    return hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize(("name", "digest"), sorted({**MANIFEST_SHA256, **EXTRACT_SHA256}.items()))
def test_copied_reference_data_is_unchanged(name: str, digest: str):
    assert normalized_sha256(name) == digest


def test_every_data_file_is_pinned():
    present = {path.name for path in DATA_DIR.iterdir() if path.is_file()}
    assert present == set(MANIFEST_SHA256) | set(EXTRACT_SHA256)
