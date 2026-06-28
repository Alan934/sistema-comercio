"""Acceso a datos de productos. Todas las funciones reciben la conexión
para poder participar de una transacción más grande (ej. una venta)."""
import sqlite3
from decimal import Decimal

from app.core import pricing
from app.core.utils import ahora_iso
from app.models.producto import Producto

_COLS = ("id, codigo_barra, nombre, es_pesable, unidad_medida, "
         "precio_venta, costo_compra, stock_actual, controla_stock, activo, "
         "categoria_id, margen_pct")


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
        categoria_id=row["categoria_id"],
        margen_pct=(Decimal(str(row["margen_pct"]))
                    if row["margen_pct"] is not None else None),
    )


def buscar_por_codigo(conn: sqlite3.Connection, codigo: str) -> Producto | None:
    """Lo que dispara la 'pistolita': busca por código de barra exacto."""
    row = conn.execute(
        f"SELECT {_COLS} FROM productos WHERE codigo_barra = ? AND activo = 1",
        (codigo,),
    ).fetchone()
    return _to_producto(row) if row else None


def obtener(conn: sqlite3.Connection, producto_id: str) -> sqlite3.Row | None:
    """Trae el producto completo (todas las columnas) para edición."""
    return conn.execute(
        "SELECT * FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()


def listar_todos(conn: sqlite3.Connection) -> list[Producto]:
    rows = conn.execute(
        f"SELECT {_COLS} FROM productos WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [_to_producto(r) for r in rows]


def listar_stock_bajo(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Productos cuyo stock llegó al mínimo. La columna es NUMERIC, así que
    la comparación stock_actual <= stock_minimo es numérica (no de texto)."""
    return conn.execute(
        "SELECT id, nombre, stock_actual, stock_minimo, unidad_medida "
        "FROM productos "
        "WHERE activo = 1 AND controla_stock = 1 "
        "  AND stock_actual <= stock_minimo "
        "ORDER BY nombre"
    ).fetchall()


def crear(conn: sqlite3.Connection, datos: dict) -> None:
    """Inserta un producto. `datos` debe traer todas las claves (lo arma
    stock_service con los valores por defecto ya completos)."""
    conn.execute(
        """INSERT INTO productos
             (id, codigo_barra, nombre, categoria_id, es_pesable, unidad_medida,
              costo_compra, precio_venta, margen_pct, stock_actual, stock_minimo,
              controla_stock, controla_vencimiento, activo, updated_at)
           VALUES
             (:id, :codigo_barra, :nombre, :categoria_id, :es_pesable, :unidad_medida,
              :costo_compra, :precio_venta, :margen_pct, :stock_actual, :stock_minimo,
              :controla_stock, :controla_vencimiento, :activo, :updated_at)""",
        datos,
    )


def actualizar(conn: sqlite3.Connection, datos: dict) -> None:
    """Edita catálogo y precios. No toca stock_actual (eso va por compras/ventas)."""
    conn.execute(
        """UPDATE productos SET
             codigo_barra = :codigo_barra, nombre = :nombre,
             categoria_id = :categoria_id, es_pesable = :es_pesable,
             unidad_medida = :unidad_medida, costo_compra = :costo_compra,
             precio_venta = :precio_venta, margen_pct = :margen_pct,
             stock_minimo = :stock_minimo,
             controla_stock = :controla_stock,
             controla_vencimiento = :controla_vencimiento,
             activo = :activo, updated_at = :updated_at
           WHERE id = :id""",
        datos,
    )


def aumentar_stock(conn: sqlite3.Connection, producto_id: str, cantidad) -> None:
    """Suma stock (al recibir un remito). Lee/reescribe en Decimal."""
    row = conn.execute(
        "SELECT stock_actual FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Producto inexistente: {producto_id}")
    nuevo = Decimal(str(row["stock_actual"])) + cantidad
    conn.execute(
        "UPDATE productos SET stock_actual = ?, updated_at = ? WHERE id = ?",
        (str(nuevo), ahora_iso(), producto_id),
    )


def actualizar_costo(conn: sqlite3.Connection, producto_id: str, costo) -> None:
    """Actualiza el costo de compra con el del último remito recibido."""
    conn.execute(
        "UPDATE productos SET costo_compra = ?, updated_at = ? WHERE id = ?",
        (str(costo), ahora_iso(), producto_id),
    )


def ids_por_categoria(conn: sqlite3.Connection, categoria_id: str) -> list[str]:
    return [r["id"] for r in conn.execute(
        "SELECT id FROM productos WHERE categoria_id = ?", (categoria_id,)).fetchall()]


def recalcular_precio(conn: sqlite3.Connection, producto_id: str) -> None:
    """Recalcula precio_venta = costo * (1 + margen/100) usando el margen
    efectivo (producto o, si no tiene, su categoría). Si no hay margen en
    ninguno, deja el precio como está (es manual)."""
    row = conn.execute(
        """SELECT p.costo_compra AS costo, p.margen_pct AS pm, c.margen_pct AS cm
           FROM productos p LEFT JOIN categorias c ON c.id = p.categoria_id
           WHERE p.id = ?""",
        (producto_id,),
    ).fetchone()
    if row is None:
        return
    pm = Decimal(str(row["pm"])) if row["pm"] is not None else None
    cm = Decimal(str(row["cm"])) if row["cm"] is not None else None
    margen = pricing.margen_efectivo(pm, cm)
    if margen is None:
        return
    precio = pricing.precio_desde_margen(row["costo"], margen)
    conn.execute(
        "UPDATE productos SET precio_venta = ?, updated_at = ? WHERE id = ?",
        (str(precio), ahora_iso(), producto_id),
    )


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


# --- Sincronización desde la nube (nube -> local) --------------------------

def _ib(v) -> int:
    """bool/valor de Postgres -> 0/1 de SQLite."""
    return 1 if v else 0


def _txt(v) -> str:
    """Decimal/numérico de Postgres -> texto (mantiene precisión)."""
    return str(v)


def _ts(v) -> str:
    """datetime de Postgres -> ISO8601 texto."""
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _txt_null(v):
    """Numérico opcional de Postgres -> texto o None."""
    return str(v) if v is not None else None


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Aplica un producto traído de Neon.

    Si ya existe localmente, actualiza SOLO catálogo y precios: NUNCA toca
    stock_actual, porque el stock es autoritativo en el local (lo descuentan
    las ventas). Si es nuevo, lo inserta completo (incluido su stock inicial)."""
    existe = conn.execute(
        "SELECT 1 FROM productos WHERE id = ?", (fila["id"],)
    ).fetchone()

    if existe:
        conn.execute(
            """UPDATE productos SET
                 codigo_barra = ?, nombre = ?, categoria_id = ?, es_pesable = ?,
                 unidad_medida = ?, precio_venta = ?, costo_compra = ?,
                 margen_pct = ?, stock_minimo = ?, controla_stock = ?,
                 controla_vencimiento = ?, activo = ?, updated_at = ?
               WHERE id = ?""",
            (fila["codigo_barra"], fila["nombre"], fila["categoria_id"],
             _ib(fila["es_pesable"]), fila["unidad_medida"],
             _txt(fila["precio_venta"]), _txt(fila["costo_compra"]),
             _txt_null(fila.get("margen_pct")), _txt(fila["stock_minimo"]),
             _ib(fila["controla_stock"]), _ib(fila["controla_vencimiento"]),
             _ib(fila["activo"]), _ts(fila["updated_at"]), fila["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO productos
                 (id, codigo_barra, nombre, categoria_id, es_pesable, unidad_medida,
                  precio_venta, costo_compra, margen_pct, stock_actual, stock_minimo,
                  controla_stock, controla_vencimiento, activo, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fila["id"], fila["codigo_barra"], fila["nombre"], fila["categoria_id"],
             _ib(fila["es_pesable"]), fila["unidad_medida"],
             _txt(fila["precio_venta"]), _txt(fila["costo_compra"]),
             _txt_null(fila.get("margen_pct")), _txt(fila["stock_actual"]),
             _txt(fila["stock_minimo"]), _ib(fila["controla_stock"]),
             _ib(fila["controla_vencimiento"]), _ib(fila["activo"]),
             _ts(fila["updated_at"])),
        )
