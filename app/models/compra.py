"""Entidades de compra/remito: cabecera (Compra) y renglón (ItemCompra)."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENTAVOS = Decimal("0.01")

# Condiciones de compra.
CONTADO = "CONTADO"
CUENTA_CORRIENTE = "CUENTA_CORRIENTE"


@dataclass
class ItemCompra:
    producto_id: str
    cantidad: Decimal
    costo_unitario: Decimal
    fecha_vencimiento: str | None = None   # ISO date; solo para perecederos

    @property
    def subtotal(self) -> Decimal:
        return (self.cantidad * self.costo_unitario).quantize(
            CENTAVOS, rounding=ROUND_HALF_UP)


@dataclass
class Compra:
    id: str
    proveedor_id: str
    fecha: str
    nro_remito: str | None
    total: Decimal
    condicion: str             # CONTADO | CUENTA_CORRIENTE
    created_at: str
    updated_at: str
