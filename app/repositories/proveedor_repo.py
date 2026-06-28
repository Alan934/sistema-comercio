"""Acceso a datos de proveedores."""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso
from app.models.proveedor import Proveedor


def _to_proveedor(row: sqlite3.Row) -> Proveedor:
    return Proveedor(
        id=row["id"],
        nombre=row["nombre"],
        cuit=row["cuit"],
        telefono=row["telefono"],
        saldo_cuenta=Decimal(str(row["saldo_cuenta"])),
        activo=bool(row["activo"]),
    )


def crear(conn: sqlite3.Connection, proveedor: Proveedor) -> None:
    conn.execute(
        """INSERT INTO proveedores
           (id, nombre, cuit, telefono, saldo_cuenta, activo, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (proveedor.id, proveedor.nombre, proveedor.cuit, proveedor.telefono,
         str(proveedor.saldo_cuenta), 1 if proveedor.activo else 0, ahora_iso()),
    )


def obtener(conn: sqlite3.Connection, proveedor_id: str) -> Proveedor | None:
    row = conn.execute(
        "SELECT id, nombre, cuit, telefono, saldo_cuenta, activo "
        "FROM proveedores WHERE id = ?", (proveedor_id,)
    ).fetchone()
    return _to_proveedor(row) if row else None


def listar_activos(conn: sqlite3.Connection) -> list[Proveedor]:
    rows = conn.execute(
        "SELECT id, nombre, cuit, telefono, saldo_cuenta, activo "
        "FROM proveedores WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [_to_proveedor(r) for r in rows]
