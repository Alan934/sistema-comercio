"""Persistencia de compras/remitos: cabecera + detalle.
Recibe la conexión para participar de la transacción que arma compra_service
(que además actualiza costos, stock, lotes y cuenta corriente)."""
import sqlite3

from app.core.utils import nuevo_id
from app.models.compra import Compra, ItemCompra


def guardar(conn: sqlite3.Connection, compra: Compra,
            items: list[ItemCompra]) -> None:
    conn.execute(
        """INSERT INTO compras
           (id, proveedor_id, fecha, nro_remito, total, condicion,
            sincronizado, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (compra.id, compra.proveedor_id, compra.fecha, compra.nro_remito,
         str(compra.total), compra.condicion, compra.created_at, compra.updated_at),
    )
    for it in items:
        conn.execute(
            """INSERT INTO compras_detalle
               (id, compra_id, producto_id, cantidad, costo_unitario, subtotal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (nuevo_id(), compra.id, it.producto_id, str(it.cantidad),
             str(it.costo_unitario), str(it.subtotal)),
        )


# --- Lectura para sincronización (local -> nube) ---------------------------

def obtener_pendientes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM compras WHERE sincronizado = 0 ORDER BY created_at"
    ).fetchall()


def obtener_detalle(conn: sqlite3.Connection, compra_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM compras_detalle WHERE compra_id = ?", (compra_id,)
    ).fetchall()


def marcar_sincronizada(conn: sqlite3.Connection, compra_id: str) -> None:
    conn.execute(
        "UPDATE compras SET sincronizado = 1 WHERE id = ?", (compra_id,)
    )
