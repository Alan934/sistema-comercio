"""Entidad Gasto (fijos y variables, opcionalmente ligados a un proveedor)."""
from dataclasses import dataclass
from decimal import Decimal

# Tipos de gasto.
FIJO = "FIJO"
VARIABLE = "VARIABLE"
TIPOS = (FIJO, VARIABLE)


@dataclass
class Gasto:
    id: str
    fecha: str
    tipo: str              # FIJO | VARIABLE
    descripcion: str
    monto: Decimal
    proveedor_id: str | None = None
