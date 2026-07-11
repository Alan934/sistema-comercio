"""Conexión y arranque de la base local SQLite.

Diseño para offline-first + hilo de sincronización:
  - WAL: permite que el hilo de sync lea mientras la caja escribe, sin bloqueos.
  - foreign_keys ON: integridad referencial (SQLite la trae apagada por defecto).
  - synchronous NORMAL: buen balance durabilidad/velocidad en SSD con WAL.

Patrón de uso: cada hilo abre SU PROPIA conexión con connect().
"""
import sqlite3
from datetime import date

from config import settings
from app.core.utils import ahora_iso, parse_fecha, sin_acentos


def connect() -> sqlite3.Connection:
    """Devuelve una conexión nueva a la base local, ya configurada."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.LOCAL_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row  # acceso a columnas por nombre: row["nombre"]
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    # Búsqueda por nombre indiferente al acento: sin_acentos('Azúcar') -> 'Azucar'.
    # deterministic=True permite usarla en índices/consultas cacheadas.
    conn.create_function("sin_acentos", 1, sin_acentos, deterministic=True)
    return conn


def _migrar(conn: sqlite3.Connection) -> None:
    """Migraciones livianas para bases ya creadas: agrega columnas nuevas si
    faltan (ALTER TABLE ADD COLUMN es idempotente vía chequeo previo)."""
    nuevas_columnas = {
        "clientes": [("sincronizado", "INTEGER NOT NULL DEFAULT 0")],
        "proveedores": [("sincronizado", "INTEGER NOT NULL DEFAULT 0"),
                        ("email", "TEXT")],
        "categorias": [("margen_pct", "NUMERIC(6,2)"),
                       ("sincronizado", "INTEGER NOT NULL DEFAULT 0")],
        "productos": [("margen_pct", "NUMERIC(6,2)"), ("ubicacion", "TEXT"),
                      ("sincronizado", "INTEGER NOT NULL DEFAULT 0")],
        "lotes": [("sincronizado", "INTEGER NOT NULL DEFAULT 0")],
        "cuenta_movimientos": [("metodo", "TEXT")],
        "gastos": [("metodo", "TEXT NOT NULL DEFAULT 'EFECTIVO'")],
        "cierres_caja": [
            ("cobros_efectivo", "NUMERIC(12,2) NOT NULL DEFAULT 0"),
            ("pagos_efectivo", "NUMERIC(12,2) NOT NULL DEFAULT 0")],
    }
    for tabla, columnas in nuevas_columnas.items():
        existentes = {row["name"]
                      for row in conn.execute(f"PRAGMA table_info({tabla})")}
        for nombre, definicion in columnas:
            if nombre not in existentes:
                conn.execute(
                    f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}")
    _normalizar_fechas_lotes(conn)
    _promover_super_admin(conn)


def _normalizar_fechas_lotes(conn: sqlite3.Connection) -> None:
    """Repara lotes cuya fecha de vencimiento quedó guardada en un formato no-ISO
    (ej. '11/07/2026' que cargaba el remito viejo). Sin esto, leer la lista de
    vencimientos rompía con date.fromisoformat. Reescribe a ISO las que se puedan
    interpretar; marca el lote para re-sincronizar. Idempotente."""
    filas = conn.execute(
        "SELECT id, fecha_vencimiento FROM lotes "
        "WHERE fecha_vencimiento IS NOT NULL AND fecha_vencimiento <> ''"
    ).fetchall()
    for f in filas:
        txt = f["fecha_vencimiento"]
        try:
            date.fromisoformat(txt)
            continue  # ya está en ISO, no tocar
        except ValueError:
            pass
        iso = parse_fecha(txt)
        if iso:
            conn.execute(
                "UPDATE lotes SET fecha_vencimiento = ?, sincronizado = 0, "
                "updated_at = ? WHERE id = ?",
                (iso, ahora_iso(), f["id"]),
            )


def _promover_super_admin(conn: sqlite3.Connection) -> None:
    """Bases creadas antes del rol SUPER_ADMIN: si no hay ningún super admin y
    existe un único administrador activo, se lo promueve (era el usuario inicial).
    Con varios administradores no se toca nada para no promover de más."""
    hay_super = conn.execute(
        "SELECT 1 FROM usuarios WHERE rol = 'SUPER_ADMIN' LIMIT 1"
    ).fetchone()
    if hay_super is not None:
        return
    admins = conn.execute(
        "SELECT id FROM usuarios WHERE rol = 'ADMIN' AND activo = 1"
    ).fetchall()
    if len(admins) == 1:
        conn.execute(
            "UPDATE usuarios SET rol = 'SUPER_ADMIN', sincronizado = 0, "
            "updated_at = ? WHERE id = ?",
            (ahora_iso(), admins[0]["id"]),
        )


def init_db() -> None:
    """Crea la base y todas las tablas si no existen. Idempotente."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = settings.SCHEMA_LOCAL_PATH.read_text(encoding="utf-8")
    conn = connect()
    try:
        conn.executescript(schema_sql)
        _migrar(conn)
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
