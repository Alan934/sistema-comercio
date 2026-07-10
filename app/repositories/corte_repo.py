"""Persistencia de cortes (renglones de despiece de una pieza).

Mientras la pieza está ABIERTA, sus cortes son borradores editables: se pueden
agregar, editar y borrar físicamente. Al confirmar la pieza, cada corte queda
`confirmado = 1` (ya sumó stock a su producto) y no debería modificarse.
"""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso
from app.models.corte import Corte


def _dec(valor) -> Decimal | None:
    return Decimal(str(valor)) if valor is not None else None


def _to_corte(row: sqlite3.Row) -> Corte:
    return Corte(
        id=row["id"],
        pieza_id=row["pieza_id"],
        descripcion=row["descripcion"],
        peso=Decimal(str(row["peso"])),
        precio_venta_kg=Decimal(str(row["precio_venta_kg"])),
        producto_id=row["producto_id"],
        margen_pct=_dec(row["margen_pct"]),
        costo_kg=Decimal(str(row["costo_kg"])),
        es_desperdicio=bool(row["es_desperdicio"]),
        confirmado=bool(row["confirmado"]),
    )


def crear(conn: sqlite3.Connection, corte: Corte) -> None:
    conn.execute(
        """INSERT INTO cortes
           (id, pieza_id, producto_id, descripcion, peso, precio_venta_kg,
            margen_pct, costo_kg, subtotal, es_desperdicio, confirmado,
            sincronizado, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (corte.id, corte.pieza_id, corte.producto_id, corte.descripcion,
         str(corte.peso), str(corte.precio_venta_kg),
         None if corte.margen_pct is None else str(corte.margen_pct),
         str(corte.costo_kg), str(corte.subtotal),
         1 if corte.es_desperdicio else 0, 1 if corte.confirmado else 0,
         ahora_iso()),
    )


def actualizar(conn: sqlite3.Connection, corte: Corte) -> None:
    conn.execute(
        """UPDATE cortes SET producto_id = ?, descripcion = ?, peso = ?,
           precio_venta_kg = ?, margen_pct = ?, costo_kg = ?, subtotal = ?,
           es_desperdicio = ?, confirmado = ?, sincronizado = 0, updated_at = ?
           WHERE id = ?""",
        (corte.producto_id, corte.descripcion, str(corte.peso),
         str(corte.precio_venta_kg),
         None if corte.margen_pct is None else str(corte.margen_pct),
         str(corte.costo_kg), str(corte.subtotal),
         1 if corte.es_desperdicio else 0, 1 if corte.confirmado else 0,
         ahora_iso(), corte.id),
    )


def marcar_confirmado(conn: sqlite3.Connection, corte_id: str,
                      producto_id: str, costo_kg: Decimal) -> None:
    """Al confirmar la pieza: fija el producto que recibió el stock y el
    costo/kg tomado de la res, y marca el corte como confirmado."""
    conn.execute(
        """UPDATE cortes SET producto_id = ?, costo_kg = ?, confirmado = 1,
           sincronizado = 0, updated_at = ? WHERE id = ?""",
        (producto_id, str(costo_kg), ahora_iso(), corte_id),
    )


def eliminar(conn: sqlite3.Connection, corte_id: str) -> None:
    """Borra físicamente un corte borrador (solo tiene sentido si la pieza aún
    no se confirmó; los confirmados ya cargaron stock)."""
    conn.execute("DELETE FROM cortes WHERE id = ?", (corte_id,))


def eliminar_por_pieza(conn: sqlite3.Connection, pieza_id: str) -> None:
    """Borra todos los cortes de una pieza (al eliminar una res no confirmada)."""
    conn.execute("DELETE FROM cortes WHERE pieza_id = ?", (pieza_id,))


def hay_confirmados_por_res(conn: sqlite3.Connection, res_id: str) -> bool:
    """True si algún corte de la res ya se confirmó (cargó stock). Sirve para
    impedir eliminar una res que ya movió stock."""
    row = conn.execute(
        """SELECT 1 FROM cortes c
           JOIN piezas p ON p.id = c.pieza_id
           WHERE p.res_id = ? AND c.confirmado = 1 LIMIT 1""",
        (res_id,)).fetchone()
    return row is not None


def obtener(conn: sqlite3.Connection, corte_id: str) -> Corte | None:
    row = conn.execute("SELECT * FROM cortes WHERE id = ?", (corte_id,)).fetchone()
    return _to_corte(row) if row else None


def listar_por_pieza(conn: sqlite3.Connection, pieza_id: str) -> list[Corte]:
    rows = conn.execute(
        "SELECT * FROM cortes WHERE pieza_id = ? ORDER BY updated_at", (pieza_id,)
    ).fetchall()
    return [_to_corte(r) for r in rows]


# --- Lectura para sincronización (local -> nube) ---------------------------

def obtener_pendientes_sync_confirmados(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Solo cortes ya confirmados: los borradores no se suben (se pueden borrar,
    y no queremos dejarlos huérfanos en la nube)."""
    return conn.execute(
        "SELECT * FROM cortes WHERE sincronizado = 0 AND confirmado = 1"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, corte_id: str) -> None:
    conn.execute("UPDATE cortes SET sincronizado = 1 WHERE id = ?", (corte_id,))


def _ts(v) -> str:
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Baja un corte de Neon (solo hay confirmados). Gana lo local si hay
    cambios sin subir."""
    actual = conn.execute(
        "SELECT sincronizado FROM cortes WHERE id = ?", (fila["id"],)
    ).fetchone()
    if actual is not None and actual["sincronizado"] == 0:
        return
    margen = str(fila["margen_pct"]) if fila.get("margen_pct") is not None else None
    vals = (fila["pieza_id"], fila["producto_id"], fila["descripcion"],
            str(fila["peso"]), str(fila["precio_venta_kg"]), margen,
            str(fila["costo_kg"]), str(fila["subtotal"]),
            1 if fila["es_desperdicio"] else 0, 1 if fila["confirmado"] else 0,
            _ts(fila["updated_at"]))
    if actual is not None:
        conn.execute(
            """UPDATE cortes SET pieza_id=?, producto_id=?, descripcion=?, peso=?,
               precio_venta_kg=?, margen_pct=?, costo_kg=?, subtotal=?,
               es_desperdicio=?, confirmado=?, updated_at=?, sincronizado=1
               WHERE id=?""", vals + (fila["id"],))
    else:
        conn.execute(
            """INSERT INTO cortes (pieza_id, producto_id, descripcion, peso,
               precio_venta_kg, margen_pct, costo_kg, subtotal, es_desperdicio,
               confirmado, updated_at, sincronizado, id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)""", vals + (fila["id"],))
