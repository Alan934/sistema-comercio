"""Demo por consola de Stock + Compras + Proveedores (sin UI).
Ejecutar desde la raiz:  python demo_stock.py

Simula:
  1) Alta de un proveedor.
  2) Alta de un producto sin stock y recepcion de un remito CONTADO
     (sube stock y actualiza costo).
  3) Segundo remito a CUENTA CORRIENTE (suma deuda con el proveedor).
  4) Pago parcial al proveedor (baja la deuda).
  5) Producto perecedero con vencimiento -> crea lote -> alerta de vencimiento.
  6) Alerta de stock bajo.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.core import db_local
from app.models.compra import ItemCompra, CONTADO, CUENTA_CORRIENTE
from app.services import stock_service, compra_service, proveedor_service


def _producto(pid):
    conn = db_local.connect()
    try:
        row = conn.execute(
            "SELECT nombre, stock_actual, costo_compra FROM productos WHERE id = ?",
            (pid,)).fetchone()
        return f"{row['nombre']}: stock={row['stock_actual']} costo=${row['costo_compra']}"
    finally:
        conn.close()


def _saldo_prov(prov_id):
    conn = db_local.connect()
    try:
        return conn.execute(
            "SELECT saldo_cuenta FROM proveedores WHERE id = ?",
            (prov_id,)).fetchone()["saldo_cuenta"]
    finally:
        conn.close()


def main():
    db_local.init_db()
    print("== DEMO STOCK + COMPRAS + PROVEEDORES ==\n")

    # 1) Proveedor
    prov = proveedor_service.crear("Distribuidora Sur", cuit="30-12345678-9",
                                   telefono="2614000000")
    print(f"Proveedor creado: Distribuidora Sur")

    # 2) Producto sin stock + remito CONTADO
    fideos = stock_service.crear_producto({
        "codigo_barra": "7790001112223", "nombre": "Fideos 500g",
        "precio_venta": "1500.00", "stock_actual": "0", "stock_minimo": "12",
    })
    print("\nProducto nuevo:", _producto(fideos))
    compra_service.registrar_compra(
        prov, [ItemCompra(fideos, Decimal("50"), Decimal("900.00"))],
        nro_remito="R-001", condicion=CONTADO)
    print("Tras remito R-001 (50u @ $900 contado):", _producto(fideos),
          "  (stock 0->50, costo ->900)")

    # 3) Remito a CUENTA CORRIENTE
    compra_service.registrar_compra(
        prov, [ItemCompra(fideos, Decimal("24"), Decimal("950.00"))],
        nro_remito="R-002", condicion=CUENTA_CORRIENTE)
    print("\nTras remito R-002 (24u @ $950 cta cte):", _producto(fideos))
    print(f"  Deuda con proveedor: ${_saldo_prov(prov)}  (24 x 950 = 22800)")

    # 4) Pago parcial al proveedor
    proveedor_service.registrar_pago(prov, Decimal("10000.00"))
    print(f"  Tras pagar $10000: deuda = ${_saldo_prov(prov)}  (22800 - 10000 = 12800)")

    # 5) Perecedero con vencimiento
    yogur = stock_service.crear_producto({
        "codigo_barra": "7790002223334", "nombre": "Yogur bebible",
        "precio_venta": "2200.00", "stock_actual": "0", "stock_minimo": "6",
        "controla_vencimiento": True,
    })
    venc = (date.today() + timedelta(days=3)).isoformat()
    compra_service.registrar_compra(
        prov, [ItemCompra(yogur, Decimal("10"), Decimal("1500.00"),
                          fecha_vencimiento=venc)],
        nro_remito="R-003", condicion=CONTADO)
    print("\nProducto perecedero recibido con vencimiento en 3 dias.")

    # 6) Producto con stock bajo
    stock_service.crear_producto({
        "nombre": "Lavandina 1L", "precio_venta": "1800.00",
        "stock_actual": "2", "stock_minimo": "6",
    })

    print("\n--- ALERTAS DE STOCK BAJO ---")
    for a in stock_service.alertas_stock_bajo():
        print(f"  {a['nombre']}: {a['stock_actual']} (minimo {a['stock_minimo']})")

    print("\n--- VENCIMIENTOS PROXIMOS (7 dias) ---")
    for a in stock_service.alertas_vencimientos(7):
        print(f"  {a['producto']}: vence {a['fecha_vencimiento']} "
              f"(en {a['dias_restantes']} dias), cantidad {a['cantidad']}")

    print("\n== Modulos de Stock y Proveedores funcionando ==")


if __name__ == "__main__":
    main()
