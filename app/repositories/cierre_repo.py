"""Acceso a datos de cierres de caja (arqueo).

El período de un cierre va desde el cierre anterior (su fecha) hasta ahora.
Las fechas son ISO locales con offset, así que comparar con `fecha > ?` como
texto funciona (mismo formato/zona)."""
import sqlite3


def ultimo(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM cierres_caja ORDER BY fecha DESC LIMIT 1"
    ).fetchone()


def resumen_desde(conn: sqlite3.Connection, desde_ts: str) -> dict:
    """Totales de ventas (por método) y gastos desde `desde_ts` (exclusivo).
    Si desde_ts es '' toma todo desde el inicio."""
    v = conn.execute(
        """SELECT COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total
           FROM ventas WHERE estado = 'COMPLETADA' AND fecha > ?""",
        (desde_ts,),
    ).fetchone()

    metodos = {row["metodo"]: row["total"] for row in conn.execute(
        """SELECT pv.metodo, COALESCE(SUM(pv.monto), 0) AS total
           FROM pagos_venta pv JOIN ventas v ON v.id = pv.venta_id
           WHERE v.estado = 'COMPLETADA' AND v.fecha > ?
           GROUP BY pv.metodo""",
        (desde_ts,),
    ).fetchall()}

    gastos = conn.execute(
        "SELECT COALESCE(SUM(monto), 0) AS total FROM gastos WHERE fecha > ?",
        (desde_ts,),
    ).fetchone()["total"]
    # Solo los gastos pagados en efectivo salen de la caja (NULL = viejos, se
    # asumen efectivo por compatibilidad).
    gastos_efectivo = conn.execute(
        """SELECT COALESCE(SUM(monto), 0) AS total FROM gastos
           WHERE fecha > ? AND (metodo = 'EFECTIVO' OR metodo IS NULL)""",
        (desde_ts,),
    ).fetchone()["total"]

    # Cobros de fiado en efectivo (entra plata a la caja) y pagos a proveedores
    # en efectivo (sale plata de la caja). Solo movimientos de tipo PAGO.
    cobros = conn.execute(
        """SELECT COALESCE(SUM(monto), 0) AS total FROM cuenta_movimientos
           WHERE entidad_tipo = 'CLIENTE' AND tipo = 'HABER'
             AND referencia_tipo = 'PAGO' AND metodo = 'EFECTIVO' AND fecha > ?""",
        (desde_ts,),
    ).fetchone()["total"]
    pagos = conn.execute(
        """SELECT COALESCE(SUM(monto), 0) AS total FROM cuenta_movimientos
           WHERE entidad_tipo = 'PROVEEDOR' AND tipo = 'HABER'
             AND referencia_tipo = 'PAGO' AND metodo = 'EFECTIVO' AND fecha > ?""",
        (desde_ts,),
    ).fetchone()["total"]

    return {
        "ventas_cantidad": v["cantidad"],
        "total_vendido": v["total"],
        "efectivo": metodos.get("EFECTIVO", 0),
        "transferencia": metodos.get("TRANSFERENCIA", 0),
        "tarjeta": metodos.get("TARJETA", 0),
        "fiado": metodos.get("FIADO", 0),
        "cobros_efectivo": cobros,
        "pagos_efectivo": pagos,
        "gastos": gastos,
        "gastos_efectivo": gastos_efectivo,
    }


def crear(conn: sqlite3.Connection, c: dict) -> None:
    conn.execute(
        """INSERT INTO cierres_caja
           (id, fecha, desde, usuario_id, usuario_nombre, ventas_cantidad,
            total_vendido, efectivo_ventas, transferencia_ventas, tarjeta_ventas,
            fiado_ventas, cobros_efectivo, pagos_efectivo, gastos_total, fondo,
            efectivo_esperado, efectivo_contado, diferencia, nota, sincronizado,
            created_at)
           VALUES (:id, :fecha, :desde, :usuario_id, :usuario_nombre,
                   :ventas_cantidad, :total_vendido, :efectivo_ventas,
                   :transferencia_ventas, :tarjeta_ventas, :fiado_ventas,
                   :cobros_efectivo, :pagos_efectivo, :gastos_total, :fondo,
                   :efectivo_esperado, :efectivo_contado, :diferencia, :nota, 0,
                   :created_at)""",
        c,
    )


def listar(conn: sqlite3.Connection, limite: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM cierres_caja ORDER BY fecha DESC LIMIT ?", (limite,)
    ).fetchall()


# --- Sincronización ---------------------------------------------------------

def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM cierres_caja WHERE sincronizado = 0 ORDER BY created_at"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, cierre_id: str) -> None:
    conn.execute(
        "UPDATE cierres_caja SET sincronizado = 1 WHERE id = ?", (cierre_id,)
    )


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Los cierres son inmutables: si no existe localmente, se inserta."""
    existe = conn.execute(
        "SELECT 1 FROM cierres_caja WHERE id = ?", (fila["id"],)
    ).fetchone()
    if existe:
        return

    def _ts(v):
        return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v else None)

    conn.execute(
        """INSERT INTO cierres_caja
           (id, fecha, desde, usuario_id, usuario_nombre, ventas_cantidad,
            total_vendido, efectivo_ventas, transferencia_ventas, tarjeta_ventas,
            fiado_ventas, cobros_efectivo, pagos_efectivo, gastos_total, fondo,
            efectivo_esperado, efectivo_contado, diferencia, nota, sincronizado,
            created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
        (fila["id"], _ts(fila["fecha"]), _ts(fila["desde"]), fila["usuario_id"],
         fila["usuario_nombre"], fila["ventas_cantidad"], str(fila["total_vendido"]),
         str(fila["efectivo_ventas"]), str(fila["transferencia_ventas"]),
         str(fila["tarjeta_ventas"]), str(fila["fiado_ventas"]),
         str(fila.get("cobros_efectivo", 0)), str(fila.get("pagos_efectivo", 0)),
         str(fila["gastos_total"]), str(fila["fondo"]),
         str(fila["efectivo_esperado"]), str(fila["efectivo_contado"]),
         str(fila["diferencia"]), fila["nota"], _ts(fila["created_at"])),
    )
