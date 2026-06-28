"""Acceso a datos de categorías."""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso, nuevo_id
from app.models.categoria import Categoria


def _to_categoria(row: sqlite3.Row) -> Categoria:
    return Categoria(
        id=row["id"],
        nombre=row["nombre"],
        margen_pct=(Decimal(str(row["margen_pct"]))
                    if row["margen_pct"] is not None else None),
        activo=bool(row["activo"]),
    )


def crear(conn: sqlite3.Connection, nombre: str, margen_pct) -> str:
    cid = nuevo_id()
    conn.execute(
        """INSERT INTO categorias (id, nombre, margen_pct, activo, updated_at)
           VALUES (?, ?, ?, 1, ?)""",
        (cid, nombre, str(margen_pct) if margen_pct is not None else None,
         ahora_iso()),
    )
    return cid


def actualizar(conn: sqlite3.Connection, categoria_id: str, nombre: str,
               margen_pct) -> None:
    conn.execute(
        "UPDATE categorias SET nombre = ?, margen_pct = ?, updated_at = ? WHERE id = ?",
        (nombre, str(margen_pct) if margen_pct is not None else None,
         ahora_iso(), categoria_id),
    )


def listar_activas(conn: sqlite3.Connection) -> list[Categoria]:
    rows = conn.execute(
        "SELECT id, nombre, margen_pct, activo FROM categorias "
        "WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [_to_categoria(r) for r in rows]


def obtener(conn: sqlite3.Connection, categoria_id: str) -> Categoria | None:
    row = conn.execute(
        "SELECT id, nombre, margen_pct, activo FROM categorias WHERE id = ?",
        (categoria_id,),
    ).fetchone()
    return _to_categoria(row) if row else None
