"""Entidad Proveedor (cuenta corriente: lo que LE DEBEMOS)."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Proveedor:
    id: str
    nombre: str
    cuit: str | None
    telefono: str | None
    saldo_cuenta: Decimal      # lo que le debemos (>0 = deuda nuestra)
    activo: bool
