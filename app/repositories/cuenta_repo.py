"""Cuenta corriente unificada (clientes y proveedores).

Cada movimiento actualiza el saldo de la entidad y deja registro en el libro
mayor (cuenta_movimientos), guardando el saldo resultante para auditoría.
Convención de saldos:
  - CLIENTE.saldo_cuenta   = lo que NOS DEBE  (DEBE lo aumenta, HABER lo baja)
  - PROVEEDOR.saldo_cuenta = lo que LE DEBEMOS (DEBE lo aumenta, HABER lo baja)
"""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso, nuevo_id

DEBE = "DEBE"
HABER = "HABER"


def registrar_movimiento(
    conn: sqlite3.Connection,
    entidad_tipo: str,           # 'CLIENTE' | 'PROVEEDOR'
    entidad_id: str,
    tipo: str,                   # DEBE | HABER
    monto: Decimal,
    referencia_tipo: str | None = None,   # VENTA | COMPRA | PAGO
    referencia_id: str | None = None,
    nota: str | None = None,
) -> None:
    tabla = "clientes" if entidad_tipo == "CLIENTE" else "proveedores"
    row = conn.execute(
        f"SELECT saldo_cuenta FROM {tabla} WHERE id = ?", (entidad_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"{entidad_tipo} inexistente: {entidad_id}")

    saldo_actual = Decimal(str(row["saldo_cuenta"]))
    nuevo_saldo = saldo_actual + monto if tipo == DEBE else saldo_actual - monto
    ahora = ahora_iso()

    # sincronizado=0: al cambiar el saldo, hay que volver a subir la entidad
    # para que la nube refleje la deuda actualizada.
    conn.execute(
        f"UPDATE {tabla} SET saldo_cuenta = ?, sincronizado = 0, updated_at = ? "
        "WHERE id = ?",
        (str(nuevo_saldo), ahora, entidad_id),
    )
    conn.execute(
        """INSERT INTO cuenta_movimientos
           (id, entidad_tipo, entidad_id, fecha, tipo, monto, saldo_resultante,
            referencia_tipo, referencia_id, nota, sincronizado, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (nuevo_id(), entidad_tipo, entidad_id, ahora, tipo, str(monto),
         str(nuevo_saldo), referencia_tipo, referencia_id, nota, ahora),
    )


# --- Lectura para sincronización (local -> nube) ---------------------------

def obtener_pendientes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM cuenta_movimientos WHERE sincronizado = 0 ORDER BY created_at"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, movimiento_id: str) -> None:
    conn.execute(
        "UPDATE cuenta_movimientos SET sincronizado = 1 WHERE id = ?",
        (movimiento_id,),
    )
