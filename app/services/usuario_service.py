"""Lógica de negocio de usuarios: alta, autenticación y roles."""
from app.core import auth, db_local
from app.core.utils import nuevo_id
from app.models.usuario import (Usuario, SUPER_ADMIN, ADMIN, EMPLEADO,
                                roles_que_puede_crear, puede_editar_credenciales)
from app.repositories import usuario_repo


class UsuarioError(Exception):
    """Error de negocio esperable."""


def hay_usuarios() -> bool:
    conn = db_local.connect()
    try:
        return usuario_repo.hay_usuarios(conn)
    finally:
        conn.close()


def _validar_password(password: str) -> None:
    if len(password or "") < 4:
        raise UsuarioError("La contraseña debe tener al menos 4 caracteres.")


def _crear(username: str, password: str, rol: str) -> str:
    username = (username or "").strip()
    if not username:
        raise UsuarioError("El usuario necesita un nombre.")
    _validar_password(password)
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


def crear_super_admin(username: str, password: str) -> str:
    return _crear(username, password, SUPER_ADMIN)


def crear_admin(username: str, password: str) -> str:
    return _crear(username, password, ADMIN)


def crear_empleado(username: str, password: str) -> str:
    return _crear(username, password, EMPLEADO)


def crear(rol_actor: str, username: str, password: str, rol: str) -> str:
    """Da de alta un usuario validando que `rol_actor` pueda crear ese `rol`."""
    if rol not in roles_que_puede_crear(rol_actor):
        raise UsuarioError("No tenés permiso para crear ese tipo de usuario.")
    return _crear(username, password, rol)


def editar(usuario_id: str, username: str, password: str | None = None,
           rol_actor: str | None = None, rol_objetivo: str | None = None) -> None:
    """Actualiza el nombre de usuario y, si se pasa contraseña, la cambia.
    Un `password` vacío o None deja la contraseña como estaba. Si se pasa
    `rol_actor`, valida que solo el super admin cambie credenciales de otros."""
    if rol_actor is not None and not puede_editar_credenciales(rol_actor,
                                                               rol_objetivo):
        raise UsuarioError(
            "Solo el super administrador puede cambiar el usuario y la contraseña.")
    username = (username or "").strip()
    if not username:
        raise UsuarioError("El usuario necesita un nombre.")
    hash_hex = salt = None
    if password:
        _validar_password(password)
        salt, hash_hex = auth.hash_password(password)
    conn = db_local.connect()
    try:
        if usuario_repo.existe_username_otro(conn, username, usuario_id):
            raise UsuarioError(f"Ya existe un usuario “{username}”.")
        with conn:
            usuario_repo.actualizar(conn, usuario_id, username, hash_hex, salt)
    finally:
        conn.close()


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
