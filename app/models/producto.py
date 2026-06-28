"""Entidad Producto (objeto puro, sin lógica de base de datos)."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Producto:
    id: str
    codigo_barra: str | None
    nombre: str
    es_pesable: bool          # True = se vende al peso (kg)
    unidad_medida: str        # 'UN' | 'KG'
    precio_venta: Decimal
    costo_compra: Decimal
    stock_actual: Decimal
    controla_stock: bool
    activo: bool
