"""Utilidades transversales: generación de IDs, timestamps y texto."""
import uuid
from datetime import datetime, timezone


# Palabras de enlace que quedan en minúscula dentro de un nombre (salvo si son
# la primera palabra). Convención de "Título" en español.
_PALABRAS_MINUSCULAS = {
    "de", "del", "la", "las", "el", "los", "lo", "y", "e", "o", "u",
    "a", "al", "en", "con", "sin", "por", "para",
}


def nuevo_id() -> str:
    """ID único global (UUID4) para offline-first. Evita colisiones local<->nube."""
    return str(uuid.uuid4())


def _capitalizar_palabra(palabra: str) -> str:
    """Primera letra en mayúscula y el resto en minúscula, respetando los guiones
    internos (ej. 'coca-cola' -> 'Coca-Cola')."""
    return "-".join(
        p[:1].upper() + p[1:] for p in palabra.split("-")
    )


def normalizar_nombre(texto: str) -> str:
    """Normaliza un nombre a formato "Título": la primera letra de cada palabra en
    mayúscula y el resto en minúscula, dejando en minúscula las palabras de enlace
    (de, la, y, ...) salvo cuando son la primera palabra.

    Ej.: 'mana rellenas de frutilla' -> 'Mana Rellenas de Frutilla'.
    Colapsa espacios repetidos y recorta los extremos."""
    if not texto:
        return ""
    palabras = texto.split()
    salida = []
    for i, palabra in enumerate(palabras):
        baja = palabra.lower()
        if i != 0 and baja in _PALABRAS_MINUSCULAS:
            salida.append(baja)
        else:
            salida.append(_capitalizar_palabra(baja))
    return " ".join(salida)


def ahora_iso() -> str:
    """Timestamp actual en ISO8601 UTC (con microsegundos). Para
    created_at/updated_at: la sincronización y la resolución de conflictos no
    dependen de la zona horaria."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def ahora_local() -> str:
    """Timestamp local CON offset (ej. ...-03:00) y microsegundos. Para la
    'fecha' de las operaciones (ventas, compras, gastos): los reportes filtran
    por el DÍA LOCAL (substr) y el cierre de caja delimita períodos con precisión
    (dos operaciones en el mismo segundo no colisionan)."""
    return datetime.now().astimezone().isoformat(timespec="microseconds")
