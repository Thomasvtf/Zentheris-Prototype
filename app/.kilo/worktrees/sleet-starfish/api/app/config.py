"""Carga de variables de entorno."""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SIM_SEED = int(os.getenv("SIM_SEED", "42"))

if not DATABASE_URL:
    raise RuntimeError(
        "Falta DATABASE_URL. Revise que el archivo .env exista en la carpeta api."
    )