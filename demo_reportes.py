"""Demo por consola de Reportes + Gastos (sin UI).
Ejecutar desde la raiz:  python demo_reportes.py

Usa las ventas/compras que ya generaron los otros demos y agrega unos gastos,
luego arma los reportes del ultimo mes.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.core import db_local
from app.models.gasto import FIJO, VARIABLE
from app.services import gasto_service, reporte_service, proveedor_service


def main():
    db_local.init_db()
    print("== DEMO REPORTES + GASTOS ==\n")

    # Un proveedor para asociar un gasto (si hay alguno cargado).
    proveedores = proveedor_service.listar_activos()
    prov_id = proveedores[0].id if proveedores else None
    prov_nombre = proveedores[0].nombre if proveedores else "(ninguno)"

    # Alta de gastos.
    gasto_service.crear_gasto(FIJO, "Alquiler del local", Decimal("150000.00"))
    gasto_service.crear_gasto(VARIABLE, "Boleta de luz", Decimal("45000.00"))
    gasto_service.crear_gasto(VARIABLE, "Flete de mercaderia",
                              Decimal("12000.00"), proveedor_id=prov_id)
    print(f"Gastos cargados (uno asociado a: {prov_nombre})\n")

    hasta = date.today()
    desde = hasta - timedelta(days=30)

    r = reporte_service.resumen(desde, hasta)
    print(f"--- RESUMEN {desde} a {hasta} ---")
    print(f"  Ventas:          {r['ventas_cantidad']}")
    print(f"  Total vendido:   ${r['total_vendido']}")
    print(f"  Costo total:     ${r['costo_total']}")
    print(f"  Ganancia bruta:  ${r['ganancia_bruta']}  (venta - costo)")
    print(f"  Gastos:          ${r['gastos_total']}")
    print(f"  GANANCIA NETA:   ${r['ganancia_neta']}  (bruta - gastos)")

    print("\n--- GASTOS POR TIPO ---")
    for g in reporte_service.gastos_por_tipo(desde, hasta):
        print(f"  {g['tipo']}: ${g['total']}")

    print("\n--- VENTAS POR METODO DE PAGO ---")
    for m in reporte_service.ventas_por_metodo(desde, hasta):
        print(f"  {m['metodo']}: ${m['total']}")

    print("\n--- TOP PRODUCTOS (por facturacion) ---")
    for t in reporte_service.top_productos(desde, hasta, 5):
        print(f"  {t['producto']}: {t['cantidad']} u  ->  ${t['total']}")

    print("\n--- POR PROVEEDOR ---")
    pp = reporte_service.por_proveedor(desde, hasta)
    print("  Compras:")
    for c in pp["compras"]:
        print(f"    {c['proveedor']}: ${c['total']}")
    print("  Gastos:")
    for g in pp["gastos"]:
        print(f"    {g['proveedor']}: ${g['total']}")

    print("\n== Reportes + Gastos funcionando ==")


if __name__ == "__main__":
    main()
