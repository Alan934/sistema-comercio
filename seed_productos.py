"""Carga masiva de productos de PRUEBA para medir rendimiento.

Genera N productos realistas de kiosko (200 por defecto) pasando por la lógica
real de alta (stock_service.crear_producto): crea categorías, aplica precios,
stock inicial y su movimiento en el ledger, y algunos con vencimiento.

TODO lo que crea queda MARCADO para poder borrarlo sin tocar tus datos reales:
  - Código de barra con prefijo  999xxxxxxxxxx
  - Categorías con nombre prefijado  "[Perf] ..."

Por defecto los productos de prueba se marcan como YA SINCRONIZADOS
(sincronizado=1): así el hilo de sync los IGNORA -> no suben a Neon, no llegan
a las otras PCs y --limpiar los borra sin que reaparezcan en el próximo pull.
Esto es clave porque la sincronización es solo upsert y NO propaga borrados:
si los dejaras subir, quedarían para siempre en la nube y en cada PC.
Usá --sincronizar solo si de verdad querés replicarlos a todas las máquinas.

Uso (desde la raíz del proyecto, PYTHONPATH=E:/Proyectos/kiosko):

    python seed_productos.py                 # carga 200, aislados del sync
    python seed_productos.py --cantidad 500  # carga 500
    python seed_productos.py --limpiar       # borra SOLO lo de prueba
    python seed_productos.py --sincronizar   # (avanzado) deja que suban a Neon
    python seed_productos.py --db ruta.db     # apunta a otra base (opcional)

IMPORTANTE: sin --db escribe en la MISMA base que usa la app (data/kiosko.db).
Eso es lo que se quiere para probar el rendimiento con la app real; para
deshacerlo, corré --limpiar.
"""
import argparse
import random
import sys
from decimal import Decimal
from datetime import date, timedelta
from pathlib import Path

MARCA_CODIGO = "999"          # prefijo de código de barra de los productos de prueba
MARCA_CAT = "[Perf] "         # prefijo de las categorías de prueba

# Rubros típicos de un kiosko/almacén con productos base y marcas para combinar.
RUBROS = {
    "Golosinas": (["Chupetín", "Chicle", "Caramelo", "Turrón", "Alfajor",
                   "Chocolate", "Oblea", "Gomitas", "Pastilla", "Bombón"],
                  ["Arcor", "Billiken", "Georgalos", "Felfort", "Misky",
                   "Bonobon", "Sugus", "Mogul"]),
    "Bebidas": (["Gaseosa", "Agua", "Jugo", "Cerveza", "Energizante",
                 "Agua saborizada", "Soda", "Tónica"],
                ["Coca", "Manaos", "Pritty", "Villavicencio", "Speed",
                 "Cepita", "Quilmes", "Brahma"]),
    "Almacén": (["Fideos", "Arroz", "Harina", "Azúcar", "Aceite", "Yerba",
                 "Puré de tomate", "Polenta", "Lentejas", "Sal"],
                ["Marolio", "Cañuelas", "Lucchetti", "Matarazzo", "Ledesma",
                 "Playadito", "Natura"]),
    "Lácteos": (["Leche", "Yogur", "Queso crema", "Manteca", "Dulce de leche",
                 "Crema", "Postre"],
                ["La Serenísima", "Ilolay", "Sancor", "Milkaut"]),
    "Limpieza": (["Lavandina", "Detergente", "Jabón", "Esponja", "Papel higiénico",
                  "Rollo cocina", "Suavizante", "Limpiador"],
                 ["Ayudín", "Magistral", "Ala", "Cif", "Elite", "Vívere"]),
    "Snacks": (["Papas fritas", "Palitos", "Maní", "Chizitos", "Nachos",
                "Tostadas", "Galletitas"],
               ["Lays", "Pehuamar", "Krachitos", "9 de Oro", "Bagley", "Terrabusi"]),
    "Fiambres": (["Jamón cocido", "Salame", "Mortadela", "Queso", "Bondiola",
                  "Panceta"],
                 ["Paladini", "Cagnoli", "La Piamontesa", "Calchaquí"]),
}
TAMANIOS = ["", "chico", "grande", "500g", "1kg", "2L", "1L", "x6", "familiar"]


