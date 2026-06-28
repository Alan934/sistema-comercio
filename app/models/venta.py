"""Entidades de venta: cabecera (Venta) y pago (Pago)."""
from dataclasses import dataclass
from decimal import Decimal

# Métodos de pago admitidos.
EFECTIVO = "EFECTIVO"
TRANSFERENCIA = "TRANSFERENCIA"
TARJETA = "TARJETA"
FIADO = "FIADO"
METODOS_PAGO = (EFECTIVO, TRANSFERENCIA, TARJETA, FIADO)


@dataclass
class Pago:
    metodo: str       # uno de METODOS_PAGO
    monto: Decimal


@dataclass
class Venta:
    id: str
    fecha: str
    cliente_id: str | None     # None = consumidor final
    subtotal: Decimal
    descuento: Decimal
    total: Decimal
    costo_total: Decimal       # snapshot para ganancia neta
    created_at: str
    updated_at: str
    estado: str = "COMPLETADA"
