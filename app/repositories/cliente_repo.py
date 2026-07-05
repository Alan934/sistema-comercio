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


def obtener(conn: sqlite3.Connection, cliente_id: str) -> Cliente | None:
    row = conn.execute(
        "SELECT id, nombre, telefono, saldo_cuenta, limite_credito "
        "FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()
    return _to_cliente(row) if row else None


def listar_activos(conn: sqlite3.Connection) -> list[Cliente]:
    rows = conn.execute(
        "SELECT id, nombre, telefono, saldo_cuenta, limite_credito FROM clientes "
        "WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [_to_cliente(r) for r in rows]


def buscar_duplicado(conn: sqlite3.Connection, nombre: str,
                     telefono: str | None = None,
                     excluir_id: str | None = None) -> Cliente | None:
    """Busca un cliente activo que colisione por nombre (sin distinguir
    mayúsculas ni espacios) o, si se provee, por teléfono igual. `excluir_id`
    deja fuera al propio cliente cuando se está editando."""
    condiciones = ["LOWER(TRIM(nombre)) = LOWER(TRIM(?))"]
    params: list[str] = [nombre]
    if telefono and telefono.strip():
        condiciones.append("TRIM(telefono) = TRIM(?)")
        params.append(telefono)
    sql = ("SELECT id, nombre, telefono, saldo_cuenta, limite_credito "
           "FROM clientes WHERE activo = 1 AND ("
           + " OR ".join(condiciones) + ")")
    if excluir_id:
        sql += " AND id != ?"
        params.append(excluir_id)
    row = conn.execute(sql + " LIMIT 1", params).fetchone()
    return _to_cliente(row) if row else None


def actualizar(conn: sqlite3.Connection, cliente_id: str, nombre: str,
               telefono: str | None, limite_credito) -> None:
    """Actualiza los datos del cliente (no toca el saldo). Marca
    `sincronizado = 0` para que el cambio suba a la nube."""
    conn.execute(
        "UPDATE clientes SET nombre = ?, telefono = ?, limite_credito = ?, "
        "sincronizado = 0, updated_at = ? WHERE id = ?",
        (nombre, telefono, str(limite_credito), ahora_iso(), cliente_id),
    )


def eliminar(conn: sqlite3.Connection, cliente_id: str) -> None:
    """Baja lógica: marca el cliente como inactivo (no borra el registro para
    conservar el historial). Marca `sincronizado = 0` para propagar la baja."""
    conn.execute(
        "UPDATE clientes SET activo = 0, sincronizado = 0, updated_at = ? "
        "WHERE id = ?", (ahora_iso(), cliente_id),
    )


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
