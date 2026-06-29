"""Lógica de negocio de reportes.

Recibe fechas como `date` y devuelve valores ya en Decimal (cuantizados a
centavos), listos para mostrar. La ganancia neta descuenta los gastos:

    ganancia_bruta = total_vendido - costo_total      (margen de los productos)
    ganancia_neta  = ganancia_bruta - gastos          (lo que queda de verdad)
"""
from datetime import date, timedelta
from decimal import Decimal

from app.core import db_local
from app.repositories import reporte_repo

CENTAVOS = Decimal("0.01")


def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(CENTAVOS)


def _rango(desde: date, hasta: date) -> tuple[str, str]:
    return desde.isoformat(), hasta.isoformat()


def resumen(desde: date, hasta: date) -> dict:
    """Números clave del período: ventas, costo, ganancia bruta/neta, gastos,
    unidades, ticket promedio y margen %."""
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        rv = reporte_repo.resumen_ventas(conn, d, h)
        gastos = _money(reporte_repo.total_gastos(conn, d, h))
        unidades = Decimal(str(reporte_repo.unidades_vendidas(conn, d, h)))
    finally:
        conn.close()

    cantidad = rv["cantidad"]
    total_vendido = _money(rv["total_vendido"])
    costo_total = _money(rv["costo_total"])
    ganancia_bruta = total_vendido - costo_total
    ticket = _money(total_vendido / cantidad) if cantidad else Decimal("0.00")
    margen = ((ganancia_bruta / total_vendido * 100).quantize(Decimal("0.1"))
              if total_vendido > 0 else Decimal("0.0"))
    return {
        "ventas_cantidad": cantidad,
        "unidades": unidades,
        "total_vendido": total_vendido,
        "costo_total": costo_total,
        "ganancia_bruta": ganancia_bruta,
        "gastos_total": gastos,
        "ganancia_neta": ganancia_bruta - gastos,
        "ticket_promedio": ticket,
        "margen_pct": margen,
    }


def por_categoria(desde: date, hasta: date) -> list[dict]:
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        rows = reporte_repo.por_categoria(conn, d, h)
    finally:
        conn.close()
    return [{"categoria": r["categoria"], "ventas": _money(r["ventas"]),
             "ganancia": _money(r["ganancia"])} for r in rows]


def ranking_proveedores(desde: date, hasta: date) -> list[dict]:
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        rows = reporte_repo.ranking_proveedores(conn, d, h)
    finally:
        conn.close()
    return [{"proveedor": r["nombre"], "comprado": _money(r["comprado"]),
             "remitos": r["remitos"], "deuda": _money(r["deuda"])} for r in rows]


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
             "total": _money(r["total"]), "ganancia": _money(r["ganancia"])}
            for r in rows]


def ventas_serie(desde: date, hasta: date) -> dict:
    """Serie temporal de ventas para el gráfico de tendencia. Elige el grano
    según el rango: diario hasta ~1 mes, mensual para rangos largos. Rellena
    los períodos sin ventas con 0 para que el gráfico no tenga huecos.
    Devuelve {titulo, puntos: [(etiqueta, total Decimal)]}."""
    d, h = _rango(desde, hasta)
    conn = db_local.connect()
    try:
        if (hasta - desde).days <= 31:
            datos = {r["dia"]: r["total"]
                     for r in reporte_repo.ventas_por_dia(conn, d, h)}
            puntos, dia = [], desde
            while dia <= hasta:
                puntos.append((dia.strftime("%d"),
                               _money(datos.get(dia.isoformat(), 0))))
                dia += timedelta(days=1)
            return {"titulo": "Ventas por día", "puntos": puntos}

        datos = {r["mes"]: r["total"]
                 for r in reporte_repo.ventas_por_mes(conn, d, h)}
        puntos, anio, mes = [], desde.year, desde.month
        while (anio, mes) <= (hasta.year, hasta.month):
            puntos.append((f"{mes:02d}", _money(datos.get(f"{anio:04d}-{mes:02d}", 0))))
            mes += 1
            if mes > 12:
                mes, anio = 1, anio + 1
        return {"titulo": "Ventas por mes", "puntos": puntos}
    finally:
        conn.close()


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
