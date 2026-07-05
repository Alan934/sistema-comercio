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
        "UPDATE categorias SET nombre = ?, margen_pct = ?, sincronizado = 0, "
        "updated_at = ? WHERE id = ?",
        (nombre, str(margen_pct) if margen_pct is not None else None,
         ahora_iso(), categoria_id),
    )


# --- Sincronización del catálogo (local <-> nube) --------------------------

def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM categorias WHERE sincronizado = 0"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, categoria_id: str) -> None:
    conn.execute(
        "UPDATE categorias SET sincronizado = 1 WHERE id = ?", (categoria_id,)
    )


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Aplica una categoría traída de Neon, salvo que haya cambios locales sin
    subir (sincronizado=0), en cuyo caso gana lo local."""
    actual = conn.execute(
        "SELECT sincronizado FROM categorias WHERE id = ?", (fila["id"],)
    ).fetchone()
    if actual is not None and actual["sincronizado"] == 0:
        return
    margen = str(fila["margen_pct"]) if fila["margen_pct"] is not None else None
    updated = (fila["updated_at"].isoformat()
               if hasattr(fila["updated_at"], "isoformat") else str(fila["updated_at"]))
    if actual is not None:
        conn.execute(
            "UPDATE categorias SET nombre = ?, margen_pct = ?, activo = ?, "
            "sincronizado = 1, updated_at = ? WHERE id = ?",
            (fila["nombre"], margen, 1 if fila["activo"] else 0, updated, fila["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO categorias (id, nombre, margen_pct, activo, sincronizado, "
            "updated_at) VALUES (?, ?, ?, ?, 1, ?)",
            (fila["id"], fila["nombre"], margen, 1 if fila["activo"] else 0, updated),
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
