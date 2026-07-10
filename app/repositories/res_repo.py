"""Persistencia de reses (cabecera del despiece).

Recibe la conexión para poder participar de la transacción que arma
despiece_service (crear la res + sumar deuda al proveedor si es a cuenta
corriente). El dinero y los pesos se guardan como str(Decimal) y se leen con
Decimal(str(...)) para no perder precisión (misma convención que el resto).
"""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso
from app.models.res import Res


def _dec(valor) -> Decimal | None:
    return Decimal(str(valor)) if valor is not None else None


def _to_res(row: sqlite3.Row) -> Res:
    return Res(
        id=row["id"],
        proveedor_id=row["proveedor_id"],
        fecha=row["fecha"],
        descripcion=row["descripcion"],
        peso_total=Decimal(str(row["peso_total"])),
        costo_por_kg=Decimal(str(row["costo_por_kg"])),
        costo_total=Decimal(str(row["costo_total"])),
        condicion=row["condicion"],
        estado=row["estado"],
        margen_pct=_dec(row["margen_pct"]),
    )


def crear(conn: sqlite3.Connection, res: Res) -> None:
    ahora = ahora_iso()
    conn.execute(
        """INSERT INTO reses
           (id, proveedor_id, fecha, descripcion, peso_total, costo_por_kg,
            costo_total, margen_pct, condicion, estado, sincronizado,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (res.id, res.proveedor_id, res.fecha, res.descripcion,
         str(res.peso_total), str(res.costo_por_kg), str(res.costo_total),
         None if res.margen_pct is None else str(res.margen_pct),
         res.condicion, res.estado, ahora, ahora),
    )


def actualizar(conn: sqlite3.Connection, res: Res) -> None:
    conn.execute(
        """UPDATE reses SET proveedor_id = ?, fecha = ?, descripcion = ?,
           peso_total = ?, costo_por_kg = ?, costo_total = ?, margen_pct = ?,
           condicion = ?, estado = ?, sincronizado = 0, updated_at = ?
           WHERE id = ?""",
        (res.proveedor_id, res.fecha, res.descripcion, str(res.peso_total),
         str(res.costo_por_kg), str(res.costo_total),
         None if res.margen_pct is None else str(res.margen_pct),
         res.condicion, res.estado, ahora_iso(), res.id),
    )


def cambiar_estado(conn: sqlite3.Connection, res_id: str, estado: str) -> None:
    conn.execute(
        "UPDATE reses SET estado = ?, sincronizado = 0, updated_at = ? WHERE id = ?",
        (estado, ahora_iso(), res_id),
    )


def eliminar(conn: sqlite3.Connection, res_id: str) -> None:
    """Borra físicamente la cabecera de la res. Las piezas y cortes se borran
    aparte (antes) para no dejar huérfanos."""
    conn.execute("DELETE FROM reses WHERE id = ?", (res_id,))


def obtener(conn: sqlite3.Connection, res_id: str) -> Res | None:
    row = conn.execute("SELECT * FROM reses WHERE id = ?", (res_id,)).fetchone()
    return _to_res(row) if row else None


def listar(conn: sqlite3.Connection, solo_abiertas: bool = False) -> list[Res]:
    sql = "SELECT * FROM reses"
    if solo_abiertas:
        sql += " WHERE estado = 'ABIERTA'"
    sql += " ORDER BY fecha DESC"
    return [_to_res(r) for r in conn.execute(sql).fetchall()]


# --- Lectura para sincronización (local -> nube) ---------------------------

def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM reses WHERE sincronizado = 0 ORDER BY created_at"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, res_id: str) -> None:
    conn.execute("UPDATE reses SET sincronizado = 1 WHERE id = ?", (res_id,))


def _ts(v) -> str:
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _txt_null(v):
    return str(v) if v is not None else None


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Baja una res de Neon. Si hay cambios locales sin subir (sincronizado=0),
    gana lo local; si no, inserta/actualiza y la marca sincronizada."""
    actual = conn.execute(
        "SELECT sincronizado FROM reses WHERE id = ?", (fila["id"],)
    ).fetchone()
    if actual is not None and actual["sincronizado"] == 0:
        return
    vals = (fila["proveedor_id"], _ts(fila["fecha"]), fila["descripcion"],
            str(fila["peso_total"]), str(fila["costo_por_kg"]),
            str(fila["costo_total"]), _txt_null(fila.get("margen_pct")),
            fila["condicion"], fila["estado"], _ts(fila["created_at"]),
            _ts(fila["updated_at"]))
    if actual is not None:
        conn.execute(
            """UPDATE reses SET proveedor_id=?, fecha=?, descripcion=?,
               peso_total=?, costo_por_kg=?, costo_total=?, margen_pct=?,
               condicion=?, estado=?, created_at=?, updated_at=?, sincronizado=1
               WHERE id=?""", vals + (fila["id"],))
    else:
        conn.execute(
            """INSERT INTO reses (proveedor_id, fecha, descripcion, peso_total,
               costo_por_kg, costo_total, margen_pct, condicion, estado,
               created_at, updated_at, sincronizado, id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)""", vals + (fila["id"],))