def _generar(cantidad: int, nombres_existentes: set[str],
             idx_inicial: int) -> list[dict]:
    """Arma `cantidad` productos NUEVOS (que no estén en `nombres_existentes`)
    combinando rubro/base/marca/tamaño. Los códigos se numeran desde
    `idx_inicial` para no chocar con lo ya cargado (permite correr el seeder
    varias veces y que vaya sumando)."""
    # Se compara con el nombre NORMALIZADO (como lo guarda la app), si no el
    # dedupe entre corridas falla y se crean nombres repetidos.
    from app.core.utils import normalizar_nombre

    rnd = random.Random(1234)  # semilla fija: mismos productos en cada PC
    vistos: set[str] = set(nombres_existentes)
    productos: list[dict] = []
    rubros = list(RUBROS.items())
    i = 0
    idx = idx_inicial
    agotado = 0
    while len(productos) < cantidad:
        rubro, (bases, marcas) = rubros[i % len(rubros)]
        i += 1
        base = rnd.choice(bases)
        marca = rnd.choice(marcas)
        tam = rnd.choice(TAMANIOS)
        nombre = f"{base} {marca} {tam}".strip()
        clave = normalizar_nombre(nombre)
        if clave in vistos:
            agotado += 1
            if agotado > 200000:  # se agotaron las combinaciones posibles
                print(f"  Aviso: solo hay combinaciones para {len(productos)} "
                      "productos nuevos distintos.")
                break
            continue
        agotado = 0
        vistos.add(clave)
        n = idx
        idx += 1
        costo = Decimal(rnd.randrange(200, 8000))
        precio = (costo * Decimal("1.4")).quantize(Decimal("1"))
        pesable = rubro == "Fiambres"
        prod = {
            "rubro": rubro,
            "codigo_barra": f"{MARCA_CODIGO}{n:010d}",  # 999 + 10 dígitos
            "nombre": nombre,
            "costo_compra": str(costo),
            "precio_venta": str(precio),
            "stock_actual": str(rnd.randrange(0, 120)),
            "stock_minimo": str(rnd.choice([0, 3, 6, 12])),
            "es_pesable": pesable,
        }
        # 1 de cada 6 controla vencimiento (perecederos): lote a 3-30 días.
        if not pesable and n % 6 == 0:
            venc = date.today() + timedelta(days=rnd.randrange(3, 30))
            prod["controla_vencimiento"] = True
            prod["fecha_vencimiento"] = venc.isoformat()
            if Decimal(prod["stock_actual"]) == 0:
                prod["stock_actual"] = "10"  # que haya algo que venza
        productos.append(prod)
    return productos


def _marcar_como_sincronizado(conn) -> None:
    """Marca las filas de prueba como ya sincronizadas para que el hilo de sync
    NO las suba a Neon (así no contaminan la nube ni las otras PCs)."""
    conn.execute(
        "UPDATE productos SET sincronizado = 1 WHERE codigo_barra LIKE '999%'")
    conn.execute(
        "UPDATE categorias SET sincronizado = 1 WHERE nombre LIKE '[Perf] %'")
    conn.execute(
        "UPDATE lotes SET sincronizado = 1 WHERE producto_id IN "
        "(SELECT id FROM productos WHERE codigo_barra LIKE '999%')")
    conn.execute(
        "UPDATE movimientos_stock SET sincronizado = 1 WHERE producto_id IN "
        "(SELECT id FROM productos WHERE codigo_barra LIKE '999%')")


