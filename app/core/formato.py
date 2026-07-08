"""Formato de números al estilo argentino: punto para separar los miles y coma
para los decimales (ej. $19.000,50 · 5,353 kg).

Centraliza el formateo de toda la app para que se muestre igual en cada vista y
diálogo. El parseo de la entrada del usuario (coma como decimal) vive en cada
diálogo; esto es solo para MOSTRAR."""
from decimal import Decimal


def _agrupar_miles(entero: str) -> str:
    """'19000' -> '19.000'. Recibe solo dígitos (sin signo)."""
    partes = []
    while len(entero) > 3:
        partes.insert(0, entero[-3:])
        entero = entero[:-3]
    partes.insert(0, entero)
    return ".".join(partes)


def numero(valor, decimales: int | None = None) -> str:
    """Formatea un número al estilo argentino (miles con punto, decimales con
    coma).

    - `decimales=None` conserva los decimales significativos del valor, sin
      ceros de relleno (ideal para pesos/cantidades: 5.353 -> '5,353', 5.5 ->
      '5,5', 19000 -> '19.000').
    - `decimales=n` fija esa cantidad de decimales (ideal para dinero)."""
    d = Decimal(str(valor))
    signo = "-" if d < 0 else ""
    d = abs(d)
    if decimales is None:
        entero, _, frac = format(d, "f").partition(".")
        frac = frac.rstrip("0")
    else:
        entero, _, frac = f"{d:.{decimales}f}".partition(".")
    ent_fmt = _agrupar_miles(entero)
    if frac:
        return f"{signo}{ent_fmt},{frac}"
    return f"{signo}{ent_fmt}"


def moneda(valor, decimales: int = 2) -> str:
    """Importe en pesos con formato argentino. Ej.: 19000.5 -> '$19.000,50'.
    El signo negativo queda antes del símbolo: -1234.5 -> '-$1.234,50'."""
    texto = numero(valor, decimales=decimales)
    if texto.startswith("-"):
        return "-$" + texto[1:]
    return "$" + texto


def kg(valor) -> str:
    """Peso en kilos con formato argentino. Ej.: 5.353 -> '5,353 kg'."""
    return f"{numero(valor)} kg"
