"""Entidad Categoría de productos (con margen de ganancia por defecto)."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Categoria:
    id: str
    nombre: str
    margen_pct: Decimal | None   # margen por defecto (%); None = sin margen
    activo: bool = True
