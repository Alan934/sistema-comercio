"""Punto de entrada de la aplicación. Ejecutar desde la raíz:  python main.py

Requisitos: pip install -r requirements.txt  (CustomTkinter).
La primera vez crea la base local y, si está vacía, siembra unos productos
y un cliente de ejemplo para poder probar la caja enseguida.
"""
from app.core import db_local
from app.core.utils import ahora_iso


def _sembrar_si_vacio() -> None:
    """Carga datos de ejemplo solo si todavía no hay productos."""
    conn = db_local.connect()
    try:
        n = conn.execute("SELECT COUNT(*) AS n FROM productos").fetchone()["n"]
        if n > 0:
            return
        ahora = ahora_iso()
        with conn:
            conn.executemany(
                """INSERT INTO productos
                   (id, codigo_barra, nombre, es_pesable, unidad_medida,
                    precio_venta, costo_compra, stock_actual, stock_minimo,
                    controla_stock, controla_vencimiento, activo, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    ("seed-coca", "7790895000270", "Coca-Cola 500ml", 0, "UN",
                     "1200.00", "800.00", "24", "6", 1, 0, 1, ahora),
                    ("seed-agua", "7790895000287", "Agua mineral 500ml", 0, "UN",
                     "800.00", "500.00", "30", "6", 1, 0, 1, ahora),
                    ("seed-alfajor", "7790040000019", "Alfajor triple", 0, "UN",
                     "950.00", "600.00", "40", "10", 1, 0, 1, ahora),
                    ("seed-queso", "2000001000005", "Queso cremoso", 1, "KG",
                     "8500.00", "6000.00", "5.000", "1.000", 1, 1, 1, ahora),
                    ("seed-jamon", "2000002000002", "Jamón cocido", 1, "KG",
                     "12000.00", "8500.00", "3.000", "0.500", 1, 1, 1, ahora),
                ],
            )
            conn.execute(
                """INSERT INTO clientes
                   (id, nombre, telefono, limite_credito, saldo_cuenta, activo, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                ("seed-juan", "Juan Pérez", "2611234567", "20000.00", "0.00", 1, ahora),
            )
    finally:
        conn.close()


def main() -> None:
    db_local.init_db()
    _sembrar_si_vacio()
    # Import diferido: solo se necesita CustomTkinter al levantar la GUI.
    from app.ui.app_window import AppWindow
    AppWindow().mainloop()


if __name__ == "__main__":
    main()
