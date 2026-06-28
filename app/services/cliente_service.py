"""Lógica de negocio de clientes/fiados."""
from decimal import Decimal

from app.core import db_local
from app.core.utils import nuevo_id
from app.models.cliente import Cliente
from app.repositories import cliente_repo, cuenta_repo


class ClienteError(Exception):
    """Error de negocio esperable."""


def crear(nombre: str, telefono: str | None = None,
          limite_credito: Decimal = Decimal("0")) -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ClienteError("El cliente necesita un nombre.")
    cliente_id = nuevo_id()
    conn = db_local.connect()
    try:
        with conn:
            cliente_repo.crear(conn, cliente_id, nombre, telefono, limite_credito)
    finally:
        conn.close()
    return cliente_id


def registrar_pago(cliente_id: str, monto: Decimal,
                   nota: str | None = None) -> None:
    """Registra un pago del cliente: baja lo que nos debe (HABER)."""
    if monto <= 0:
        raise ClienteError("El monto del pago debe ser mayor a cero.")
    conn = db_local.connect()
    try:
        with conn:
            cuenta_repo.registrar_movimiento(
                conn, entidad_tipo="CLIENTE", entidad_id=cliente_id,
                tipo=cuenta_repo.HABER, monto=monto,
                referencia_tipo="PAGO", nota=nota or "Pago de cuenta")
    finally:
        conn.close()


def listar_activos() -> list[Cliente]:
    conn = db_local.connect()
    try:
        return cliente_repo.listar_activos(conn)
    finally:
        conn.close()
