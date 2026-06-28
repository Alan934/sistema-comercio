"""Persistencia de ventas: cabecera + detalle + pagos.

Recibe la conexión para escribir todo dentro de la MISMA transacción que el
descuento de stock y la cuenta corriente (lo orquesta venta_service)."""
import sqlite3

from app.core.utils import nuevo_id
from app.models.carrito import ItemCarrito
from app.models.venta import Venta, Pago


def guardar(conn: sqlite3.Connection, venta: Venta,
            items: list[ItemCarrito], pagos: list[Pago]) -> None:
    conn.execute(
        """INSERT INTO ventas
           (id, fecha, cliente_id, subtotal, descuento, total, costo_total,
            estado, sincronizado, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (venta.id, venta.fecha, venta.cliente_id, str(venta.subtotal),
         str(venta.descuento), str(venta.total), str(venta.costo_total),
         venta.estado, venta.created_at, venta.updated_at),
    )

    for it in items:
        conn.execute(
            """INSERT INTO ventas_detalle
               (id, venta_id, producto_id, descripcion, cantidad,
                precio_unitario, costo_unitario, subtotal)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (nuevo_id(), venta.id, it.producto_id, it.descripcion,
             str(it.cantidad), str(it.precio_unitario),
             str(it.costo_unitario), str(it.subtotal)),
        )

    for p in pagos:
        conn.execute(
            "INSERT INTO pagos_venta (id, venta_id, metodo, monto) VALUES (?, ?, ?, ?)",
            (nuevo_id(), venta.id, p.metodo, str(p.monto)),
        )


def contar_pendientes_sync(conn: sqlite3.Connection) -> int:
    """Cuántas ventas están sin subir a la nube (para el futuro sync_manager)."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM ventas WHERE sincronizado = 0"
    ).fetchone()
    return row["n"]
