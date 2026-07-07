"""Entidad Corte: renglón de despiece de una pieza.

Cada corte tiene kg y precio/kg (como en la planilla de la carnicera) y, al
confirmarse, suma su peso al stock de un producto pesable. El costo/kg se toma
de la res (mismo costo para todos los cortes, tal como lo calcula ella).
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENTAVOS = Decimal("0.01")


@dataclass
class Corte:
    id: str
    pieza_id: str
    descripcion: str
    peso: Decimal
    precio_venta_kg: Decimal
    producto_id: str | None = None
    margen_pct: Decimal | None = None
    costo_kg: Decimal = Decimal("0")
    es_desperdicio: bool = False
    confirmado: bool = False

    @property
    def subtotal(self) -> Decimal:
        """Lo que se espera vender de este corte: kg * precio/kg."""
        return (self.peso * self.precio_venta_kg).quantize(
            CENTAVOS, rounding=ROUND_HALF_UP)

    @property
    def costo(self) -> Decimal:
        """Costo asignado al corte: kg * costo/kg de la res."""
        return (self.peso * self.costo_kg).quantize(
            CENTAVOS, rounding=ROUND_HALF_UP)

    @property
    def ganancia(self) -> Decimal:
        return self.subtotal - self.costo
