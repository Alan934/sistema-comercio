"""Modal que pide las credenciales de un administrador para autorizar una
acción sensible (ej.: vender por encima del stock disponible).

Devuelve True si un usuario con rol de administrador se autenticó correctamente;
None si se canceló o las credenciales no eran de un admin válido.
"""
import customtkinter as ctk

from app.services import usuario_service
from app.ui import theme
from app.ui.dialogs.base import ModalBase


class AutorizacionAdminDialog(ModalBase):
    def __init__(self, master, motivo: str = ""):
        super().__init__(master, "Autorización de administrador")

        ctk.CTkLabel(self, text="Autorización requerida",
                     font=theme.fuente(16, "bold"), text_color=theme.TXT).pack(
            padx=24, pady=(18, 2))
        if motivo:
            ctk.CTkLabel(self, text=motivo, text_color=theme.TXT_MUTED,
                         font=theme.fuente(13), justify="center",
                         wraplength=320).pack(padx=24, pady=(0, 10))

        ctk.CTkLabel(self, text="Usuario administrador", anchor="w",
                     text_color=theme.TXT_MUTED, font=theme.fuente(13)).pack(
            fill="x", padx=24)
        self.ent_user = ctk.CTkEntry(self, width=290, height=42,
                                     corner_radius=10, font=theme.fuente(15),
                                     placeholder_text="Usuario")
        self.ent_user.pack(padx=24, pady=(4, 12))

        ctk.CTkLabel(self, text="Contraseña", anchor="w",
                     text_color=theme.TXT_MUTED, font=theme.fuente(13)).pack(
            fill="x", padx=24)
        self.ent_pass = self._password_con_ojo("Contraseña")
        self.ent_pass.pack(padx=24, pady=(4, 8))

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO,
                                      font=theme.fuente(13), justify="center",
                                      wraplength=290)
        self.lbl_error.pack()

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(padx=24, pady=(8, 16))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Autorizar", width=140, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(bind_enter=False)
        self.ent_user.bind("<Return>", lambda _e: self._confirmar())
        self.ent_pass.bind("<Return>", lambda _e: self._confirmar())
        self.after(60, self.ent_user.focus_set)

    def _password_con_ojo(self, placeholder: str) -> ctk.CTkEntry:
        """Campo de contraseña con botón de ojito para mostrar/ocultar (igual que
        en la ventana de login)."""
        ent = ctk.CTkEntry(self, width=290, height=42, corner_radius=10,
                           show="•", font=theme.fuente(15),
                           placeholder_text=placeholder)
        ojo = ctk.CTkButton(ent, text="👁", width=32, height=32, corner_radius=8,
                            fg_color="transparent", hover_color=theme.GHOST,
                            text_color=theme.TXT_MUTED, font=theme.fuente(15))

        def alternar() -> None:
            if ent.cget("show"):          # oculta -> mostrar
                ent.configure(show="")
                ojo.configure(text="🙈")
            else:                         # visible -> ocultar
                ent.configure(show="•")
                ojo.configure(text="👁")

        ojo.configure(command=alternar)
        ojo.place(relx=1.0, rely=0.5, x=-5, anchor="e")
        return ent

    def _confirmar(self) -> None:
        user = self.ent_user.get().strip()
        pw = self.ent_pass.get()
        if not user or not pw:
            self.lbl_error.configure(text="⚠ Completá usuario y contraseña")
            return
        usuario = usuario_service.autenticar(user, pw)
        if usuario is None:
            self.lbl_error.configure(text="⚠ Usuario o contraseña incorrectos")
            return
        if not usuario.es_admin:
            self.lbl_error.configure(
                text="⚠ Ese usuario no tiene permisos de administrador")
            return
        self._aceptar(True)
