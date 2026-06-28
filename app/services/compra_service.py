"""Lógica de negocio de compras/remitos.

Registrar un remito es una operación transaccional que, además de guardar la
compra, impacta varias cosas a la vez:
  - actualiza el costo de compra de cada producto (último costo del remito),
  - aumenta el stock,
  - crea lotes para los perecederos con vencimiento,
  - si es a cuenta corriente, suma la deuda con el proveedor.
Todo dentro de una sola transacción: o entra completo, o no entra nada.
"""
from decimal import Decimal

from app.core import db_local
from app.core.utils import ahora_iso, nuevo_id
from app.models.compra import Compra, ItemCompra, CONTADO, CUENTA_CORRIENTE
from app.repositories import compra_repo, producto_repo, lote_repo, cuenta_repo


class CompraError(Exception):
    """Error de negocio esperable."""


def registrar_compra(proveedor_id: str, items: list[ItemCompra],
                     nro_remito: str | None = None,
                     condicion: str = CONTADO) -> str:
    if not proveedor_id:
        raise CompraError("Elegí un proveedor para el remito.")
    if not items:
        raise CompraError("El remito no tiene productos.")
    if condicion not in (CONTADO, CUENTA_CORRIENTE):
        raise CompraError(f"Condición inválida: {condicion}")

    total = sum((it.subtotal for it in items), Decimal("0.00"))
    ahora = ahora_iso()
    compra = Compra(
        id=nuevo_id(), proveedor_id=proveedor_id, fecha=ahora,
        nro_remito=nro_remito, total=total, condicion=condicion,
        created_at=ahora, updated_at=ahora)

    conn = db_local.connect()
    try:
        with conn:
            compra_repo.guardar(conn, compra, items)
            for it in items:
                producto_repo.actualizar_costo(conn, it.producto_id, it.costo_unitario)
                # Si el producto tiene margen (propio o por categoría), el precio
                # se reajusta solo al nuevo costo; si no, queda el precio manual.
                producto_repo.recalcular_precio(conn, it.producto_id)
                producto_repo.aumentar_stock(conn, it.producto_id, it.cantidad)
                if it.fecha_vencimiento:
                    lote_repo.crear(conn, it.producto_id, it.fecha_vencimiento,
                                    it.cantidad, compra.id)
            if condicion == CUENTA_CORRIENTE:
                cuenta_repo.registrar_movimiento(
                    conn, entidad_tipo="PROVEEDOR", entidad_id=proveedor_id,
                    tipo=cuenta_repo.DEBE, monto=total,
                    referencia_tipo="COMPRA", referencia_id=compra.id,
                    nota=f"Remito {nro_remito or ''}".strip())
    finally:
        conn.close()

    return compra.id
