"""Acceso a datos de lotes (control de vencimientos de perecederos)."""
import sqlite3
from datetime import date, timedelta

from app.core.utils import ahora_iso, nuevo_id


def crear(conn: sqlite3.Connection, producto_id: str, fecha_vencimiento: str,
          cantidad, compra_id: str | None = None) -> None:
    conn.execute(
        """INSERT INTO lotes
           (id, producto_id, fecha_vencimiento, cantidad, compra_id, activo, updated_at)
           VALUES (?, ?, ?, ?, ?, 1, ?)""",
        (nuevo_id(), producto_id, fecha_vencimiento, str(cantidad),
         compra_id, ahora_iso()),
    )


def proximos_a_vencer(conn: sqlite3.Connection, dias: int = 7) -> list[sqlite3.Row]:
    """Lotes con stock que vencen dentro de `dias` (incluye ya vencidos).
    Las fechas son ISO (YYYY-MM-DD), así que comparar como texto es correcto."""
    limite = (date.today() + timedelta(days=dias)).isoformat()
    return conn.execute(
        """SELECT l.id, l.fecha_vencimiento, l.cantidad,
                  p.nombre AS producto_nombre
           FROM lotes l
           JOIN productos p ON p.id = l.producto_id
           WHERE l.activo = 1 AND l.cantidad > 0
             AND l.fecha_vencimiento IS NOT NULL
             AND l.fecha_vencimiento <= ?
           ORDER BY l.fecha_vencimiento""",
        (limite,),
    ).fetchall()
