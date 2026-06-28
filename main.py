"""Punto de entrada. Por ahora hace una PRUEBA DE HUMO del core:
crea la base local, verifica las tablas y hace un insert/select de prueba.

Más adelante, este archivo levantará la GUI de CustomTkinter.
Ejecutar desde la raíz del proyecto:  python main.py
"""
from decimal import Decimal

from app.core import db_local, network
from app.core.utils import nuevo_id, ahora_iso
from config import settings


def prueba_de_humo() -> None:
    print(f"== {settings.APP_NOMBRE} v{settings.APP_VERSION} - prueba de humo del core ==\n")

    # 1) Crear/abrir la base local
    db_local.init_db()
    print(f"[OK] Base local lista en: {settings.LOCAL_DB_PATH}")

    # 2) Verificar tablas creadas
    tablas = db_local.listar_tablas()
    print(f"[OK] {len(tablas)} tablas: {', '.join(tablas)}")

    # 3) Insert/select de prueba (idempotente por codigo_barra UNIQUE)
    conn = db_local.connect()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO productos
               (id, codigo_barra, nombre, precio_venta, costo_compra, stock_actual, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (nuevo_id(), "7790000000017", "Producto de prueba",
             str(Decimal("1500.00")), str(Decimal("900.00")),
             str(Decimal("10")), ahora_iso()),
        )
        conn.commit()
        fila = conn.execute(
            "SELECT nombre, precio_venta, stock_actual FROM productos "
            "WHERE codigo_barra = ?",
            ("7790000000017",),
        ).fetchone()
        print(f"[OK] Producto leido: {fila['nombre']} "
              f"${fila['precio_venta']} (stock {fila['stock_actual']})")
    finally:
        conn.close()

    # 4) Estado de conectividad (no es error si no hay internet)
    online = network.hay_internet()
    print(f"[OK] Conectividad a internet: {'SI' if online else 'NO (modo offline)'}")

    print("\n== Core funcionando correctamente ==")


if __name__ == "__main__":
    prueba_de_humo()
