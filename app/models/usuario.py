"""Entidad Usuario y roles del sistema."""
from dataclasses import dataclass

# Roles (de mayor a menor privilegio).
SUPER_ADMIN = "SUPER_ADMIN"
ADMIN = "ADMIN"
EMPLEADO = "EMPLEADO"

# Etiquetas legibles para la interfaz.
ETIQUETA_ROL = {
    SUPER_ADMIN: "Super administrador",
    ADMIN: "Administrador",
    EMPLEADO: "Empleado",
}

# Qué secciones ve cada rol (claves de las vistas del menú lateral).
_SECCIONES_ADMIN = ["caja", "stock", "carne", "proveedores", "clientes",
                    "reportes", "cierres", "usuarios"]
SECCIONES_POR_ROL = {
    SUPER_ADMIN: _SECCIONES_ADMIN,
    ADMIN: _SECCIONES_ADMIN,
    EMPLEADO: ["caja", "clientes"],
}


def etiqueta_rol(rol: str) -> str:
    return ETIQUETA_ROL.get(rol, rol)


def roles_que_puede_crear(rol_actor: str) -> list[str]:
    """Roles que un usuario con `rol_actor` puede dar de alta."""
    if rol_actor == SUPER_ADMIN:
        return [ADMIN, EMPLEADO]
    if rol_actor == ADMIN:
        return [EMPLEADO]
    return []


def puede_gestionar(rol_actor: str, rol_objetivo: str) -> bool:
    """True si `rol_actor` puede desactivar a un usuario con `rol_objetivo`. El
    super admin gestiona administradores y empleados; el admin solo empleados.
    Nadie gestiona a otro super admin desde la interfaz."""
    if rol_actor == SUPER_ADMIN:
        return rol_objetivo in (ADMIN, EMPLEADO)
    if rol_actor == ADMIN:
        return rol_objetivo == EMPLEADO
    return False


def puede_editar_credenciales(rol_actor: str, rol_objetivo: str) -> bool:
    """True si `rol_actor` puede cambiar el usuario y la contraseña de otro
    usuario. Solo el super administrador puede, y sobre administradores y
    empleados."""
    return rol_actor == SUPER_ADMIN and rol_objetivo in (ADMIN, EMPLEADO)


@dataclass
class Usuario:
    id: str
    username: str
    rol: str
    activo: bool = True

    @property
    def es_super_admin(self) -> bool:
        return self.rol == SUPER_ADMIN

    @property
    def es_admin(self) -> bool:
        """Tiene privilegios de administrador (el super admin también)."""
        return self.rol in (ADMIN, SUPER_ADMIN)

    @property
    def rol_legible(self) -> str:
        return etiqueta_rol(self.rol)

    def puede_ver(self, seccion: str) -> bool:
        return seccion in SECCIONES_POR_ROL.get(self.rol, [])
