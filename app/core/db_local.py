"""Conexión y arranque de la base local SQLite.

Diseño para offline-first + hilo de sincronización:
  - WAL: permite que el hilo de sync lea mientras la caja escribe, sin bloqueos.
  - foreign_keys ON: integridad referencial (SQLite la trae apagada por defecto).
  - synchronous NORMAL: buen balance durabilidad/velocidad en SSD con WAL.

Patrón de uso: cada hilo abre SU PROPIA conexión con connect().
"""
import sqlite3

from config import settings


def connect() -> sqlite3.Connection:
    """Devuelve una conexión nueva a la base local, ya configurada."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.LOCAL_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row  # acceso a columnas por nombre: row["nombre"]
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db() -> None:
    """Crea la base y todas las tablas si no existen. Idempotente."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = settings.SCHEMA_LOCAL_PATH.read_text(encoding="utf-8")
    conn = connect()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def listar_tablas() -> list[str]:
    """Devuelve los nombres de tablas existentes (útil para verificación)."""
    conn = connect()
    try:
        filas = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        ).fetchall()
        return [f["name"] for f in filas]
    finally:
        conn.close()
