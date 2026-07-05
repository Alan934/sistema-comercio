"""Modal de alta de empleado (usuario + contraseña).

Devuelve {username, password} o None si se cancela.
"""
import customtkinter as ctk

from app.ui import theme
from app.ui.dialogs.base import ModalBase


class UsuarioDialog(ModalBase):
    def __init__(self, master):
        super().__init__(master, "Nuevo empleado")

        ctk.CTkLabel(self, text="Usuario", anchor="w").grid(
            row=0, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_user = ctk.CTkEntry(self, width=240)
        self.ent_user.grid(row=0, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="Contraseña", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_pass = ctk.CTkEntry(self, width=240, show="•")
        self.ent_pass.grid(row=1, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="Repetir contraseña", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_pass2 = ctk.CTkEntry(self, width=240, show="•")
        self.ent_pass2.grid(row=2, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="El empleado accede solo a Caja y Clientes.",
                     text_color=theme.TXT_MUTED, font=theme.fuente(12)).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=20)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
        self.lbl_error.grid(row=4, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=5, column=0, columnspan=2, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Crear", width=140, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)
        self._pie_atajos(grid_row=99)
        self.after(50, self.ent_user.focus_set)

    def _confirmar(self) -> None:
        user = self.ent_user.get().strip()
        pw = self.ent_pass.get()
        if not user:
            self.lbl_error.configure(text="⚠ El usuario es obligatorio")
            return
        if len(pw) < 4:
            self.lbl_error.configure(text="⚠ La contraseña debe tener 4+ caracteres")
            return
        if pw != self.ent_pass2.get():
            self.lbl_error.configure(text="⚠ Las contraseñas no coinciden")
            return
        self._aceptar({"username": user, "password": pw})
