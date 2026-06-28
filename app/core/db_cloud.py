"""Conexión a Neon PostgreSQL.

Es LAZY a propósito: la app debe arrancar y vender aunque no haya internet
ni psycopg instalado. Solo se conecta cuando el sync realmente lo necesita.
"""
from config import settings

try:
    import psycopg
except ImportError:
    psycopg = None


def disponible() -> bool:
    """True si tenemos lo necesario para intentar conectar a la nube."""
    return psycopg is not None and bool(settings.NEON_DSN)


def connect():
    """Abre una conexión a Neon. Lanza excepción si no está configurado;
    el llamador (sync_manager) la captura y reintenta más tarde."""
    if psycopg is None:
        raise RuntimeError("psycopg no está instalado (pip install 'psycopg[binary]').")
    if not settings.NEON_DSN:
        raise RuntimeError("Falta NEON_DATABASE_URL en el archivo .env.")
    return psycopg.connect(settings.NEON_DSN)
