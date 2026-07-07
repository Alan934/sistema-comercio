"""Entidad Res: una media res (o res) que ingresa por kg para despiezar.

Se compra por peso a un costo/kg y se subdivide en piezas (Espalda, Pierna).
Queda ABIERTA hasta terminar de bajar todas sus piezas.
"""
from dataclasses import dataclass
from decimal import Decimal

# Condición de compra (reusa la convención de compras).
CONTADO = "CONTADO"
CUENTA_CORRIENTE = "CUENTA_CORRIENTE"

# Estados del despiece.
ABIERTA = "ABIERTA"
CERRADA = "CERRADA"


@dataclass
class Res:
    id: str
    proveedor_id: str | None
    fecha: str
    descripcion: str
    peso_total: Decimal
    costo_por_kg: Decimal
    costo_total: Decimal
    condicion: str = CONTADO
    estado: str = ABIERTA
    margen_pct: Decimal | None = None
