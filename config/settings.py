"""Configuración central del sistema. Único lugar con rutas y parámetros."""
from pathlib import Path
import os

# Carga el .env si existe (no falla si no está instalado python-dotenv).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Rutas base -------------------------------------------------------------
# settings.py está en config/, así que la raíz del proyecto es dos niveles arriba.
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

# --- Base de datos local (SQLite) ------------------------------------------
LOCAL_DB_PATH = DATA_DIR / "kiosko.db"
SCHEMA_LOCAL_PATH = DATA_DIR / "schema_local.sql"

# --- Base de datos nube (Neon PostgreSQL) ----------------------------------
NEON_DSN = os.getenv("NEON_DATABASE_URL", "")

# --- Parámetros de la app --------------------------------------------------
APP_NOMBRE = "Kiosko POS"
APP_VERSION = "0.1.0"

# Cada cuántos segundos el hilo de sincronización intenta subir ventas pendientes.
SYNC_INTERVALO_SEG = 60
