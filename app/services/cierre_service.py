"""Lógica de negocio del cierre de caja (arqueo).

efectivo esperado = fondo + ventas en efectivo + cobros de fiado en efectivo
                    − pagos a proveedores en efectivo − gastos en efectivo.
diferencia = efectivo contado − efectivo esperado  (>0 sobrante, <0 faltante).

Cobros de fiado, pagos a proveedores y gastos solo tocan la caja si fueron en
efectivo: un fiado no es plata hasta que el cliente lo paga en mano, y un gasto
pagado por transferencia no descuenta del efectivo del cajón.
"""
from decimal import Decimal

from app.core import db_local
from app.core.utils import ahora_iso, ahora_local, nuevo_id
from app.models.usuario import Usuario
from app.repositories import cierre_repo

CENTAVOS = Decimal("0.01")


def _d(x) -> Decimal:
    return Decimal(str(x)).quantize(CENTAVOS)


def resumen_periodo_abierto() -> dict:
    """Totales desde el último cierre hasta ahora (el período que se cerraría)."""
    conn = db_local.connect()
    try:
        ultimo = cierre_repo.ultimo(conn)
        desde = ultimo["fecha"] if ultimo else None
        r = cierre_repo.resumen_desde(conn, desde or "")
    finally:
        conn.close()
    return {
        "desde": desde,
        "ventas_cantidad": r["ventas_cantidad"],
        "total_vendido": _d(r["total_vendido"]),
        "efectivo": _d(r["efectivo"]),
        "transferencia": _d(r["transferencia"]),
        "tarjeta": _d(r["tarjeta"]),
        "fiado": _d(r["fiado"]),
        "cobros_efectivo": _d(r["cobros_efectivo"]),
        "pagos_efectivo": _d(r["pagos_efectivo"]),
        "gastos": _d(r["gastos"]),
        "gastos_efectivo": _d(r["gastos_efectivo"]),
    }


def realizar_cierre(usuario: Usuario, resumen: dict, fondo: Decimal,
                    efectivo_contado: Decimal, nota: str | None = None) -> dict:
    """Guarda el cierre con los totales previsualizados y devuelve el resultado."""
    fondo = _d(fondo)
    contado = _d(efectivo_contado)
    esperado = _d(fondo + resumen["efectivo"] + resumen["cobros_efectivo"]
                  - resumen["pagos_efectivo"] - resumen["gastos_efectivo"])
    diferencia = _d(contado - esperado)

    ahora = ahora_local()
    cierre = {
        "id": nuevo_id(),
        "fecha": ahora,
        "desde": resumen.get("desde"),
        "usuario_id": usuario.id,
        "usuario_nombre": usuario.username,
        "ventas_cantidad": resumen["ventas_cantidad"],
        "total_vendido": str(resumen["total_vendido"]),
        "efectivo_ventas": str(resumen["efectivo"]),
        "transferencia_ventas": str(resumen["transferencia"]),
        "tarjeta_ventas": str(resumen["tarjeta"]),
        "fiado_ventas": str(resumen["fiado"]),
        "cobros_efectivo": str(resumen["cobros_efectivo"]),
        "pagos_efectivo": str(resumen["pagos_efectivo"]),
        "gastos_total": str(resumen["gastos"]),
        "fondo": str(fondo),
        "efectivo_esperado": str(esperado),
        "efectivo_contado": str(contado),
        "diferencia": str(diferencia),
        "nota": (nota or "").strip() or None,
        "created_at": ahora_iso(),
    }
    conn = db_local.connect()
    try:
        with conn:
            cierre_repo.crear(conn, cierre)
    finally:
        conn.close()
    return {"efectivo_esperado": esperado, "diferencia": diferencia}


def listar_cierres(limite: int = 50) -> list[dict]:
    conn = db_local.connect()
    try:
        rows = cierre_repo.listar(conn, limite)
    finally:
        conn.close()
    return [dict(r) for r in rows]
