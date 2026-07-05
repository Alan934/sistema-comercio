"""Lógica de negocio de gastos."""
from decimal import Decimal

from app.core import db_local
from app.core.utils import ahora_local, nuevo_id
from app.models.gasto import Gasto, TIPOS, FIJO, VARIABLE
from app.repositories import gasto_repo


class GastoError(Exception):
    """Error de negocio esperable."""


def crear_gasto(tipo: str, descripcion: str, monto: Decimal,
                proveedor_id: str | None = None,
                fecha: str | None = None, metodo: str = "EFECTIVO") -> str:
    descripcion = (descripcion or "").strip()
    if tipo not in TIPOS:
        raise GastoError("El tipo debe ser FIJO o VARIABLE.")
    if not descripcion:
        raise GastoError("El gasto necesita una descripción.")
    if monto <= 0:
        raise GastoError("El monto debe ser mayor a cero.")

    gasto = Gasto(
        id=nuevo_id(), fecha=fecha or ahora_local(), tipo=tipo,
        descripcion=descripcion, monto=monto, proveedor_id=proveedor_id,
        metodo=metodo)
    conn = db_local.connect()
    try:
        with conn:
            gasto_repo.crear(conn, gasto)
    finally:
        conn.close()
    return gasto.id


def listar(desde: str, hasta: str) -> list[dict]:
    conn = db_local.connect()
    try:
        return [dict(r) for r in gasto_repo.listar(conn, desde, hasta)]
    finally:
        conn.close()
