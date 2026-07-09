"""E2E del ledger de stock contra Neon REAL.

Ejercita las funciones reales de sync (_push_movimientos / _pull_movimientos)
contra la nube, usando un producto de DESCARTE y bases locales TEMPORALES. NO
toca la base de esta PC ni el stock real. Al terminar borra sus filas de prueba
de Neon.

Uso:  python demo_sync_stock.py   (con el .env y su NEON_DATABASE_URL presente)
"""
import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path

from app.core import db_cloud, sync_manager
from app.repositories import producto_repo, movimiento_repo
from config import settings

PROD = "E2E-TEST-PROD"   # producto de descarte; por acá limpiamos al final
CAT = "E2E-TEST-CAT"


def _pc_temp() -> sqlite3.Connection:
    """Una base local SQLite temporal con el esquema, más un producto de
    descarte en stock 0 (para que el pull pueda aplicarle el delta)."""
    ruta = Path(tempfile.mkdtemp()) / "pc.db"
    c = sqlite3.connect(str(ruta))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(settings.SCHEMA_LOCAL_PATH.read_text(encoding="utf-8"))
    c.execute("INSERT INTO categorias(id,nombre,updated_at) VALUES(?,?,?)",
              (CAT, "E2E", "2026-01-01"))
    c.execute("INSERT INTO productos(id,codigo_barra,nombre,categoria_id,"
              "stock_actual,updated_at) VALUES(?,?,?,?,?,?)",
              (PROD, None, "Producto E2E", CAT, "0", "2026-01-01"))
    c.commit()
    return c


def main() -> None:
    if not db_cloud.disponible():
        print("[X] Nube no configurada: falta psycopg o NEON_DATABASE_URL en .env")
        return

    print("Conectando a Neon...")
    cloud = db_cloud.connect()
    try:
        db_cloud.asegurar_schema(cloud)
        print("[OK] Esquema asegurado (tabla movimientos_stock existe en Neon)")

        # Por las dudas, limpiamos restos de una corrida anterior.
        with cloud.cursor() as cur:
            cur.execute("DELETE FROM movimientos_stock WHERE producto_id = %s",
                        (PROD,))

        # --- PC1: genera un movimiento pendiente y lo SUBE -------------------
        pc1 = _pc_temp()
        producto_repo.aumentar_stock(pc1, PROD, Decimal("7.500"),
                                     referencia_id="e2e-remito")
        pc1.commit()
        subidos = sync_manager._push_movimientos(pc1, cloud)
        print(f"[OK] PUSH: {subidos} movimiento(s) subido(s) a Neon")

        # Verificar que llegó, con los tipos correctos.
        with cloud.cursor() as cur:
            cur.execute("SELECT tipo, cantidad FROM movimientos_stock "
                        "WHERE producto_id = %s", (PROD,))
            fila = cur.fetchone()
        assert fila is not None, "el movimiento no llegó a Neon"
        assert fila[0] == "COMPRA", f"tipo inesperado: {fila[0]}"
        assert Decimal(str(fila[1])) == Decimal("7.500"), f"cantidad: {fila[1]}"
        print(f"  en Neon: tipo={fila[0]} cantidad={fila[1]} (tipos OK)")

        # --- PC2: PC 'nueva' que BAJA el movimiento y aplica el delta --------
        pc2 = _pc_temp()
        bajados = sync_manager._pull_movimientos(pc2, cloud)
        stock2 = Decimal(str(pc2.execute(
            "SELECT stock_actual FROM productos WHERE id = ?", (PROD,)
        ).fetchone()["stock_actual"]))
        print(f"[OK] PULL: {bajados} movimiento(s) aplicado(s); stock PC2 = {stock2}")
        assert stock2 == Decimal("7.500"), "el delta no se aplicó bien"

        # Idempotencia: volver a bajar no debe re-aplicar.
        rebaj = sync_manager._pull_movimientos(pc2, cloud)
        stock2b = Decimal(str(pc2.execute(
            "SELECT stock_actual FROM productos WHERE id = ?", (PROD,)
        ).fetchone()["stock_actual"]))
        assert rebaj == 0 and stock2b == Decimal("7.500"), "pull no es idempotente"
        print(f"[OK] IDEMPOTENCIA: segundo pull aplicó {rebaj}; stock sigue {stock2b}")

        print("\n[OK] E2E OK: el ledger sincroniza correctamente contra Neon real.")
    finally:
        # Limpieza: borrar SOLO las filas de prueba de Neon.
        try:
            with cloud.cursor() as cur:
                cur.execute("DELETE FROM movimientos_stock WHERE producto_id = %s",
                            (PROD,))
            print("Limpieza: filas de prueba borradas de Neon.")
        except Exception as e:  # noqa: BLE001
            print(f"(No se pudo limpiar Neon automáticamente: {e})")
        cloud.close()


if __name__ == "__main__":
    main()
