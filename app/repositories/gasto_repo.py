"""Acceso a datos de gastos."""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso
from app.models.gasto import Gasto


def crear(conn: sqlite3.Connection, gasto: Gasto) -> None:
    conn.execute(
        """INSERT INTO gastos
           (id, fecha, tipo, descripcion, monto, proveedor_id, metodo,
            sincronizado, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (gasto.id, gasto.fecha, gasto.tipo, gasto.descripcion,
         str(gasto.monto), gasto.proveedor_id, gasto.metodo, ahora_iso()),
    )


def listar(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    """Gastos en un rango de fechas (comparando solo la parte AAAA-MM-DD)."""
    return conn.execute(
        """SELECT g.id, g.fecha, g.tipo, g.descripcion, g.monto,
                  p.nombre AS proveedor_nombre
           FROM gastos g
           LEFT JOIN proveedores p ON p.id = g.proveedor_id
           WHERE substr(g.fecha, 1, 10) BETWEEN ? AND ?
           ORDER BY g.fecha DESC""",
        (desde, hasta),
    ).fetchall()


# --- Lectura para sincronización (local -> nube) ---------------------------

def obtener_pendientes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM gastos WHERE sincronizado = 0 ORDER BY created_at"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, gasto_id: str) -> None:
    conn.execute(
        "UPDATE gastos SET sincronizado = 1 WHERE id = ?", (gasto_id,)
    )
