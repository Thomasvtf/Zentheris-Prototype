"""Comprobaciones de integración del repositorio de Zentheris.

Parte A (PR 3): las copias de `api/app/config_files/` deben ser idénticas, byte a byte,
a sus originales en `docs/` (PENDIENTES #4 y #5). Se compara el SHA-256.
Parte B (PR 5): contrato ↔ routers ↔ app ↔ mapa de integración. Aún no existe.

Uso, desde la raíz del repositorio: `python scripts/check_integration.py`.
Termina con código 0 si todo coincide y con código 1 si algo falta o difiere.
"""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONFIG_COPIES = (
    ("api/app/config_files/umbrales-estado.v1.json", "docs/datos/umbrales-estado.v1.json"),
    ("api/app/config_files/textos-backend.es-CO.json", "docs/textos/textos-backend.es-CO.json"),
)


def sha256_of(path: Path) -> str:
    """SHA-256 de los bytes del archivo, tal cual están en disco."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_config_copies() -> list[str]:
    """Parte A. Devuelve la lista de problemas; vacía si las copias coinciden."""
    problems = []
    for copy_rel, original_rel in CONFIG_COPIES:
        copy_path, original_path = ROOT / copy_rel, ROOT / original_rel
        missing = [rel for rel, p in ((copy_rel, copy_path), (original_rel, original_path))
                   if not p.is_file()]
        if missing:
            problems.append(f"falta: {', '.join(missing)}")
            continue
        copy_hash, original_hash = sha256_of(copy_path), sha256_of(original_path)
        if copy_hash != original_hash:
            problems.append(
                f"{copy_rel} difiere de {original_rel}\n"
                f"  copia:    {copy_hash}\n"
                f"  original: {original_hash}"
            )
    return problems


def main() -> int:
    problems = check_config_copies()
    if problems:
        print("config_files: las copias no coinciden con docs/ · ERROR")
        for problem in problems:
            print(f"- {problem}")
        print("Se editan en docs/ y se vuelven a copiar a api/app/config_files/.")
        return 1
    total = len(CONFIG_COPIES)
    print(f"config_files: {total}/{total} copias iguales a docs/ · OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
