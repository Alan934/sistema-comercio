"""Acceso a datos de clientes."""
import sqlite3
from decimal import Decimal

from app.models.cliente import Cliente


def _to_cliente(row: sqlite3.Row) -> Cliente:
    return Cliente(
        id=row["id"],
        nombre=row["nombre"],
        saldo_cuenta=Decimal(str(row["saldo_cuenta"])),
        limite_credito=Decimal(str(row["limite_credito"])),
    )


def listar_activos(conn: sqlite3.Connection) -> list[Cliente]:
    rows = conn.execute(
        "SELECT id, nombre, saldo_cuenta, limite_credito FROM clientes "
        "WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [_to_cliente(r) for r in rows]
