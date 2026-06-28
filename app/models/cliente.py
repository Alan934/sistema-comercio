"""Entidad Cliente (cuenta corriente / fiado)."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Cliente:
    id: str
    nombre: str
    saldo_cuenta: Decimal      # lo que NOS DEBE
    limite_credito: Decimal
    telefono: str | None = None
