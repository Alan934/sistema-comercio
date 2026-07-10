"""Modal de alta/edición de usuario (usuario + contraseña + rol).

Devuelve {username, password, rol} o None si se cancela. En modo edición,
un `password` vacío significa "no cambiar la contraseña".
"""
import customtkinter as ctk

from app.models.usuario import etiqueta_rol, EMPLEADO
from app.ui import theme
from app.ui.dialogs.base import ModalBase


class UsuarioDialog(ModalBase):
    def __init__(self, master, roles_disponibles, usuario=None):
        self.edicion = usuario is not None
        super().__init__(master, "Editar usuario" if self.edicion
                         else "Nuevo usuario")
        self._roles_disponibles = roles_disponibles
        self._rol_actual = usuario.rol if self.edicion else None

        ctk.CTkLabel(self, text="Usuario", anchor="w").grid(
            row=0, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_user = ctk.CTkEntry(self, width=240)
        self.ent_user.grid(row=0, column=1, padx=(8, 20), pady=6)
        if self.edicion:
            self.ent_user.insert(0, usuario.username)

        ctk.CTkLabel(self, text="Contraseña nueva" if self.edicion
                     else "Contraseña", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_pass = self._password_con_ojo()
        self.ent_pass.grid(row=1, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="Repetir contraseña", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_pass2 = self._password_con_ojo()
        self.ent_pass2.grid(row=2, column=1, padx=(8, 20), pady=6)

        # Selección de rol: solo al crear y si hay más de una opción.
        self._label_a_rol = {etiqueta_rol(r): r for r in roles_disponibles}
        self._selector = not self.edicion and len(roles_disponibles) > 1
        if self._selector:
            ctk.CTkLabel(self, text="Rol", anchor="w").grid(
                row=3, column=0, sticky="w", padx=(20, 8), pady=6)
            labels = list(self._label_a_rol.keys())
            self.rol_var = ctk.StringVar(value=labels[0])
            ctk.CTkOptionMenu(self, width=240, variable=self.rol_var,
                              values=labels).grid(
                row=3, column=1, padx=(8, 20), pady=6)
        else:
            if self.edicion:
                nota = "Dejá la contraseña en blanco para no cambiarla."
            elif roles_disponibles and roles_disponibles[0] == EMPLEADO:
                nota = "El empleado accede solo a Caja y Clientes."
            else:
                nota = ""
            if nota:
                ctk.CTkLabel(self, text=nota, text_color=theme.TXT_MUTED,
                             font=theme.fuente(12)).grid(
                    row=3, column=0, columnspan=2, sticky="w", padx=20)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.grid(row=4, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=5, column=0, columnspan=2, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar" if self.edicion else "Crear",
                      width=140, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)
        self._pie_atajos(grid_row=99)
        self.after(50, self.ent_user.focus_set)

    def _password_con_ojo(self) -> ctk.CTkEntry:
        """Campo de contraseña con botón de ojito para mostrar/ocultar lo
        escrito, igual que en la pantalla de login."""
        ent = ctk.CTkEntry(self, width=240, show="•")
        ojo = ctk.CTkButton(ent, text="👁", width=30, height=26, corner_radius=6,
                            fg_color="transparent", hover_color=theme.GHOST,
                            text_color=theme.TXT_MUTED, font=theme.fuente(14))

        def alternar() -> None:
            if ent.cget("show"):          # oculta -> mostrar
                ent.configure(show="")
                ojo.configure(text="🙈")
            else:                         # visible -> ocultar
                ent.configure(show="•")
                ojo.configure(text="👁")

        ojo.configure(command=alternar)
        ojo.place(relx=1.0, rely=0.5, x=-4, anchor="e")
        return ent

    def _rol_elegido(self) -> str:
        if self.edicion:
            return self._rol_actual
        if self._selector:
            return self._label_a_rol[self.rol_var.get()]
        return self._roles_disponibles[0]

    def _confirmar(self) -> None:
        user = self.ent_user.get().strip()
        pw = self.ent_pass.get()
        if not user:
            self.lbl_error.configure(text="⚠ El usuario es obligatorio")
            return
        # En edición, contraseña vacía = no se cambia; si no, se valida.
        if not (self.edicion and not pw):
            if len(pw) < 4:
                self.lbl_error.configure(
                    text="⚠ La contraseña debe tener 4+ caracteres")
                return
        if pw != self.ent_pass2.get():
            self.lbl_error.configure(text="⚠ Las contraseñas no coinciden")
            return
        self._aceptar({"username": user, "password": pw,
                       "rol": self._rol_elegido()})
