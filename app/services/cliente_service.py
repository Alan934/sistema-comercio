"""Lógica de negocio de clientes/fiados."""
from decimal import Decimal

from app.core import db_local
from app.core.utils import nuevo_id
from app.models.cliente import Cliente
from app.repositories import cliente_repo, cuenta_repo


class ClienteError(Exception):
    """Error de negocio esperable."""


def _verificar_duplicado(conn, nombre: str, telefono: str | None,
                         excluir_id: str | None = None) -> None:
    """Lanza ClienteError si otro cliente colisiona por nombre o teléfono.
    `excluir_id` deja fuera al propio cliente al editar."""
    existente = cliente_repo.buscar_duplicado(
        conn, nombre, telefono, excluir_id=excluir_id)
    if existente is None:
        return
    if existente.nombre.strip().lower() == nombre.lower():
        motivo = f"Ya existe un cliente con el nombre «{existente.nombre}»."
    else:
        motivo = (f"El teléfono ya está registrado en el cliente "
                  f"«{existente.nombre}».")
    raise ClienteError(motivo)


def crear(nombre: str, telefono: str | None = None,
          limite_credito: Decimal = Decimal("0")) -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ClienteError("El cliente necesita un nombre.")
    cliente_id = nuevo_id()
    conn = db_local.connect()
    try:
        with conn:
            _verificar_duplicado(conn, nombre, telefono)
            cliente_repo.crear(conn, cliente_id, nombre, telefono, limite_credito)
    finally:
        conn.close()
    return cliente_id


def editar(cliente_id: str, nombre: str, telefono: str | None = None,
           limite_credito: Decimal = Decimal("0")) -> None:
    """Actualiza los datos de un cliente existente. Valida el nombre y evita
    colisiones con otros clientes (mismo nombre o teléfono)."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ClienteError("El cliente necesita un nombre.")
    conn = db_local.connect()
    try:
        with conn:
            actual = cliente_repo.obtener(conn, cliente_id)
            if actual is None:
                raise ClienteError("Cliente inexistente.")
            _verificar_duplicado(conn, nombre, telefono, excluir_id=cliente_id)
            cliente_repo.actualizar(conn, cliente_id, nombre, telefono,
                                    limite_credito)
    finally:
        conn.close()


def eliminar(cliente_id: str) -> None:
    """Da de baja un cliente (baja lógica). No permite eliminar si tiene saldo
    pendiente (deuda o saldo a favor), para no perder el rastro de la plata."""
    conn = db_local.connect()
    try:
        with conn:
            actual = cliente_repo.obtener(conn, cliente_id)
            if actual is None:
                raise ClienteError("Cliente inexistente.")
            if actual.saldo_cuenta != Decimal("0"):
                raise ClienteError(
                    "No se puede eliminar: el cliente tiene saldo pendiente. "
                    "Registrá el pago o ajustá el saldo a cero primero.")
            cliente_repo.eliminar(conn, cliente_id)
    finally:
        conn.close()


def ajustar_saldo(cliente_id: str, nuevo_saldo: Decimal) -> None:
    """Corrige el saldo a un valor concreto. Registra la diferencia como un
    movimiento de ajuste (deja rastro)."""
    if nuevo_saldo < 0:
        raise ClienteError("El saldo no puede ser negativo.")
    conn = db_local.connect()
    try:
        with conn:
            row = conn.execute(
                "SELECT saldo_cuenta FROM clientes WHERE id = ?",
                (cliente_id,)).fetchone()
            if row is None:
                raise ClienteError("Cliente inexistente.")
            diferencia = nuevo_saldo - Decimal(str(row["saldo_cuenta"]))
            if diferencia == 0:
                return
            tipo = cuenta_repo.DEBE if diferencia > 0 else cuenta_repo.HABER
            cuenta_repo.registrar_movimiento(
                conn, entidad_tipo="CLIENTE", entidad_id=cliente_id,
                tipo=tipo, monto=abs(diferencia), referencia_tipo="AJUSTE",
                nota="Ajuste de saldo")
    finally:
        conn.close()


def registrar_pago(cliente_id: str, monto: Decimal, metodo: str = "EFECTIVO",
                   nota: str | None = None) -> None:
    """Registra un pago del cliente: baja lo que nos debe (HABER).

    `metodo` (EFECTIVO/TRANSFERENCIA/TARJETA) permite que el arqueo cuente
    la plata que realmente entró a la caja."""
    if monto <= 0:
        raise ClienteError("El monto del pago debe ser mayor a cero.")
    conn = db_local.connect()
    try:
        with conn:
            cuenta_repo.registrar_movimiento(
                conn, entidad_tipo="CLIENTE", entidad_id=cliente_id,
                tipo=cuenta_repo.HABER, monto=monto,
                referencia_tipo="PAGO", nota=nota or "Pago de cuenta",
                metodo=metodo)
    finally:
        conn.close()


def listar_activos() -> list[Cliente]:
    conn = db_local.connect()
    try:
        return cliente_repo.listar_activos(conn)
    finally:
        conn.close()
