"""Persistencia de piezas (Espalda, Pierna, ... de una res)."""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso
from app.models.pieza import Pieza


def _dec(valor) -> Decimal | None:
    return Decimal(str(valor)) if valor is not None else None


def _to_pieza(row: sqlite3.Row) -> Pieza:
    return Pieza(
        id=row["id"],
        res_id=row["res_id"],
        nombre=row["nombre"],
        fecha=row["fecha"],
        peso=Decimal(str(row["peso"])),
        estado=row["estado"],
        margen_pct=_dec(row["margen_pct"]),
    )


def crear(conn: sqlite3.Connection, pieza: Pieza) -> None:
    conn.execute(
        """INSERT INTO piezas
           (id, res_id, nombre, fecha, peso, margen_pct, estado,
            sincronizado, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (pieza.id, pieza.res_id, pieza.nombre, pieza.fecha, str(pieza.peso),
         None if pieza.margen_pct is None else str(pieza.margen_pct),
         pieza.estado, ahora_iso()),
    )


def actualizar(conn: sqlite3.Connection, pieza: Pieza) -> None:
    conn.execute(
        """UPDATE piezas SET nombre = ?, fecha = ?, peso = ?, margen_pct = ?,
           estado = ?, sincronizado = 0, updated_at = ? WHERE id = ?""",
        (pieza.nombre, pieza.fecha, str(pieza.peso),
         None if pieza.margen_pct is None else str(pieza.margen_pct),
         pieza.estado, ahora_iso(), pieza.id),
    )


def actualizar_peso(conn: sqlite3.Connection, pieza_id: str, peso: Decimal) -> None:
    """Refresca el peso de la pieza (suma de los kg de sus cortes)."""
    conn.execute(
        "UPDATE piezas SET peso = ?, sincronizado = 0, updated_at = ? WHERE id = ?",
        (str(peso), ahora_iso(), pieza_id),
    )


def cambiar_estado(conn: sqlite3.Connection, pieza_id: str, estado: str) -> None:
    conn.execute(
        "UPDATE piezas SET estado = ?, sincronizado = 0, updated_at = ? WHERE id = ?",
        (estado, ahora_iso(), pieza_id),
    )


def eliminar_por_res(conn: sqlite3.Connection, res_id: str) -> None:
    """Borra todas las piezas de una res (al eliminar una res no confirmada).
    Los cortes de cada pieza se borran aparte antes de esto."""
    conn.execute("DELETE FROM piezas WHERE res_id = ?", (res_id,))


def obtener(conn: sqlite3.Connection, pieza_id: str) -> Pieza | None:
    row = conn.execute("SELECT * FROM piezas WHERE id = ?", (pieza_id,)).fetchone()
    return _to_pieza(row) if row else None


def listar_por_res(conn: sqlite3.Connection, res_id: str) -> list[Pieza]:
    rows = conn.execute(
        "SELECT * FROM piezas WHERE res_id = ? ORDER BY fecha", (res_id,)
    ).fetchall()
    return [_to_pieza(r) for r in rows]


# --- Lectura para sincronización (local -> nube) ---------------------------

def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM piezas WHERE sincronizado = 0"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, pieza_id: str) -> None:
    conn.execute("UPDATE piezas SET sincronizado = 1 WHERE id = ?", (pieza_id,))


def _ts(v) -> str:
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Baja una pieza de Neon (gana lo local si hay cambios sin subir)."""
    actual = conn.execute(
        "SELECT sincronizado FROM piezas WHERE id = ?", (fila["id"],)
    ).fetchone()
    if actual is not None and actual["sincronizado"] == 0:
        return
    margen = str(fila["margen_pct"]) if fila.get("margen_pct") is not None else None
    vals = (fila["res_id"], fila["nombre"], _ts(fila["fecha"]),
            str(fila["peso"]), margen, fila["estado"], _ts(fila["updated_at"]))
    if actual is not None:
        conn.execute(
            """UPDATE piezas SET res_id=?, nombre=?, fecha=?, peso=?, margen_pct=?,
               estado=?, updated_at=?, sincronizado=1 WHERE id=?""",
            vals + (fila["id"],))
    else:
        conn.execute(
            """INSERT INTO piezas (res_id, nombre, fecha, peso, margen_pct, estado,
               updated_at, sincronizado, id) VALUES (?,?,?,?,?,?,?,1,?)""",
            vals + (fila["id"],))
