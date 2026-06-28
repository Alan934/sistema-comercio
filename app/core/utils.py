"""Utilidades transversales: generación de IDs y timestamps."""
import uuid
from datetime import datetime, timezone


def nuevo_id() -> str:
    """ID único global (UUID4) para offline-first. Evita colisiones local<->nube."""
    return str(uuid.uuid4())


def ahora_iso() -> str:
    """Timestamp actual en ISO8601 UTC. Usamos UTC siempre para que la
    sincronización y la resolución de conflictos no dependan de la zona horaria."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
