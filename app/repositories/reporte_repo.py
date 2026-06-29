"""Consultas de agregación para reportes.

Todas filtran por la parte AAAA-MM-DD de la fecha (substr) para no enredarse
con la hora ni la zona horaria. Las ventas anuladas se excluyen siempre.
"""
import sqlite3


def resumen_ventas(conn: sqlite3.Connection, desde: str, hasta: str) -> sqlite3.Row:
    """Cantidad de ventas, total vendido y costo total (para la ganancia)."""
    return conn.execute(
        """SELECT COUNT(*)                 AS cantidad,
                  COALESCE(SUM(total), 0)       AS total_vendido,
                  COALESCE(SUM(costo_total), 0) AS costo_total
           FROM ventas
           WHERE estado = 'COMPLETADA'
             AND substr(fecha, 1, 10) BETWEEN ? AND ?""",
        (desde, hasta),
    ).fetchone()


def total_gastos(conn: sqlite3.Connection, desde: str, hasta: str):
    row = conn.execute(
        """SELECT COALESCE(SUM(monto), 0) AS total FROM gastos
           WHERE substr(fecha, 1, 10) BETWEEN ? AND ?""",
        (desde, hasta),
    ).fetchone()
    return row["total"]


def gastos_por_tipo(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT tipo, COALESCE(SUM(monto), 0) AS total FROM gastos
           WHERE substr(fecha, 1, 10) BETWEEN ? AND ?
           GROUP BY tipo ORDER BY total DESC""",
        (desde, hasta),
    ).fetchall()


def ventas_por_metodo(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT pv.metodo, COALESCE(SUM(pv.monto), 0) AS total
           FROM pagos_venta pv
           JOIN ventas v ON v.id = pv.venta_id
           WHERE v.estado = 'COMPLETADA'
             AND substr(v.fecha, 1, 10) BETWEEN ? AND ?
           GROUP BY pv.metodo ORDER BY total DESC""",
        (desde, hasta),
    ).fetchall()


def unidades_vendidas(conn: sqlite3.Connection, desde: str, hasta: str):
    row = conn.execute(
        """SELECT COALESCE(SUM(vd.cantidad), 0) AS u
           FROM ventas_detalle vd JOIN ventas v ON v.id = vd.venta_id
           WHERE v.estado = 'COMPLETADA'
             AND substr(v.fecha, 1, 10) BETWEEN ? AND ?""",
        (desde, hasta),
    ).fetchone()
    return row["u"]


def top_productos(conn: sqlite3.Connection, desde: str, hasta: str,
                  limite: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT vd.descripcion,
                  COALESCE(SUM(vd.cantidad), 0) AS cantidad,
                  COALESCE(SUM(vd.subtotal), 0) AS total,
                  COALESCE(SUM(vd.subtotal - vd.costo_unitario * vd.cantidad), 0)
                      AS ganancia
           FROM ventas_detalle vd
           JOIN ventas v ON v.id = vd.venta_id
           WHERE v.estado = 'COMPLETADA'
             AND substr(v.fecha, 1, 10) BETWEEN ? AND ?
           GROUP BY vd.descripcion ORDER BY total DESC LIMIT ?""",
        (desde, hasta, limite),
    ).fetchall()


def por_categoria(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT COALESCE(c.nombre, 'Sin categoría') AS categoria,
                  COALESCE(SUM(vd.subtotal), 0) AS ventas,
                  COALESCE(SUM(vd.subtotal - vd.costo_unitario * vd.cantidad), 0)
                      AS ganancia
           FROM ventas_detalle vd
           JOIN ventas v ON v.id = vd.venta_id
           LEFT JOIN productos p ON p.id = vd.producto_id
           LEFT JOIN categorias c ON c.id = p.categoria_id
           WHERE v.estado = 'COMPLETADA'
             AND substr(v.fecha, 1, 10) BETWEEN ? AND ?
           GROUP BY categoria ORDER BY ventas DESC""",
        (desde, hasta),
    ).fetchall()


def ranking_proveedores(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT p.nombre,
                  COALESCE(SUM(c.total), 0) AS comprado,
                  COUNT(c.id) AS remitos,
                  p.saldo_cuenta AS deuda
           FROM proveedores p
           LEFT JOIN compras c ON c.proveedor_id = p.id
                AND substr(c.fecha, 1, 10) BETWEEN ? AND ?
           WHERE p.activo = 1
           GROUP BY p.id, p.nombre, p.saldo_cuenta
           HAVING COALESCE(SUM(c.total), 0) > 0 OR p.saldo_cuenta <> 0
           ORDER BY comprado DESC""",
        (desde, hasta),
    ).fetchall()


def compras_por_proveedor(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT p.nombre, COALESCE(SUM(c.total), 0) AS total
           FROM compras c
           JOIN proveedores p ON p.id = c.proveedor_id
           WHERE substr(c.fecha, 1, 10) BETWEEN ? AND ?
           GROUP BY p.id, p.nombre ORDER BY total DESC""",
        (desde, hasta),
    ).fetchall()


def gastos_por_proveedor(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT p.nombre, COALESCE(SUM(g.monto), 0) AS total
           FROM gastos g
           JOIN proveedores p ON p.id = g.proveedor_id
           WHERE substr(g.fecha, 1, 10) BETWEEN ? AND ?
           GROUP BY p.id, p.nombre ORDER BY total DESC""",
        (desde, hasta),
    ).fetchall()


def ventas_por_dia(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT substr(fecha, 1, 10) AS dia, COALESCE(SUM(total), 0) AS total
           FROM ventas
           WHERE estado = 'COMPLETADA' AND substr(fecha, 1, 10) BETWEEN ? AND ?
           GROUP BY dia ORDER BY dia""",
        (desde, hasta),
    ).fetchall()


def ventas_por_mes(conn: sqlite3.Connection, desde: str, hasta: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT substr(fecha, 1, 7) AS mes, COALESCE(SUM(total), 0) AS total
           FROM ventas
           WHERE estado = 'COMPLETADA' AND substr(fecha, 1, 10) BETWEEN ? AND ?
           GROUP BY mes ORDER BY mes""",
        (desde, hasta),
    ).fetchall()
