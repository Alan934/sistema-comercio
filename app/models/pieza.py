"""Entidad Pieza: subdivisión de una res (Espalda, Pierna, ...).

Se baja en un día concreto y agrupa los cortes que salen de ella. Al confirmar
la pieza, sus cortes cargan stock a los productos pesables correspondientes.
"""
from dataclasses import dataclass
from decimal import Decimal

ABIERTA = "ABIERTA"
CERRADA = "CERRADA"


@dataclass
class Pieza:
    id: str
    res_id: str
    nombre: str
    fecha: str
    peso: Decimal
    estado: str = ABIERTA
    margen_pct: Decimal | None = None
