"""Carga de variables de entorno."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Encuentra la ruta base del proyecto o de la carpeta 'api'
BASE_DIR = Path(__file__).resolve().parent.parent  # Ajusta si config.py está dentro de app/
env_path = BASE_DIR / ".env"

# Carga explícita indicando la ruta del archivo .env
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SIM_SEED = int(os.getenv("SIM_SEED", "42"))

if not DATABASE_URL:
    raise RuntimeError(
        "Falta DATABASE_URL. Revise que el archivo .env exista en la carpeta adecuada."
    )