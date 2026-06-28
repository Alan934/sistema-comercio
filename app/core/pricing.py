"""Cálculo de precios a partir de costo y margen de ganancia.

Reglas de negocio:
  - El margen efectivo de un producto es el SUYO si lo tiene definido; si no,
    el de su categoría; si ninguno, no hay margen (precio manual).
  - precio = costo * (1 + margen/100), redondeado a centavos.
"""
from decimal import Decimal, ROUND_HALF_UP

CENTAVOS = Decimal("0.01")


def margen_efectivo(margen_producto, margen_categoria):
    """Devuelve el margen que aplica (producto pisa categoría) o None."""
    if margen_producto is not None:
        return margen_producto
    return margen_categoria


def precio_desde_margen(costo, margen) -> Decimal:
    costo = Decimal(str(costo))
    margen = Decimal(str(margen))
    return (costo * (Decimal(1) + margen / Decimal(100))).quantize(
        CENTAVOS, rounding=ROUND_HALF_UP)
