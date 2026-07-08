"""Lógica de negocio de categorías y su margen de ganancia."""
from decimal import Decimal

from app.core import db_local
from app.core.utils import normalizar_nombre
from app.models.categoria import Categoria
from app.repositories import categoria_repo, producto_repo


class CategoriaError(Exception):
    """Error de negocio esperable."""


def crear(nombre: str, margen_pct: Decimal | None = None) -> str:
    nombre = normalizar_nombre(nombre or "")
    if not nombre:
        raise CategoriaError("La categoría necesita un nombre.")
    conn = db_local.connect()
    try:
        with conn:
            return categoria_repo.crear(conn, nombre, margen_pct)
    finally:
        conn.close()


def actualizar(categoria_id: str, nombre: str,
               margen_pct: Decimal | None) -> None:
    """Edita la categoría y recalcula el precio de TODOS sus productos (los que
    tienen margen propio mantienen el suyo; los demás toman el nuevo)."""
    nombre = normalizar_nombre(nombre or "")
    if not nombre:
        raise CategoriaError("La categoría necesita un nombre.")
    conn = db_local.connect()
    try:
        with conn:
            categoria_repo.actualizar(conn, categoria_id, nombre, margen_pct)
            for pid in producto_repo.ids_por_categoria(conn, categoria_id):
                producto_repo.recalcular_precio(conn, pid)
    finally:
        conn.close()


def listar_activas() -> list[Categoria]:
    conn = db_local.connect()
    try:
        return categoria_repo.listar_activas(conn)
    finally:
        conn.close()
