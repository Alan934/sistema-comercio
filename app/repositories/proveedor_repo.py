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
        email=row["email"],
    )


def crear(conn: sqlite3.Connection, proveedor: Proveedor) -> None:
    conn.execute(
        """INSERT INTO proveedores
           (id, nombre, cuit, telefono, email, saldo_cuenta, activo, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (proveedor.id, proveedor.nombre, proveedor.cuit, proveedor.telefono,
         proveedor.email, str(proveedor.saldo_cuenta),
         1 if proveedor.activo else 0, ahora_iso()),
    )


def buscar_duplicado(conn: sqlite3.Connection, nombre: str,
                     cuit: str | None = None,
                     telefono: str | None = None,
                     excluir_id: str | None = None) -> Proveedor | None:
    """Busca un proveedor activo que colisione con los datos dados.

    Coincide por nombre (sin distinguir mayúsculas ni espacios) o, si se
    proveen, por CUIT o teléfono iguales. Sirve para evitar altas duplicadas.
    `excluir_id` deja fuera al propio proveedor cuando se está editando.
    """
    condiciones = ["LOWER(TRIM(nombre)) = LOWER(TRIM(?))"]
    params: list[str] = [nombre]
    if cuit and cuit.strip():
        condiciones.append("TRIM(cuit) = TRIM(?)")
        params.append(cuit)
    if telefono and telefono.strip():
        condiciones.append("TRIM(telefono) = TRIM(?)")
        params.append(telefono)
    sql = ("SELECT id, nombre, cuit, telefono, email, saldo_cuenta, activo "
           "FROM proveedores WHERE activo = 1 AND ("
           + " OR ".join(condiciones) + ")")
    if excluir_id:
        sql += " AND id != ?"
        params.append(excluir_id)
    row = conn.execute(sql + " LIMIT 1", params).fetchone()
    return _to_proveedor(row) if row else None


def actualizar(conn: sqlite3.Connection, proveedor: Proveedor) -> None:
    """Actualiza los datos de contacto del proveedor (no toca el saldo).

    Marca `sincronizado = 0` para que el cambio suba a la nube."""
    conn.execute(
        "UPDATE proveedores SET nombre = ?, cuit = ?, telefono = ?, email = ?, "
        "sincronizado = 0, updated_at = ? WHERE id = ?",
        (proveedor.nombre, proveedor.cuit, proveedor.telefono, proveedor.email,
         ahora_iso(), proveedor.id),
    )


def eliminar(conn: sqlite3.Connection, proveedor_id: str) -> None:
    """Baja lógica: marca el proveedor como inactivo (no borra el registro para
    conservar el historial). Marca `sincronizado = 0` para propagar la baja."""
    conn.execute(
        "UPDATE proveedores SET activo = 0, sincronizado = 0, updated_at = ? "
        "WHERE id = ?", (ahora_iso(), proveedor_id),
    )


def obtener(conn: sqlite3.Connection, proveedor_id: str) -> Proveedor | None:
    row = conn.execute(
        "SELECT id, nombre, cuit, telefono, email, saldo_cuenta, activo "
        "FROM proveedores WHERE id = ?", (proveedor_id,)
    ).fetchone()
    return _to_proveedor(row) if row else None


def listar_activos(conn: sqlite3.Connection) -> list[Proveedor]:
    rows = conn.execute(
        "SELECT id, nombre, cuit, telefono, email, saldo_cuenta, activo "
        "FROM proveedores WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [_to_proveedor(r) for r in rows]


# --- Lectura para sincronización del catálogo (local -> nube) --------------

def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM proveedores WHERE sincronizado = 0"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, proveedor_id: str) -> None:
    conn.execute(
        "UPDATE proveedores SET sincronizado = 1 WHERE id = ?", (proveedor_id,)
    )


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Baja un proveedor de Neon. Conserva el saldo_cuenta local; para uno nuevo
    lo trae completo. No pisa si hay cambios locales sin subir."""
    actual = conn.execute(
        "SELECT sincronizado FROM proveedores WHERE id = ?", (fila["id"],)
    ).fetchone()
    if actual is not None and actual["sincronizado"] == 0:
        return
    updated = (fila["updated_at"].isoformat()
               if hasattr(fila["updated_at"], "isoformat") else str(fila["updated_at"]))
    if actual is not None:
        conn.execute(
            "UPDATE proveedores SET nombre = ?, cuit = ?, telefono = ?, email = ?, "
            "activo = ?, sincronizado = 1, updated_at = ? WHERE id = ?",
            (fila["nombre"], fila["cuit"], fila["telefono"], fila["email"],
             1 if fila["activo"] else 0, updated, fila["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO proveedores (id, nombre, cuit, telefono, email, "
            "saldo_cuenta, activo, sincronizado, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (fila["id"], fila["nombre"], fila["cuit"], fila["telefono"],
             fila["email"], str(fila["saldo_cuenta"]),
             1 if fila["activo"] else 0, updated),
        )
