"""Lógica de negocio de usuarios: alta, autenticación y roles."""
from app.core import auth, db_local
from app.core.utils import nuevo_id
from app.models.usuario import Usuario, ADMIN, EMPLEADO
from app.repositories import usuario_repo


class UsuarioError(Exception):
    """Error de negocio esperable."""


def hay_usuarios() -> bool:
    conn = db_local.connect()
    try:
        return usuario_repo.hay_usuarios(conn)
    finally:
        conn.close()


def _crear(username: str, password: str, rol: str) -> str:
    username = (username or "").strip()
    if not username:
        raise UsuarioError("El usuario necesita un nombre.")
    if len(password or "") < 4:
        raise UsuarioError("La contraseña debe tener al menos 4 caracteres.")
    conn = db_local.connect()
    try:
        if usuario_repo.existe_username(conn, username):
            raise UsuarioError(f"Ya existe un usuario “{username}”.")
        salt, hash_hex = auth.hash_password(password)
        uid = nuevo_id()
        with conn:
            usuario_repo.crear(conn, uid, username, hash_hex, salt, rol)
    finally:
        conn.close()
    return uid


def crear_admin(username: str, password: str) -> str:
    return _crear(username, password, ADMIN)


def crear_empleado(username: str, password: str) -> str:
    return _crear(username, password, EMPLEADO)


def autenticar(username: str, password: str) -> Usuario | None:
    """Devuelve el Usuario si las credenciales son válidas, si no None."""
    conn = db_local.connect()
    try:
        row = usuario_repo.obtener_por_username(conn, (username or "").strip())
    finally:
        conn.close()
    if row is None:
        return None
    if not auth.verificar(password or "", row["salt"], row["password_hash"]):
        return None
    return Usuario(id=row["id"], username=row["username"], rol=row["rol"],
                   activo=True)


def listar() -> list[Usuario]:
    conn = db_local.connect()
    try:
        return usuario_repo.listar_activos(conn)
    finally:
        conn.close()


def desactivar(usuario_id: str) -> None:
    conn = db_local.connect()
    try:
        with conn:
            usuario_repo.desactivar(conn, usuario_id)
    finally:
        conn.close()
