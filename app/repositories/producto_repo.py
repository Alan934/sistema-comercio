"""Acceso a datos de productos. Todas las funciones reciben la conexión
para poder participar de una transacción más grande (ej. una venta)."""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso
from app.models.producto import Producto

_COLS = ("id, codigo_barra, nombre, es_pesable, unidad_medida, "
         "precio_venta, costo_compra, stock_actual, controla_stock, activo")


def _to_producto(row: sqlite3.Row) -> Producto:
    return Producto(
        id=row["id"],
        codigo_barra=row["codigo_barra"],
        nombre=row["nombre"],
        es_pesable=bool(row["es_pesable"]),
        unidad_medida=row["unidad_medida"],
        precio_venta=Decimal(str(row["precio_venta"])),
        costo_compra=Decimal(str(row["costo_compra"])),
        stock_actual=Decimal(str(row["stock_actual"])),
        controla_stock=bool(row["controla_stock"]),
        activo=bool(row["activo"]),
    )


def buscar_por_codigo(conn: sqlite3.Connection, codigo: str) -> Producto | None:
    """Lo que dispara la 'pistolita': busca por código de barra exacto."""
    row = conn.execute(
        f"SELECT {_COLS} FROM productos WHERE codigo_barra = ? AND activo = 1",
        (codigo,),
    ).fetchone()
    return _to_producto(row) if row else None


def buscar_por_nombre(conn: sqlite3.Connection, texto: str,
                      limite: int = 20) -> list[Producto]:
    """Búsqueda parcial por nombre (para el buscador manual del POS)."""
    rows = conn.execute(
        f"SELECT {_COLS} FROM productos "
        "WHERE nombre LIKE ? AND activo = 1 ORDER BY nombre LIMIT ?",
        (f"%{texto}%", limite),
    ).fetchall()
    return [_to_producto(r) for r in rows]


def descontar_stock(conn: sqlite3.Connection, producto_id: str,
                    cantidad: Decimal) -> None:
    """Resta del stock leyendo y reescribiendo en Decimal (texto) para no
    perder precisión con pesos como 0.750. Permite stock negativo a propósito:
    en un kiosko nunca se bloquea una venta por stock desactualizado."""
    row = conn.execute(
        "SELECT stock_actual FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Producto inexistente: {producto_id}")
    nuevo_stock = Decimal(str(row["stock_actual"])) - cantidad
    conn.execute(
        "UPDATE productos SET stock_actual = ?, updated_at = ? WHERE id = ?",
        (str(nuevo_stock), ahora_iso(), producto_id),
    )
