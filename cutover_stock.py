"""Cutover a "stock por ledger" (Camino B).

Pone el stock de todos los productos en 0 y vacía el libro de movimientos, en
la base LOCAL de esta PC y —con --nube— también en Neon. Es un paso de puesta
en marcha que se corre UNA sola vez: después se carga el stock real por alta o
remito y, con el ledger ya activo, las PCs convergen solas.

Uso:
    python cutover_stock.py            # solo la base local de esta PC
    python cutover_stock.py --nube     # además limpia Neon (correr en UNA PC)

IMPORTANTE (orden del cutover):
    1. Cerrá la app en TODAS las PCs.
    2. Corré este script en cada PC (una de ellas con --nube para limpiar Neon).
    3. RECIÉN AHÍ abrí la app y empezá a cargar el stock real.
   Si una PC ya empezó a cargar stock y otra corre --nube después, se borra ese
   avance. Por eso el reset se hace en todas ANTES de cargar nada.

Nota: solo toca el stock. Productos, categorías, clientes, ventas, etc. quedan
intactos.
"""
import sys

from app.core import db_local, db_cloud


def _reset_local() -> None:
    # Asegura el esquema (crea movimientos_stock si la base es anterior al
    # ledger). init_db es idempotente: CREATE IF NOT EXISTS, no toca datos.
    db_local.init_db()
    conn = db_local.connect()
    try:
        with conn:  # transacción: o se hace todo o nada
            prods = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
            movs = conn.execute(
                "SELECT COUNT(*) FROM movimientos_stock").fetchone()[0]
            conn.execute("UPDATE productos SET stock_actual = '0'")
            conn.execute("DELETE FROM movimientos_stock")
        print(f"Local: {prods} productos puestos en stock 0; "
              f"{movs} movimientos borrados.")
    finally:
        conn.close()


def _reset_nube() -> None:
    if not db_cloud.disponible():
        print("Nube no configurada (falta psycopg o NEON_DATABASE_URL): se omite.")
        return
    conn = db_cloud.connect()
    try:
        db_cloud.asegurar_schema(conn)
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("UPDATE productos SET stock_actual = 0")
                cur.execute("DELETE FROM movimientos_stock")
        print("Neon: stock de productos en 0 y movimientos_stock vaciado.")
    finally:
        conn.close()


if __name__ == "__main__":
    _reset_local()
    if "--nube" in sys.argv:
        _reset_nube()
    print("Listo. Abrí la app, cargá el stock real y ya queda sincronizado "
          "por ledger entre las PCs.")
