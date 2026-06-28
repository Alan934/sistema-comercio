"""Demo por consola del motor de ventas (sin UI).
Ejecutar desde la raíz:  python demo_pos.py

Simula:
  1) Escaneo de un producto por unidad (Coca) -> se agrega x2.
  2) Producto pesable (Queso) -> se ingresa el peso 0.750 kg.
  3) Pago dividido: efectivo + transferencia.
  4) Una segunda venta FIADA a un cliente (cuenta corriente).
"""
from decimal import Decimal

from app.core import db_local
from app.core.utils import ahora_iso, nuevo_id
from app.models.carrito import Carrito
from app.models.venta import Pago, EFECTIVO, TRANSFERENCIA, FIADO
from app.services import venta_service
from app.repositories import venta_repo

# IDs fijos para que el demo sea repetible (INSERT OR REPLACE los resetea).
ID_COCA = "demo-coca-500"
ID_QUESO = "demo-queso-kg"
ID_CLIENTE = "demo-cliente-juan"
COD_COCA = "7790895000270"
COD_QUESO = "2000001000005"


def sembrar_datos():
    """Carga productos y un cliente de prueba con stock conocido."""
    conn = db_local.connect()
    ahora = ahora_iso()
    try:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO productos
                   (id, codigo_barra, nombre, es_pesable, unidad_medida,
                    precio_venta, costo_compra, stock_actual, stock_minimo,
                    controla_stock, controla_vencimiento, activo, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ID_COCA, COD_COCA, "Coca-Cola 500ml", 0, "UN",
                 "1200.00", "800.00", "24", "6", 1, 0, 1, ahora),
            )
            conn.execute(
                """INSERT OR REPLACE INTO productos
                   (id, codigo_barra, nombre, es_pesable, unidad_medida,
                    precio_venta, costo_compra, stock_actual, stock_minimo,
                    controla_stock, controla_vencimiento, activo, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ID_QUESO, COD_QUESO, "Queso cremoso", 1, "KG",
                 "8500.00", "6000.00", "5.000", "1.000", 1, 1, 1, ahora),
            )
            conn.execute(
                """INSERT OR REPLACE INTO clientes
                   (id, nombre, telefono, limite_credito, saldo_cuenta, activo, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (ID_CLIENTE, "Juan (fiado)", "2611234567", "20000.00", "0.00", 1, ahora),
            )
    finally:
        conn.close()


def stock_de(producto_id) -> str:
    conn = db_local.connect()
    try:
        row = conn.execute(
            "SELECT nombre, stock_actual FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        return f"{row['nombre']}: {row['stock_actual']}"
    finally:
        conn.close()


def main():
    db_local.init_db()
    sembrar_datos()
    print("== DEMO MOTOR DE VENTAS ==\n")
    print("Stock inicial:")
    print("  -", stock_de(ID_COCA))
    print("  -", stock_de(ID_QUESO))

    # ----- VENTA 1: contado, pago dividido -----
    carrito = Carrito()

    coca = venta_service.buscar_por_codigo(COD_COCA)        # "pistolita"
    carrito.agregar(coca, Decimal("1"))
    carrito.agregar(coca, Decimal("1"))                     # escaneada de nuevo -> x2

    queso = venta_service.buscar_por_codigo(COD_QUESO)
    carrito.agregar(queso, Decimal("0.750"))               # peso ingresado a mano

    print("\nVenta 1 - carrito:")
    for it in carrito.items:
        print(f"  {it.cantidad} x {it.descripcion} @ ${it.precio_unitario} = ${it.subtotal}")
    print(f"  TOTAL: ${carrito.total}")

    # Coca: 2 x 1200 = 2400 ; Queso: 0.750 x 8500 = 6375 ; Total = 8775
    pagos = [Pago(EFECTIVO, Decimal("5000.00")),
             Pago(TRANSFERENCIA, Decimal("3775.00"))]
    venta_id = venta_service.registrar_venta(carrito, pagos)
    print(f"  -> Venta registrada OK (id {venta_id[:8]}...)")

    # ----- VENTA 2: fiada a cliente -----
    carrito2 = Carrito()
    carrito2.agregar(venta_service.buscar_por_codigo(COD_COCA), Decimal("3"))
    total2 = carrito2.total
    venta_service.registrar_venta(
        carrito2, [Pago(FIADO, total2)], cliente_id=ID_CLIENTE
    )
    print(f"\nVenta 2 - FIADA a Juan por ${total2}")

    # ----- Verificaciones -----
    print("\nStock final (debe haber bajado):")
    print("  -", stock_de(ID_COCA), "(24 - 2 - 3 = 19)")
    print("  -", stock_de(ID_QUESO), "(5.000 - 0.750 = 4.250)")

    conn = db_local.connect()
    try:
        saldo = conn.execute(
            "SELECT saldo_cuenta FROM clientes WHERE id = ?", (ID_CLIENTE,)
        ).fetchone()["saldo_cuenta"]
        print(f"\nSaldo cuenta corriente Juan (lo que nos debe): ${saldo}")
        print("Ventas pendientes de sincronizar:",
              venta_repo.contar_pendientes_sync(conn))
    finally:
        conn.close()

    print("\n== Motor de ventas funcionando ==")


if __name__ == "__main__":
    main()
