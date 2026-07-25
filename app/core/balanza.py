"""Lectura de las etiquetas que imprime la balanza etiquetadora (Systel Cuora MAX).

Formato del código de barras impreso en cada etiqueta (EAN-13). Es la
configuración de fábrica de la balanza para "venta por peso" (manual, pág. 39):

    2 0 | P P P P | I I I I I I | X
    └─┬┘   └──┬─┘   └────┬────┘   └── dígito verificador EAN-13
      │       │          └─ importe total, ya calculado por la balanza
      │       └─ PLU: código del artículo EN LA BALANZA (1..9999)
      └─ cabecera fija "20" = artículo PESABLE

Reglas de negocio:
  - La etiqueta trae el IMPORTE, no el peso. Se cobra ese importe tal cual,
    porque es el que el cliente está viendo impreso. El peso se deduce
    dividiendo por el precio por kg (`peso_desde_importe`) y sirve solo para
    descontar el stock.
  - El importe viene en PESOS ENTEROS porque la balanza está configurada con
    "coma de precio" 6.0 ($ 000000, sin centavos; manual pág. 41). Si alguna vez
    se la pasa a modo 4.2 ($0000.00), el importe pasaría a venir en centavos:
    ahí hay que poner IMPORTE_DECIMALES = 2.
  - El PLU es un dato de la balanza que hay que cargar a mano en ella y espejar
    en el producto. Con 4 dígitos el tope es 9999: el manual avisa que si el PLU
    no entra en los dígitos configurados, la balanza no imprime el código.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CABECERA_PESABLE = "20"   # cabecera de fábrica para venta por peso
LARGO_EAN13 = 13
PLU_MAX = 9999            # 4 dígitos en el código de barras

IMPORTE_DECIMALES = 0     # "coma de precio" 6.0 = pesos enteros
KILOS = Decimal("0.001")  # la balanza pesa de a gramos


@dataclass(frozen=True)
class Etiqueta:
    """Lo que dice una etiqueta de la balanza. `plu` es 0 cuando se pesó sin
    seleccionar artículo (modo genérico): la etiqueta es válida pero anónima."""
    plu: int
    importe: Decimal


def normalizar_plu(valor) -> int | None:
    """Texto/número -> PLU válido, o None si viene vacío (el producto no se pesa
    en la balanza). Lanza ValueError con un mensaje mostrable; cada servicio lo
    envuelve en su propio tipo de error."""
    if valor is None or str(valor).strip() == "":
        return None
    try:
        plu = int(str(valor).strip())
    except ValueError:
        raise ValueError("El PLU de balanza tiene que ser un número entero.")
    if not 1 <= plu <= PLU_MAX:
        raise ValueError(
            f"El PLU de balanza va de 1 a {PLU_MAX} (el código de barras de "
            "la etiqueta reserva 4 dígitos).")
    return plu


def _digito_verificador(doce: str) -> int:
    suma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(doce))
    return (10 - suma % 10) % 10


def parsear(codigo: str) -> Etiqueta | None:
    """Interpreta un código escaneado. Devuelve None si NO es una etiqueta de
    la balanza (largo, cabecera o dígito verificador que no cierran), para que
    la caja lo siga tratando como un código de barras común."""
    codigo = (codigo or "").strip()
    if len(codigo) != LARGO_EAN13 or not codigo.isdigit():
        return None
    if not codigo.startswith(CABECERA_PESABLE):
        return None
    if int(codigo[12]) != _digito_verificador(codigo[:12]):
        return None
    return Etiqueta(
        plu=int(codigo[2:6]),
        importe=Decimal(codigo[6:12]).scaleb(-IMPORTE_DECIMALES),
    )


def precio_desfasado(importe: Decimal, precio_por_kg: Decimal) -> bool:
    """Detecta que el precio/kg cargado en la balanza NO es el mismo que el del
    sistema, mirando solo el importe de la etiqueta.

    Cómo: la balanza pesa de a gramos, así que el peso real siempre es múltiplo
    de 0,001 kg. Si el precio del sistema es el correcto, `importe / precio` cae
    justo en un gramo redondo, con la única diferencia del redondeo del importe
    a peso entero. Si el precio está desfasado, cae en cualquier lado.

    Es una HEURÍSTICA, no una prueba:
      - Detecta ~9 de cada 10 escaneos con el precio mal; en dos o tres ventas
        del mismo corte salta seguro.
      - Punto ciego: si los precios están en una proporción que conserva la
        alineación de gramos (el doble, la mitad), no lo ve.
      - La tolerancia usa 1 peso (no 0,5) para cubrir tanto que la balanza
        redondee como que trunque el importe, y así no dar falsas alarmas.
    """
    precio_por_kg = Decimal(str(precio_por_kg))
    if precio_por_kg <= 0:
        return False
    exacto = Decimal(str(importe)) / precio_por_kg
    desvio = abs(exacto - exacto.quantize(KILOS, rounding=ROUND_HALF_UP))
    return desvio > (Decimal("1") / precio_por_kg)


def peso_desde_importe(importe: Decimal, precio_por_kg: Decimal) -> Decimal | None:
    """Deduce los kg que representa el importe de la etiqueta, para descontar
    stock. Redondea al gramo. Devuelve None si el producto no tiene precio (no
    hay forma de deducir el peso)."""
    precio_por_kg = Decimal(str(precio_por_kg))
    if precio_por_kg <= 0:
        return None
    kg = (Decimal(str(importe)) / precio_por_kg).quantize(
        KILOS, rounding=ROUND_HALF_UP)
    return kg if kg > 0 else None
