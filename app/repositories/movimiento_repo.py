"""Acceso a datos del libro de movimientos de stock (ledger).

Cada cambio de stock deja aquí una fila inmutable con la cantidad CON SIGNO
(+ entra, − sale). El stock_actual del producto es una caché = suma de estos
deltas. Sincronizando estas filas entre PCs (idempotente por id UUID) el stock
converge sin que una PC pise el número de otra.

Todas las funciones reciben la conexión para participar de la transacción del
service que las llama (venta, compra, despiece)."""
import sqlite3
from decimal import Decimal

from app.core.utils import ahora_iso, ahora_local, nuevo_id

# Tipos de movimiento (metadata para trazabilidad / reportes tipo kardex).
VENTA = "VENTA"
COMPRA = "COMPRA"
DESPIECE = "DESPIECE"
ALTA = "ALTA"
AJUSTE = "AJUSTE"


def registrar(conn: sqlite3.Connection, producto_id: str, cantidad: Decimal,
              tipo: str, referencia_id: str | None = None) -> None:
    """Anota un movimiento de stock. `cantidad` va CON SIGNO (negativa = salida).
    Queda sincronizado=0 para que el sync lo suba a la nube."""
    conn.execute(
        "INSERT INTO movimientos_stock "
        "(id, producto_id, fecha, tipo, cantidad, referencia_id, "
        " sincronizado, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
        (nuevo_id(), producto_id, ahora_local(), tipo, str(cantidad),
         referencia_id, ahora_iso()),
    )


# --- Sincronización ---------------------------------------------------------

def _ts(v) -> str:
    """datetime de Postgres -> ISO8601 texto (o pasa el texto tal cual)."""
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Movimientos aún no subidos a la nube."""
    return conn.execute(
        "SELECT * FROM movimientos_stock WHERE sincronizado = 0"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, mov_id: str) -> None:
    conn.execute(
        "UPDATE movimientos_stock SET sincronizado = 1 WHERE id = ?", (mov_id,)
    )


def aplicar_desde_nube(conn: sqlite3.Connection, fila: dict) -> bool:
    """Aplica un movimiento traído de Neon que esta PC todavía no tiene: lo
    inserta (ya sincronizado) y suma su delta al stock_actual del producto.

    Idempotente por id (UUID): si el movimiento ya existe localmente, no hace
    nada. Si el producto aún no bajó a esta PC, se saltea (se aplicará en el
    próximo ciclo, una vez que _pull_catalogo lo haya insertado). Devuelve True
    si aplicó el delta."""
    ya = conn.execute(
        "SELECT 1 FROM movimientos_stock WHERE id = ?", (fila["id"],)
    ).fetchone()
    if ya is not None:
        return False
    prod = conn.execute(
        "SELECT stock_actual FROM productos WHERE id = ?", (fila["producto_id"],)
    ).fetchone()
    if prod is None:
        return False  # el producto todavía no existe local: reintentar luego
    cantidad = Decimal(str(fila["cantidad"]))
    conn.execute(
        "INSERT INTO movimientos_stock "
        "(id, producto_id, fecha, tipo, cantidad, referencia_id, "
        " sincronizado, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
        (fila["id"], fila["producto_id"], _ts(fila["fecha"]), fila["tipo"],
         str(cantidad), fila.get("referencia_id"), _ts(fila["created_at"])),
    )
    nuevo = Decimal(str(prod["stock_actual"])) + cantidad
    conn.execute(
        "UPDATE productos SET stock_actual = ? WHERE id = ?",
        (str(nuevo), fila["producto_id"]),
    )
    return True
