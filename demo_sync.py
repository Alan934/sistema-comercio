"""Prueba manual de la sincronización con Neon (sin GUI).
Ejecutar desde la raíz:  python demo_sync.py

Requisitos para que haga algo:
  - pip install -r requirements.txt   (psycopg)
  - NEON_DATABASE_URL completo en el archivo .env
Si falta algo, lo informa y no hace nada destructivo.
"""
from app.core import db_local, db_cloud, sync_manager
from app.repositories import venta_repo


def main():
    db_local.init_db()

    if not db_cloud.disponible():
        print("[!] Nube no configurada.")
        print("  - Instalá dependencias: pip install -r requirements.txt")
        print("  - Completá NEON_DATABASE_URL en el archivo .env")
        return

    conn = db_local.connect()
    try:
        pendientes_antes = venta_repo.contar_pendientes_sync(conn)
    finally:
        conn.close()
    print(f"Ventas pendientes ANTES: {pendientes_antes}")

    print("Sincronizando con Neon...")
    resultado = sync_manager.sincronizar_ahora()
    print("Resultado:", resultado)

    conn = db_local.connect()
    try:
        pendientes_despues = venta_repo.contar_pendientes_sync(conn)
    finally:
        conn.close()
    print(f"Ventas pendientes DESPUÉS: {pendientes_despues}")


if __name__ == "__main__":
    main()
