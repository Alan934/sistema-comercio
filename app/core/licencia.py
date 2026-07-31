"""Firma de los registros de suscripción (HMAC-SHA256).

Para qué: el comercio tiene la base local en su propia PC y podría abrirla con
cualquier editor de SQLite y regalarse doce meses de suscripción. Cada fila de
`suscripcion` y `suscripcion_pagos` va firmada con un secreto que solo conoce
la aplicación; una fila insertada a mano no valida y el cálculo la IGNORA.

Alcance honesto de esta defensa: el secreto viaja dentro del .exe, así que
alguien con conocimientos y ganas puede extraerlo. Frena el ataque realista
(editar la base con DB Browser), no a un ingeniero decidido. La segunda capa
—la nube manda y el pull reemplaza lo local— es la que cierra el resto.

La firma se versiona ("v1:<hex>") para poder rotar el secreto más adelante sin
invalidar en silencio todo lo firmado antes.
"""
import hashlib
import hmac
import json
from decimal import Decimal, InvalidOperation

from config import settings

VERSION = "v1"

# Secreto ofuscado con un XOR simple: no evita que se extraiga del binario,
# pero evita que aparezca como texto legible al abrir el .exe con un editor.
_CLAVE_XOR = 0x5A
_SEMILLA = bytes(b ^ _CLAVE_XOR for b in bytes([
    0x31, 0x33, 0x35, 0x29, 0x31, 0x35, 0x77, 0x2A, 0x35, 0x29, 0x26, 0x36,
    0x33, 0x39, 0x3F, 0x34, 0x39, 0x33, 0x3B, 0x26, 0x2C, 0x6B, 0x26, 0x1B,
    0x36, 0x3B, 0x34, 0x63, 0x69, 0x6E, 0x26, 0x34, 0x35, 0x77, 0x3F, 0x3E,
    0x33, 0x2E, 0x3B, 0x28,
]))


def _secreto() -> bytes:
    return hashlib.sha256(_SEMILLA).digest()


# --- Normalización ----------------------------------------------------------
# Los valores tienen que serializarse EXACTAMENTE igual al firmar y al
# verificar. Ojo con el dinero: la columna es NUMERIC y SQLite, por afinidad de
# tipo, convierte '1000.00' en el entero 1000 al guardarlo. Por eso el importe
# se cuantiza siempre a dos decimales en vez de usar el texto tal cual.

def _dinero(valor) -> str:
    try:
        return str(Decimal(str(valor if valor not in (None, "") else 0))
                   .quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return "0.00"


def _entero(valor) -> str:
    try:
        return str(int(valor or 0))
    except (TypeError, ValueError):
        return "0"


def _texto(valor) -> str:
    return "" if valor is None else str(valor)


def _firmar_campos(campos: list[str]) -> str:
    mensaje = "|".join(campos).encode("utf-8")
    mac = hmac.new(_secreto(), mensaje, hashlib.sha256).hexdigest()
    return f"{VERSION}:{mac}"


def _verificar(campos: list[str], firma) -> bool:
    if not firma:
        return False
    return hmac.compare_digest(_firmar_campos(campos), str(firma))


# --- Pagos ------------------------------------------------------------------
# Se firma lo que define cuánto crédito otorga el pago. La nota, el método y
# quién lo cargó quedan fuera a propósito: son informativos y cambiarlos no
# altera la cobertura.

def _campos_pago(fila) -> list[str]:
    return [
        "pago",
        _texto(fila["id"]),
        _texto(fila["fecha"]),
        _entero(fila["meses"]),
        _dinero(fila["monto"]),
        _entero(fila["anulado"]),
    ]


def firmar_pago(fila) -> str:
    """Devuelve la firma de un pago. `fila` es un dict o sqlite3.Row con
    id, fecha, meses, monto y anulado."""
    return _firmar_campos(_campos_pago(fila))


def pago_valido(fila) -> bool:
    """True si el pago fue creado por la aplicación y nadie lo tocó después."""
    try:
        return _verificar(_campos_pago(fila), fila["firma"])
    except (KeyError, IndexError, TypeError):
        return False


# --- Configuración ----------------------------------------------------------

#   `ultima_fecha_vista` queda FUERA de la firma a propósito: la aplicación la
#   adelanta sola en cada arranque y volver a firmar en cada avance sería ruido.
#   Tampoco hace falta protegerla: atrasarla no regala días (el cálculo toma el
#   máximo entre ella y el reloj) y adelantarla solo perjudica a quien lo haga.

def _campos_config(fila) -> list[str]:
    return [
        "config",
        _texto(fila["id"]),
        _texto(fila["fecha_inicio"]),
        _dinero(fila["monto_mensual"]),
        _entero(fila["gracia_dias"]),
        _texto(fila["estado_manual"]),
    ]


def firmar_config(fila) -> str:
    return _firmar_campos(_campos_config(fila))


def config_valida(fila) -> bool:
    try:
        return _verificar(_campos_config(fila), fila["firma"])
    except (KeyError, IndexError, TypeError):
        return False


# --- Sello en disco ---------------------------------------------------------
# Copia firmada de la configuración, guardada FUERA de la base. Cubre el hueco
# más obvio: borrar la fila de `suscripcion` con un editor de SQLite dejaría al
# sistema "sin configurar" y por lo tanto sin vencimiento. Con el sello, esa
# fila se restaura sola en el próximo arranque. Guarda también la marca de agua
# de fecha, para que borrar la base no reinicie la protección del reloj.

_CAMPOS_SELLO = ("id", "comercio", "fecha_inicio", "monto_mensual",
                 "gracia_dias", "datos_pago", "estado_manual",
                 "ultima_fecha_vista", "firma", "updated_at")


def _ruta_sello():
    return settings.DATA_DIR / "licencia.dat"


def guardar_sello(fila) -> None:
    """Escribe el sello. Nunca lanza: si el disco falla, la app sigue andando
    (la nube sigue siendo la autoridad de todos modos)."""
    datos = {}
    for c in _CAMPOS_SELLO:
        try:
            valor = fila[c]
        except (KeyError, IndexError, TypeError):
            valor = None
        datos[c] = None if valor is None else str(valor)
    cuerpo = json.dumps(datos, sort_keys=True, ensure_ascii=False)
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _ruta_sello().write_text(
            json.dumps({"datos": datos, "sello": _firmar_campos(["sello", cuerpo])},
                       ensure_ascii=False),
            encoding="utf-8")
    except OSError:
        pass


def leer_sello() -> dict | None:
    """Devuelve el sello si existe y no fue alterado; si no, None."""
    ruta = _ruta_sello()
    try:
        if not ruta.exists():
            return None
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        datos = contenido["datos"]
        cuerpo = json.dumps(datos, sort_keys=True, ensure_ascii=False)
        if not _verificar(["sello", cuerpo], contenido.get("sello")):
            return None
        return datos
    except (OSError, ValueError, KeyError, TypeError):
        return None
