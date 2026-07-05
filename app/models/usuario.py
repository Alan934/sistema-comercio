"""Entidad Usuario y roles del sistema."""
from dataclasses import dataclass

# Roles.
ADMIN = "ADMIN"
EMPLEADO = "EMPLEADO"

# Qué secciones ve cada rol (claves de las vistas del menú lateral).
SECCIONES_POR_ROL = {
    ADMIN: ["caja", "stock", "proveedores", "clientes", "reportes", "cierres",
            "usuarios"],
    EMPLEADO: ["caja", "clientes"],
}


@dataclass
class Usuario:
    id: str
    username: str
    rol: str
    activo: bool = True

    @property
    def es_admin(self) -> bool:
        return self.rol == ADMIN

    def puede_ver(self, seccion: str) -> bool:
        return seccion in SECCIONES_POR_ROL.get(self.rol, [])