def sembrar(cantidad: int, sincronizar: bool = False) -> None:
    from app.core import db_local
    from app.services import stock_service, categoria_service

    db_local.init_db()
    print(f"== Sembrando {cantidad} productos de prueba ==")

    # Estado actual: qué productos de prueba ya existen (para ir sumando sin
    # chocar) y qué categorías [Perf] reutilizar.
    conn = db_local.connect()
    try:
        filas = conn.execute(
            "SELECT nombre, codigo_barra FROM productos "
            "WHERE codigo_barra LIKE '999%'").fetchall()
        nombres_existentes = {f["nombre"] for f in filas}
        indices = [int(f["codigo_barra"][3:]) for f in filas
                   if f["codigo_barra"][3:].isdigit()]
        idx_inicial = max(indices) + 1 if indices else 0
        cats_existentes = {f["nombre"]: f["id"] for f in conn.execute(
            "SELECT id, nombre FROM categorias WHERE nombre LIKE '[Perf] %'")}
    finally:
        conn.close()
    if nombres_existentes:
        print(f"  Ya hay {len(nombres_existentes)} productos de prueba; "
              f"se agregan {cantidad} mas.")

    # Categorías (una por rubro, prefijadas): reutiliza las que ya estén.
    cats: dict[str, str] = {}
    for rubro in RUBROS:
        nombre_cat = MARCA_CAT + rubro
        cats[rubro] = (cats_existentes.get(nombre_cat)
                       or categoria_service.crear(nombre_cat))

    productos = _generar(cantidad, nombres_existentes, idx_inicial)
    for k, p in enumerate(productos, 1):
        datos = {k2: v for k2, v in p.items() if k2 != "rubro"}
        datos["categoria_id"] = cats[p["rubro"]]
        stock_service.crear_producto(datos)
        if k % 50 == 0:
            print(f"  {k}/{cantidad}...")

    if not sincronizar:
        conn = db_local.connect()
        try:
            with conn:
                _marcar_como_sincronizado(conn)
        finally:
            conn.close()
        aviso = "aislados del sync (no suben a Neon ni a otras PCs)"
    else:
        aviso = "PENDIENTES de subir: se replicaran a Neon y a las demas PCs"

    print(f"Listo: +{len(productos)} productos de prueba (categorias: {len(cats)}).")
    print(f"Estado: {aviso}.")
    print("Para borrarlos todos:  python seed_productos.py --limpiar")


def limpiar() -> None:
    """Borra FÍSICAMENTE solo lo marcado como prueba (código 999*, cat [Perf]*)
    junto con sus lotes y movimientos de stock. No toca datos reales."""
    from app.core import db_local

    db_local.init_db()
    conn = db_local.connect()
    try:
        with conn:
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM productos WHERE codigo_barra LIKE '999%'")]
            if ids:
                marcas = ",".join("?" * len(ids))
                conn.execute(
                    f"DELETE FROM movimientos_stock WHERE producto_id IN ({marcas})",
                    ids)
                conn.execute(
                    f"DELETE FROM lotes WHERE producto_id IN ({marcas})", ids)
                conn.execute(
                    f"DELETE FROM productos WHERE id IN ({marcas})", ids)
            cats = conn.execute(
                "DELETE FROM categorias WHERE nombre LIKE '[Perf] %'").rowcount
        print(f"Borrados {len(ids)} productos y {cats} categorias de prueba.")
    finally:
        conn.close()


def _apuntar_db(ruta: str) -> None:
    """Redirige la base a otra ruta (para no tocar la de la app si se quiere)."""
    from config import settings
    p = Path(ruta).resolve()
    settings.DATA_DIR = p.parent
    settings.LOCAL_DB_PATH = p


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga productos de prueba de rendimiento.")
    ap.add_argument("--cantidad", type=int, default=200,
                    help="Cantidad de productos a crear (default 200).")
    ap.add_argument("--limpiar", action="store_true",
                    help="Borra los productos/categorías de prueba y sale.")
    ap.add_argument("--sincronizar", action="store_true",
                    help="Deja que los productos de prueba suban a Neon y se "
                         "repliquen a las demás PCs (por defecto NO suben).")
    ap.add_argument("--db", metavar="RUTA",
                    help="Base a usar (default: la de la app, data/kiosko.db).")
    args = ap.parse_args()

    if args.db:
        _apuntar_db(args.db)

    if args.limpiar:
        limpiar()
    else:
        sembrar(args.cantidad, sincronizar=args.sincronizar)


if __name__ == "__main__":
    sys.exit(main())
