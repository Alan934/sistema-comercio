"""Acceso a datos de clientes."""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso
from app.models.cliente import Cliente


def _to_cliente(row: sqlite3.Row) -> Cliente:
    return Cliente(
        id=row["id"],
        nombre=row["nombre"],
        saldo_cuenta=Decimal(str(row["saldo_cuenta"])),
        limite_credito=Decimal(str(row["limite_credito"])),
        telefono=row["telefono"],
    )


def crear(conn: sqlite3.Connection, cliente_id: str, nombre: str,
          telefono: str | None, limite_credito) -> None:
    conn.execute(
        """INSERT INTO clientes
           (id, nombre, telefono, limite_credito, saldo_cuenta, activo,
            sincronizado, updated_at)
           VALUES (?, ?, ?, ?, '0.00', 1, 0, ?)""",
        (cliente_id, nombre, telefono, str(limite_credito), ahora_iso()),
    )


def listar_activos(conn: sqlite3.Connection) -> list[Cliente]:
    rows = conn.execute(
        "SELECT id, nombre, telefono, saldo_cuenta, limite_credito FROM clientes "
        "WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [_to_cliente(r) for r in rows]


# --- Lectura para sincronización del catálogo (local -> nube) --------------

def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM clientes WHERE sincronizado = 0"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, cliente_id: str) -> None:
    conn.execute(
        "UPDATE clientes SET sincronizado = 1 WHERE id = ?", (cliente_id,)
    )


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Baja un cliente de Neon. Conserva el saldo_cuenta local (lo mueven los
    fiados de esta PC); para uno nuevo, lo trae completo. No pisa si hay cambios
    locales sin subir."""
    actual = conn.execute(
        "SELECT sincronizado FROM clientes WHERE id = ?", (fila["id"],)
    ).fetchone()
    if actual is not None and actual["sincronizado"] == 0:
        return
    updated = (fila["updated_at"].isoformat()
               if hasattr(fila["updated_at"], "isoformat") else str(fila["updated_at"]))
    if actual is not None:
        conn.execute(
            "UPDATE clientes SET nombre = ?, telefono = ?, limite_credito = ?, "
            "activo = ?, sincronizado = 1, updated_at = ? WHERE id = ?",
            (fila["nombre"], fila["telefono"], str(fila["limite_credito"]),
             1 if fila["activo"] else 0, updated, fila["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO clientes (id, nombre, telefono, limite_credito, "
            "saldo_cuenta, activo, sincronizado, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (fila["id"], fila["nombre"], fila["telefono"],
             str(fila["limite_credito"]), str(fila["saldo_cuenta"]),
             1 if fila["activo"] else 0, updated),
        )
