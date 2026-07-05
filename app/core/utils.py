"""Utilidades transversales: generación de IDs y timestamps."""
import uuid
from datetime import datetime, timezone


def nuevo_id() -> str:
    """ID único global (UUID4) para offline-first. Evita colisiones local<->nube."""
    return str(uuid.uuid4())


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
