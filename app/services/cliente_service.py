"""Lógica de negocio de clientes/fiados."""
from app.core import db_local
from app.models.cliente import Cliente
from app.repositories import cliente_repo


def listar_activos() -> list[Cliente]:
    conn = db_local.connect()
    try:
        return cliente_repo.listar_activos(conn)
    finally:
        conn.close()
