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
        """SELECT l.id, l.producto_id, l.fecha_vencimiento, l.cantidad,
                  p.nombre AS producto_nombre
           FROM lotes l
           JOIN productos p ON p.id = l.producto_id
           WHERE l.activo = 1 AND l.cantidad > 0
             AND l.fecha_vencimiento IS NOT NULL
             AND l.fecha_vencimiento <= ?
           ORDER BY l.fecha_vencimiento""",
        (limite,),
    ).fetchall()


def listar_activos(conn: sqlite3.Connection, producto_id: str) -> list[sqlite3.Row]:
    """Todos los lotes activos de un producto, del que vence antes al que vence
    después (los sin fecha, al final)."""
    return conn.execute(
        """SELECT id, fecha_vencimiento, cantidad FROM lotes
           WHERE producto_id = ? AND activo = 1
           ORDER BY fecha_vencimiento IS NULL, fecha_vencimiento""",
        (producto_id,),
    ).fetchall()


def eliminar(conn: sqlite3.Connection, lote_id: str) -> None:
    """Borrado lógico de un lote (activo = 0)."""
    conn.execute(
        "UPDATE lotes SET activo = 0, updated_at = ? WHERE id = ?",
        (ahora_iso(), lote_id),
    )


def ultimo_activo(conn: sqlite3.Connection, producto_id: str) -> sqlite3.Row | None:
    """Lote activo con vencimiento más próximo (para precargar la edición)."""
    return conn.execute(
        """SELECT id, fecha_vencimiento, cantidad FROM lotes
           WHERE producto_id = ? AND activo = 1
             AND fecha_vencimiento IS NOT NULL
           ORDER BY fecha_vencimiento LIMIT 1""",
        (producto_id,),
    ).fetchone()


def actualizar_fecha(conn: sqlite3.Connection, lote_id: str,
                     fecha_vencimiento: str) -> None:
    conn.execute(
        "UPDATE lotes SET fecha_vencimiento = ?, updated_at = ? WHERE id = ?",
        (fecha_vencimiento, ahora_iso(), lote_id),
    )
