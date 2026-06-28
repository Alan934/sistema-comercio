"""Lógica de negocio de reportes.

Recibe fechas como `date` y devuelve valores ya en Decimal (cuantizados a
centavos), listos para mostrar. La ganancia neta descuenta los gastos:

    ganancia_bruta = total_vendido - costo_total      (margen de los productos)
    ganancia_neta  = ganancia_bruta - gastos          (lo que queda de verdad)
"""
from datetime import date
from decimal import Decimal

from app.core import db_local
from app.repositories import reporte_repo

CENTAVOS = Decimal("0.01")


def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(CENTAVOS)


def _rango(desde: date, hasta: date) -> tuple[str, str]:
    return desde.isoformat(), hasta.isoformat()


def resumen(desde: date, hasta: date) -> dict:
    """Números clave del período: ventas, costo, ganancia bruta/neta, gastos."""
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        rv = reporte_repo.resumen_ventas(conn, d, h)
        gastos = _money(reporte_repo.total_gastos(conn, d, h))
    finally:
        conn.close()

    total_vendido = _money(rv["total_vendido"])
    costo_total = _money(rv["costo_total"])
    ganancia_bruta = total_vendido - costo_total
    return {
        "ventas_cantidad": rv["cantidad"],
        "total_vendido": total_vendido,
        "costo_total": costo_total,
        "ganancia_bruta": ganancia_bruta,
        "gastos_total": gastos,
        "ganancia_neta": ganancia_bruta - gastos,
    }


def gastos_por_tipo(desde: date, hasta: date) -> list[dict]:
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        rows = reporte_repo.gastos_por_tipo(conn, d, h)
    finally:
        conn.close()
    return [{"tipo": r["tipo"], "total": _money(r["total"])} for r in rows]


def ventas_por_metodo(desde: date, hasta: date) -> list[dict]:
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        rows = reporte_repo.ventas_por_metodo(conn, d, h)
    finally:
        conn.close()
    return [{"metodo": r["metodo"], "total": _money(r["total"])} for r in rows]


def top_productos(desde: date, hasta: date, limite: int = 10) -> list[dict]:
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        rows = reporte_repo.top_productos(conn, d, h, limite)
    finally:
        conn.close()
    return [{"producto": r["descripcion"], "cantidad": r["cantidad"],
             "total": _money(r["total"])} for r in rows]


def por_proveedor(desde: date, hasta: date) -> dict:
    """Compras y gastos agrupados por proveedor en el período."""
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        compras = reporte_repo.compras_por_proveedor(conn, d, h)
        gastos = reporte_repo.gastos_por_proveedor(conn, d, h)
    finally:
        conn.close()
    return {
        "compras": [{"proveedor": r["nombre"], "total": _money(r["total"])}
                    for r in compras],
        "gastos": [{"proveedor": r["nombre"], "total": _money(r["total"])}
                   for r in gastos],
    }
