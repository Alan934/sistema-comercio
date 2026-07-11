"""Lógica de negocio del POS. Orquesta repositorios y transacciones.
La UI llamará a estas funciones y nunca verá SQL.
"""
from decimal import Decimal

from app.core import db_local
from app.core.utils import ahora_iso, ahora_local, nuevo_id
from app.models.carrito import Carrito
from app.models.producto import Producto
from app.models.venta import Venta, Pago, FIADO, METODOS_PAGO
from app.repositories import producto_repo, venta_repo, cuenta_repo, lote_repo


class VentaError(Exception):
    """Error de negocio esperable (se muestra al usuario, no es un crash)."""


# --- Búsqueda de productos (lo que usa la caja al escanear o buscar) --------

def buscar_por_codigo(codigo: str) -> Producto | None:
    conn = db_local.connect()
    try:
        return producto_repo.buscar_por_codigo(conn, codigo)
    finally:
        conn.close()


def buscar_por_nombre(texto: str) -> list[Producto]:
    conn = db_local.connect()
    try:
        return producto_repo.buscar_por_nombre(conn, texto)
    finally:
        conn.close()


def stock_actual(producto_id: str) -> Decimal:
    """Stock disponible de un producto (para que la caja valide antes de
    agregarlo al carrito). Si el producto no existe, devuelve 0."""
    conn = db_local.connect()
    try:
        row = producto_repo.obtener(conn, producto_id)
        return Decimal(str(row["stock_actual"])) if row is not None else Decimal("0")
    finally:
        conn.close()


# --- Registro de la venta ---------------------------------------------------

def registrar_venta(carrito: Carrito, pagos: list[Pago],
                    cliente_id: str | None = None) -> str:
    """Valida y persiste la venta en una sola transacción: cabecera, detalle,
    pagos, descuento de stock y, si hay fiado, la cuenta corriente del cliente.
    Devuelve el id de la venta. Lanza VentaError si algo no cierra."""
    if carrito.esta_vacio():
        raise VentaError("El carrito está vacío.")

    for p in pagos:
        if p.metodo not in METODOS_PAGO:
            raise VentaError(f"Método de pago inválido: {p.metodo}")
        if p.monto <= 0:
            raise VentaError("Hay un pago con monto cero o negativo.")

    total = carrito.total
    total_pagado = sum((p.monto for p in pagos), Decimal("0"))
    if total_pagado != total:
        raise VentaError(
            f"Los pagos (${total_pagado}) no coinciden con el total (${total})."
        )

    monto_fiado = sum((p.monto for p in pagos if p.metodo == FIADO), Decimal("0"))
    if monto_fiado > 0 and not cliente_id:
        raise VentaError("Una venta fiada requiere elegir un cliente.")

    ahora = ahora_iso()
    venta = Venta(
        id=nuevo_id(),
        fecha=ahora_local(),
        cliente_id=cliente_id,
        subtotal=carrito.subtotal,
        descuento=Decimal("0.00"),
        total=total,
        costo_total=carrito.costo_total,
        created_at=ahora,
        updated_at=ahora,
    )

    conn = db_local.connect()
    try:
        with conn:  # commit si todo OK, rollback automático si hay excepción
            venta_repo.guardar(conn, venta, carrito.items, pagos)
            for it in carrito.items:
                if it.controla_stock:
                    producto_repo.descontar_stock(
                        conn, it.producto_id, it.cantidad,
                        referencia_id=venta.id)
                if it.controla_vencimiento:
                    # Perecedero: descuenta primero del lote que vence antes.
                    lote_repo.consumir_fefo(
                        conn, it.producto_id, it.cantidad)
            if monto_fiado > 0:
                cuenta_repo.registrar_movimiento(
                    conn,
                    entidad_tipo="CLIENTE",
                    entidad_id=cliente_id,
                    tipo=cuenta_repo.DEBE,
                    monto=monto_fiado,
                    referencia_tipo="VENTA",
                    referencia_id=venta.id,
                    nota="Venta fiada",
                )
    finally:
        conn.close()

    return venta.id
