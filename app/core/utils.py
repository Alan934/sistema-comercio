"""Utilidades transversales: generación de IDs y timestamps."""
import uuid
from datetime import datetime, timezone


def nuevo_id() -> str:
    """ID único global (UUID4) para offline-first. Evita colisiones local<->nube."""
    return str(uuid.uuid4())


def ahora_iso() -> str:
    """Timestamp actual en ISO8601 UTC. Para created_at/updated_at: la
    sincronización y la resolución de conflictos no dependen de la zona horaria."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ahora_local() -> str:
    """Timestamp local CON offset (ej. ...-03:00). Para la 'fecha' de las
    operaciones (ventas, compras, gastos): así los reportes filtran por el DÍA
    LOCAL del negocio y no por el día UTC. El offset deja la fecha sin ambigüedad
    para la sincronización a la nube."""
    return datetime.now().astimezone().isoformat(timespec="seconds")
