"""Acceso a datos de productos. Todas las funciones reciben la conexión
para poder participar de una transacción más grande (ej. una venta)."""
import sqlite3
from decimal import Decimal

from app.core import pricing
from app.core.utils import ahora_iso
from app.models.producto import Producto
from app.repositories import movimiento_repo

_COLS = ("id, codigo_barra, nombre, es_pesable, unidad_medida, "
         "precio_venta, costo_compra, stock_actual, controla_stock, activo, "
         "categoria_id, margen_pct, ubicacion, controla_vencimiento, stock_minimo")


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
        ubicacion=row["ubicacion"],
        controla_vencimiento=bool(row["controla_vencimiento"]),
        stock_minimo=Decimal(str(row["stock_minimo"])),
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
              costo_compra, precio_venta, margen_pct, ubicacion, stock_actual,
              stock_minimo, controla_stock, controla_vencimiento, activo, updated_at)
           VALUES
             (:id, :codigo_barra, :nombre, :categoria_id, :es_pesable, :unidad_medida,
              :costo_compra, :precio_venta, :margen_pct, :ubicacion, :stock_actual,
              :stock_minimo, :controla_stock, :controla_vencimiento, :activo, :updated_at)""",
        datos,
    )
    # Stock inicial del alta: deja su movimiento para que viaje a las demás PCs.
    inicial = Decimal(str(datos.get("stock_actual", "0")))
    if inicial != 0:
        movimiento_repo.registrar(conn, datos["id"], inicial,
                                  movimiento_repo.ALTA, datos["id"])


def actualizar(conn: sqlite3.Connection, datos: dict) -> None:
    """Edita catálogo y precios. No toca stock_actual (eso va por compras/ventas)."""
    conn.execute(
        """UPDATE productos SET
             codigo_barra = :codigo_barra, nombre = :nombre,
             categoria_id = :categoria_id, es_pesable = :es_pesable,
             unidad_medida = :unidad_medida, costo_compra = :costo_compra,
             precio_venta = :precio_venta, margen_pct = :margen_pct,
             ubicacion = :ubicacion, stock_minimo = :stock_minimo,
             controla_stock = :controla_stock,
             controla_vencimiento = :controla_vencimiento,
             activo = :activo, sincronizado = 0, updated_at = :updated_at
           WHERE id = :id""",
        datos,
    )


def aumentar_stock(conn: sqlite3.Connection, producto_id: str, cantidad,
                   tipo: str = movimiento_repo.COMPRA,
                   referencia_id: str | None = None) -> None:
    """Suma stock (al recibir un remito o confirmar un despiece). Lee/reescribe
    en Decimal y anota el movimiento (delta positivo) en el ledger."""
    row = conn.execute(
        "SELECT stock_actual FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Producto inexistente: {producto_id}")
    cantidad = Decimal(str(cantidad))
    nuevo = Decimal(str(row["stock_actual"])) + cantidad
    conn.execute(
        "UPDATE productos SET stock_actual = ?, sincronizado = 0, updated_at = ? "
        "WHERE id = ?",
        (str(nuevo), ahora_iso(), producto_id),
    )
    movimiento_repo.registrar(conn, producto_id, cantidad, tipo, referencia_id)


def ajustar_stock(conn: sqlite3.Connection, producto_id: str, nuevo_stock,
                  referencia_id: str | None = None) -> None:
    """Fija el stock a un valor ABSOLUTO (ajuste manual desde la edición del
    producto). Calcula la diferencia con el stock actual y la anota con signo en
    el ledger como AJUSTE, para que la corrección viaje al resto de las PCs (el
    stock se reconstruye sumando el ledger). Si no cambia, no hace nada."""
    row = conn.execute(
        "SELECT stock_actual FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Producto inexistente: {producto_id}")
    objetivo = Decimal(str(nuevo_stock))
    delta = objetivo - Decimal(str(row["stock_actual"]))
    if delta == 0:
        return
    conn.execute(
        "UPDATE productos SET stock_actual = ?, sincronizado = 0, updated_at = ? "
        "WHERE id = ?",
        (str(objetivo), ahora_iso(), producto_id),
    )
    movimiento_repo.registrar(conn, producto_id, delta,
                              movimiento_repo.AJUSTE, referencia_id)


def actualizar_costo(conn: sqlite3.Connection, producto_id: str, costo) -> None:
    """Actualiza el costo de compra con el del último remito recibido."""
    conn.execute(
        "UPDATE productos SET costo_compra = ?, sincronizado = 0, updated_at = ? "
        "WHERE id = ?",
        (str(costo), ahora_iso(), producto_id),
    )


def actualizar_precio(conn: sqlite3.Connection, producto_id: str, precio) -> None:
    """Fija el precio de venta directamente (sin recalcular por margen). Lo usa
    el despiece: cada corte define su propio precio/kg."""
    conn.execute(
        "UPDATE productos SET precio_venta = ?, sincronizado = 0, updated_at = ? "
        "WHERE id = ?",
        (str(precio), ahora_iso(), producto_id),
    )


def ubicaciones_distintas(conn: sqlite3.Connection) -> list[str]:
    """Ubicaciones ya usadas (para sugerir y filtrar)."""
    return [r["ubicacion"] for r in conn.execute(
        "SELECT DISTINCT ubicacion FROM productos "
        "WHERE ubicacion IS NOT NULL AND TRIM(ubicacion) <> '' "
        "ORDER BY ubicacion").fetchall()]


def ids_por_categoria(conn: sqlite3.Connection, categoria_id: str) -> list[str]:
    return [r["id"] for r in conn.execute(
        "SELECT id FROM productos WHERE categoria_id = ?", (categoria_id,)).fetchall()]


def contar_activos_por_categoria(conn: sqlite3.Connection, categoria_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS n FROM productos WHERE categoria_id = ? AND activo = 1",
        (categoria_id,)).fetchone()["n"]


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
        "UPDATE productos SET precio_venta = ?, sincronizado = 0, updated_at = ? "
        "WHERE id = ?",
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
                    cantidad: Decimal, tipo: str = movimiento_repo.VENTA,
                    referencia_id: str | None = None) -> None:
    """Resta del stock leyendo y reescribiendo en Decimal (texto) para no
    perder precisión con pesos como 0.750. Permite stock negativo a propósito:
    en un kiosko nunca se bloquea una venta por stock desactualizado.
    Anota el movimiento (delta negativo) en el ledger."""
    row = conn.execute(
        "SELECT stock_actual FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Producto inexistente: {producto_id}")
    cantidad = Decimal(str(cantidad))
    nuevo_stock = Decimal(str(row["stock_actual"])) - cantidad
    conn.execute(
        "UPDATE productos SET stock_actual = ?, sincronizado = 0, updated_at = ? "
        "WHERE id = ?",
        (str(nuevo_stock), ahora_iso(), producto_id),
    )
    movimiento_repo.registrar(conn, producto_id, -cantidad, tipo, referencia_id)


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


def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM productos WHERE sincronizado = 0"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, producto_id: str) -> None:
    conn.execute(
        "UPDATE productos SET sincronizado = 1 WHERE id = ?", (producto_id,)
    )


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Aplica un producto traído de Neon.

    - Si el producto local tiene cambios pendientes de subir (sincronizado=0),
      NO se pisa: gana lo local hasta que suba (evita perder ediciones).
    - Si ya existe y está sincronizado, actualiza el catálogo PERO conserva el
      stock_actual local (lo maneja el ledger de movimientos, no este pull).
    - Si es nuevo (PC nueva / restaurada), se inserta con stock 0: el stock lo
      reconstruye después _pull_movimientos sumando el ledger de la nube. Así el
      libro de movimientos es la ÚNICA autoridad del stock y nunca se cuenta
      doble (snapshot + ledger). Queda marcado como sincronizado."""
    actual = conn.execute(
        "SELECT sincronizado FROM productos WHERE id = ?", (fila["id"],)
    ).fetchone()

    if actual is not None and actual["sincronizado"] == 0:
        return  # cambios locales sin subir: no pisar

    if actual is not None:
        conn.execute(
            """UPDATE productos SET
                 codigo_barra = ?, nombre = ?, categoria_id = ?, es_pesable = ?,
                 unidad_medida = ?, precio_venta = ?, costo_compra = ?,
                 margen_pct = ?, ubicacion = ?, stock_minimo = ?, controla_stock = ?,
                 controla_vencimiento = ?, activo = ?, sincronizado = 1, updated_at = ?
               WHERE id = ?""",
            (fila["codigo_barra"], fila["nombre"], fila["categoria_id"],
             _ib(fila["es_pesable"]), fila["unidad_medida"],
             _txt(fila["precio_venta"]), _txt(fila["costo_compra"]),
             _txt_null(fila.get("margen_pct")), fila.get("ubicacion"),
             _txt(fila["stock_minimo"]),
             _ib(fila["controla_stock"]), _ib(fila["controla_vencimiento"]),
             _ib(fila["activo"]), _ts(fila["updated_at"]), fila["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO productos
                 (id, codigo_barra, nombre, categoria_id, es_pesable, unidad_medida,
                  precio_venta, costo_compra, margen_pct, ubicacion, stock_actual,
                  stock_minimo, controla_stock, controla_vencimiento, activo,
                  sincronizado, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
            (fila["id"], fila["codigo_barra"], fila["nombre"], fila["categoria_id"],
             _ib(fila["es_pesable"]), fila["unidad_medida"],
             _txt(fila["precio_venta"]), _txt(fila["costo_compra"]),
             _txt_null(fila.get("margen_pct")), fila.get("ubicacion"),
             "0",  # stock lo reconstruye _pull_movimientos desde el ledger
             _txt(fila["stock_minimo"]), _ib(fila["controla_stock"]),
             _ib(fila["controla_vencimiento"]), _ib(fila["activo"]),
             _ts(fila["updated_at"])),
        )
