"""Decodifica un código de barras de la balanza. Para probar en el mostrador.

Sirve para saber QUÉ trae una etiqueta cuando algo no funciona: si el código es
válido, qué PLU y qué importe lleva, y si ese PLU está en el sistema.

Uso:
    python decodificar_etiqueta.py 2000000110554
    python decodificar_etiqueta.py            (modo interactivo: escaneá y Enter)

En modo interactivo se puede usar la pistolita directamente sobre la consola.
No escribe NADA en la base: solo lee.
"""
import sys

from app.core import balanza, db_local
from app.repositories import producto_repo


def _linea(txt=""):
    print(txt)


def analizar(codigo: str) -> None:
    codigo = (codigo or "").strip()
    _linea()
    _linea(f"  Codigo escaneado: {codigo!r}  ({len(codigo)} caracteres)")
    _linea("  " + "-" * 58)

    etq = balanza.parsear(codigo)
    if etq is None:
        _linea("  NO es una etiqueta de la balanza.")
        # Explica POR QUE, que es lo util cuando algo no anda.
        if not codigo.isdigit():
            _linea("  Motivo: tiene caracteres que no son numeros.")
        elif len(codigo) != 13:
            _linea(f"  Motivo: tiene {len(codigo)} digitos y un EAN-13 tiene 13.")
        elif not codigo.startswith(balanza.CABECERA_PESABLE):
            _linea(f"  Motivo: empieza con {codigo[:2]!r} y las etiquetas de "
                   f"peso empiezan con {balanza.CABECERA_PESABLE!r}.")
            _linea("          Revisa en la balanza: 8 configurar equipo ->")
            _linea("          2 Balanza -> 2 codigo de barras -> 1 Venta por Peso")
        else:
            esperado = balanza._digito_verificador(codigo[:12])
            _linea(f"  Motivo: el digito verificador no cierra "
                   f"(dice {codigo[12]}, deberia ser {esperado}).")
            _linea("          Suele ser un error de lectura: escanea de nuevo.")
        _linea()
        _linea("  Si es un codigo de gondola comun, esta bien que diga esto:")
        _linea("  el sistema lo busca como codigo de barra normal.")
        return

    _linea("  ES una etiqueta de balanza (venta por peso).")
    _linea(f"    PLU     : {etq.plu}")
    _linea(f"    Importe : ${etq.importe}")

    if etq.plu == 0:
        _linea()
        _linea("  El PLU es 0: se peso SIN elegir el articulo en la balanza.")
        _linea("  La etiqueta no dice que corte es. Hay que pesar de nuevo")
        _linea("  seleccionando el articulo.")
        return

    db_local.init_db()
    conn = db_local.connect()
    try:
        prod = producto_repo.buscar_por_plu(conn, etq.plu)
    finally:
        conn.close()

    _linea()
    if prod is None:
        _linea(f"  Ningun producto del sistema tiene el PLU {etq.plu}.")
        _linea("  Cargaselo: Stock -> editar el producto -> campo PLU balanza.")
        return

    _linea(f"  Producto  : {prod.nombre}")
    _linea(f"  Precio    : ${prod.precio_venta} por kg (segun el SISTEMA)")

    kg = balanza.peso_desde_importe(etq.importe, prod.precio_venta)
    if kg is None:
        _linea("  Sin precio cargado: no se puede deducir el peso.")
        return
    _linea(f"  Peso      : {kg} kg   (= ${etq.importe} / ${prod.precio_venta})")
    _linea(f"  Se cobra  : ${etq.importe}  (el importe impreso, tal cual)")

    _linea()
    if balanza.precio_desfasado(etq.importe, prod.precio_venta):
        implicito = (etq.importe / kg) if kg else 0
        _linea("  *** EL PRECIO NO COINCIDE ***")
        _linea(f"  El sistema tiene ${prod.precio_venta}/kg, pero la balanza")
        _linea(f"  parece tener otro (rondaria ${implicito:.2f}/kg).")
        _linea("  Emparejalos o el stock se va a ir desviando.")
    else:
        _linea("  El precio de la balanza coincide con el del sistema. OK.")


def main() -> None:
    if len(sys.argv) > 1:
        for c in sys.argv[1:]:
            analizar(c)
        return
    _linea("Escanea una etiqueta (o pega el codigo) y Enter. Enter vacio para salir.")
    while True:
        try:
            codigo = input("\ncodigo> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not codigo:
            break
        analizar(codigo)


if __name__ == "__main__":
    main()
