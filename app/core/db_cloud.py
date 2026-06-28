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
    el llamador (sync_manager) la captura y reintenta más tarde.

    autocommit=True es CLAVE: así cada `with conn.transaction()` es un bloque
    atómico real e independiente. Sin esto, los SELECT del pull dejan una
    transacción abierta y los `transaction()` de los push se vuelven savepoints
    anidados que, al cerrar la conexión, se revierten (se perderían los INSERT)."""
    if psycopg is None:
        raise RuntimeError("psycopg no está instalado (pip install 'psycopg[binary]').")
    if not settings.NEON_DSN:
        raise RuntimeError("Falta NEON_DATABASE_URL en el archivo .env.")
    return psycopg.connect(settings.NEON_DSN, autocommit=True)


def asegurar_schema(conn) -> None:
    """Crea las tablas en Neon si no existen. Ejecuta cada sentencia por
    separado (psycopg no corre varias en un mismo execute), todo atómico."""
    sql = settings.SCHEMA_CLOUD_PATH.read_text(encoding="utf-8")
    # Quita líneas de comentario antes de partir por ';'.
    lineas = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    limpio = "\n".join(lineas)
    with conn.transaction():
        with conn.cursor() as cur:
            for sentencia in limpio.split(";"):
                s = sentencia.strip()
                if s:
                    cur.execute(s)
