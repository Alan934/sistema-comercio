"""Configuración central del sistema. Único lugar con rutas y parámetros.

Maneja dos modos:
  - Desarrollo: corre desde el código fuente.
  - Compilado (PyInstaller): corre desde el .exe. Acá hay que separar
    los datos PERSISTENTES (base SQLite, .env: viven al lado del .exe y NO se
    tocan al actualizar) de los RECURSOS empaquetados de solo lectura
    (los .sql del esquema: van adentro del .exe y se extraen a una carpeta
    temporal en cada arranque).
"""
import os
import sys
from pathlib import Path

# ¿La app está corriendo compilada (frozen) por PyInstaller?
_FROZEN = getattr(sys, "frozen", False)

if _FROZEN:
    # Carpeta del ejecutable: persistente y editable por el usuario.
    APP_DIR = Path(sys.executable).resolve().parent
    # Carpeta temporal con los recursos empaquetados (solo lectura).
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    # En desarrollo, la raíz del proyecto (settings.py está en config/).
    APP_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = APP_DIR

BASE_DIR = APP_DIR  # compatibilidad

# --- Datos PERSISTENTES (sobreviven a las actualizaciones) ------------------
DATA_DIR = APP_DIR / "data"
LOCAL_DB_PATH = DATA_DIR / "kiosko.db"

# --- Recursos EMPAQUETADOS (solo lectura) ----------------------------------
SCHEMA_LOCAL_PATH = RESOURCE_DIR / "data" / "schema_local.sql"
SCHEMA_CLOUD_PATH = RESOURCE_DIR / "data" / "schema_cloud.sql"
ASSETS_DIR = RESOURCE_DIR / "assets"

# --- Cargar el .env (junto al .exe / raíz del proyecto) --------------------
try:
    from dotenv import load_dotenv
    _env = APP_DIR / ".env"
    load_dotenv(_env if _env.exists() else None)
except ImportError:
    pass

# --- Base de datos nube (Neon PostgreSQL) ----------------------------------
NEON_DSN = os.getenv("NEON_DATABASE_URL", "")

# --- Parámetros de la app --------------------------------------------------
APP_NOMBRE = "Kiosko POS"
APP_VERSION = "0.6.0"

# Cada cuántos segundos el hilo de sincronización intenta subir ventas pendientes.
SYNC_INTERVALO_SEG = 60
