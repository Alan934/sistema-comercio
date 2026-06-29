"""Lógica de negocio de proveedores y su cuenta corriente."""
from decimal import Decimal

from app.core import db_local
from app.core.utils import nuevo_id
from app.models.proveedor import Proveedor
from app.repositories import proveedor_repo, cuenta_repo


class ProveedorError(Exception):
    """Error de negocio esperable (se muestra al usuario)."""


def crear(nombre: str, cuit: str | None = None,
          telefono: str | None = None) -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ProveedorError("El proveedor necesita un nombre.")
    proveedor = Proveedor(
        id=nuevo_id(), nombre=nombre, cuit=cuit, telefono=telefono,
        saldo_cuenta=Decimal("0.00"), activo=True)
    conn = db_local.connect()
    try:
        with conn:
            proveedor_repo.crear(conn, proveedor)
    finally:
        conn.close()
    return proveedor.id


def listar_activos() -> list[Proveedor]:
    conn = db_local.connect()
    try:
        return proveedor_repo.listar_activos(conn)
    finally:
        conn.close()


def ajustar_saldo(proveedor_id: str, nuevo_saldo: Decimal) -> None:
    """Corrige el saldo a un valor concreto (ej. dejarlo en 0). Registra la
    diferencia como un movimiento de ajuste, así queda el rastro."""
    if nuevo_saldo < 0:
        raise ProveedorError("El saldo no puede ser negativo.")
    conn = db_local.connect()
    try:
        with conn:
            row = conn.execute(
                "SELECT saldo_cuenta FROM proveedores WHERE id = ?",
                (proveedor_id,)).fetchone()
            if row is None:
                raise ProveedorError("Proveedor inexistente.")
            diferencia = nuevo_saldo - Decimal(str(row["saldo_cuenta"]))
            if diferencia == 0:
                return
            tipo = cuenta_repo.DEBE if diferencia > 0 else cuenta_repo.HABER
            cuenta_repo.registrar_movimiento(
                conn, entidad_tipo="PROVEEDOR", entidad_id=proveedor_id,
                tipo=tipo, monto=abs(diferencia), referencia_tipo="AJUSTE",
                nota="Ajuste de saldo")
    finally:
        conn.close()


def registrar_pago(proveedor_id: str, monto: Decimal,
                   nota: str | None = None) -> None:
    """Registra un pago a un proveedor: baja lo que le debemos (HABER)."""
    if monto <= 0:
        raise ProveedorError("El monto del pago debe ser mayor a cero.")
    conn = db_local.connect()
    try:
        with conn:
            cuenta_repo.registrar_movimiento(
                conn, entidad_tipo="PROVEEDOR", entidad_id=proveedor_id,
                tipo=cuenta_repo.HABER, monto=monto,
                referencia_tipo="PAGO", nota=nota or "Pago a proveedor")
    finally:
        conn.close()
