"""Lógica de negocio de stock: alta/edición de productos y alertas."""
from datetime import date
from decimal import Decimal

from app.core import db_local
from app.core.utils import ahora_iso, nuevo_id
from app.models.producto import Producto
from app.repositories import producto_repo, lote_repo


class StockError(Exception):
    """Error de negocio esperable."""


def _normalizar(datos: dict, *, con_id: bool) -> dict:
    """Completa valores por defecto y normaliza tipos para guardar."""
    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        raise StockError("El producto necesita un nombre.")
    completo = {
        "codigo_barra": (datos.get("codigo_barra") or None),
        "nombre": nombre,
        "categoria_id": datos.get("categoria_id"),
        "es_pesable": 1 if datos.get("es_pesable") else 0,
        "unidad_medida": datos.get("unidad_medida") or ("KG" if datos.get("es_pesable") else "UN"),
        "costo_compra": str(datos.get("costo_compra", "0")),
        "precio_venta": str(datos.get("precio_venta", "0")),
        "stock_minimo": str(datos.get("stock_minimo", "0")),
        "controla_stock": 1 if datos.get("controla_stock", True) else 0,
        "controla_vencimiento": 1 if datos.get("controla_vencimiento") else 0,
        "activo": 1 if datos.get("activo", True) else 0,
        "updated_at": ahora_iso(),
    }
    if con_id:
        completo["id"] = datos["id"]
    return completo


def crear_producto(datos: dict) -> str:
    """Alta de producto. Devuelve el id generado."""
    completo = _normalizar(datos, con_id=False)
    completo["id"] = nuevo_id()
    completo["stock_actual"] = str(datos.get("stock_actual", "0"))
    conn = db_local.connect()
    try:
        with conn:
            producto_repo.crear(conn, completo)
    finally:
        conn.close()
    return completo["id"]


def actualizar_producto(producto_id: str, datos: dict) -> None:
    """Edita un producto existente (no cambia el stock_actual)."""
    completo = _normalizar({**datos, "id": producto_id}, con_id=True)
    conn = db_local.connect()
    try:
        with conn:
            producto_repo.actualizar(conn, completo)
    finally:
        conn.close()


def listar_productos() -> list[Producto]:
    conn = db_local.connect()
    try:
        return producto_repo.listar_todos(conn)
    finally:
        conn.close()


def alertas_stock_bajo() -> list[dict]:
    conn = db_local.connect()
    try:
        rows = producto_repo.listar_stock_bajo(conn)
        return [dict(r) for r in rows]
    finally:
        conn.close()


def alertas_vencimientos(dias: int = 7) -> list[dict]:
    """Lotes por vencer/vencidos, con los días que faltan (negativo = vencido)."""
    conn = db_local.connect()
    try:
        rows = lote_repo.proximos_a_vencer(conn, dias)
    finally:
        conn.close()
    hoy = date.today()
    salida = []
    for r in rows:
        venc = date.fromisoformat(r["fecha_vencimiento"])
        salida.append({
            "producto": r["producto_nombre"],
            "fecha_vencimiento": r["fecha_vencimiento"],
            "cantidad": r["cantidad"],
            "dias_restantes": (venc - hoy).days,
        })
    return salida
