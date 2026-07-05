"""Lógica de negocio de proveedores y su cuenta corriente."""
from decimal import Decimal

from app.core import db_local
from app.core.utils import nuevo_id
from app.models.proveedor import Proveedor
from app.repositories import proveedor_repo, cuenta_repo


class ProveedorError(Exception):
    """Error de negocio esperable (se muestra al usuario)."""


def _verificar_duplicado(conn, nombre: str, cuit: str | None,
                         telefono: str | None,
                         excluir_id: str | None = None) -> None:
    """Lanza ProveedorError si otro proveedor colisiona por nombre, CUIT o
    teléfono. `excluir_id` deja fuera al propio proveedor al editar."""
    existente = proveedor_repo.buscar_duplicado(
        conn, nombre, cuit, telefono, excluir_id=excluir_id)
    if existente is None:
        return
    if existente.nombre.strip().lower() == nombre.lower():
        motivo = f"Ya existe un proveedor con el nombre «{existente.nombre}»."
    elif cuit and existente.cuit and existente.cuit.strip() == cuit.strip():
        motivo = (f"El CUIT ya está registrado en el proveedor "
                  f"«{existente.nombre}».")
    else:
        motivo = (f"El teléfono ya está registrado en el proveedor "
                  f"«{existente.nombre}».")
    raise ProveedorError(motivo)


def crear(nombre: str, cuit: str | None = None,
          telefono: str | None = None, email: str | None = None) -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ProveedorError("El proveedor necesita un nombre.")
    proveedor = Proveedor(
        id=nuevo_id(), nombre=nombre, cuit=cuit, telefono=telefono,
        saldo_cuenta=Decimal("0.00"), activo=True, email=email)
    conn = db_local.connect()
    try:
        with conn:
            _verificar_duplicado(conn, nombre, cuit, telefono)
            proveedor_repo.crear(conn, proveedor)
    finally:
        conn.close()
    return proveedor.id


def editar(proveedor_id: str, nombre: str, cuit: str | None = None,
           telefono: str | None = None, email: str | None = None) -> None:
    """Actualiza los datos de contacto de un proveedor existente.

    Valida el nombre y evita colisiones con otros proveedores (mismo nombre,
    CUIT o teléfono)."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ProveedorError("El proveedor necesita un nombre.")
    conn = db_local.connect()
    try:
        with conn:
            actual = proveedor_repo.obtener(conn, proveedor_id)
            if actual is None:
                raise ProveedorError("Proveedor inexistente.")
            _verificar_duplicado(conn, nombre, cuit, telefono,
                                 excluir_id=proveedor_id)
            actual.nombre = nombre
            actual.cuit = cuit
            actual.telefono = telefono
            actual.email = email
            proveedor_repo.actualizar(conn, actual)
    finally:
        conn.close()


def eliminar(proveedor_id: str) -> None:
    """Da de baja un proveedor (baja lógica). No permite eliminar si tiene saldo
    pendiente, para no perder el rastro de lo que se le debe."""
    conn = db_local.connect()
    try:
        with conn:
            actual = proveedor_repo.obtener(conn, proveedor_id)
            if actual is None:
                raise ProveedorError("Proveedor inexistente.")
            if actual.saldo_cuenta != Decimal("0"):
                raise ProveedorError(
                    "No se puede eliminar: el proveedor tiene saldo pendiente. "
                    "Registrá el pago o ajustá el saldo a cero primero.")
            proveedor_repo.eliminar(conn, proveedor_id)
    finally:
        conn.close()


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


def registrar_pago(proveedor_id: str, monto: Decimal, metodo: str = "EFECTIVO",
                   nota: str | None = None) -> None:
    """Registra un pago a un proveedor: baja lo que le debemos (HABER).

    `metodo` (EFECTIVO/TRANSFERENCIA/TARJETA) permite que el arqueo descuente
    de la caja solo lo que se pagó en efectivo."""
    if monto <= 0:
        raise ProveedorError("El monto del pago debe ser mayor a cero.")
    conn = db_local.connect()
    try:
        with conn:
            cuenta_repo.registrar_movimiento(
                conn, entidad_tipo="PROVEEDOR", entidad_id=proveedor_id,
                tipo=cuenta_repo.HABER, monto=monto,
                referencia_tipo="PAGO", nota=nota or "Pago a proveedor",
                metodo=metodo)
    finally:
        conn.close()
