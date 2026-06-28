"""Prueba manual de la sincronización con Neon (sin GUI).
Ejecutar desde la raíz:  python demo_sync.py

Requisitos para que haga algo:
  - pip install -r requirements.txt   (psycopg)
  - NEON_DATABASE_URL completo en el archivo .env
Si falta algo, lo informa y no hace nada destructivo.
"""
from app.core import db_local, db_cloud, sync_manager

TABLAS_SYNC = ("ventas", "compras", "cuenta_movimientos", "gastos")


def _pendientes() -> dict:
    conn = db_local.connect()
    try:
        return {t: conn.execute(
            f"SELECT COUNT(*) AS n FROM {t} WHERE sincronizado = 0"
        ).fetchone()["n"] for t in TABLAS_SYNC}
    finally:
        conn.close()


def main():
    db_local.init_db()

    if not db_cloud.disponible():
        print("[!] Nube no configurada.")
        print("  - Instalá dependencias: pip install -r requirements.txt")
        print("  - Completá NEON_DATABASE_URL en el archivo .env")
        return

    print("Pendientes ANTES: ", _pendientes())
    print("Sincronizando con Neon...")
    resultado = sync_manager.sincronizar_ahora()
    print("Resultado:", resultado)
    print("Pendientes DESPUES:", _pendientes())


if __name__ == "__main__":
    main()
