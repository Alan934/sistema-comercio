"""Ventana de ingreso: login o, si no hay usuarios, creación del administrador.

Al terminar, deja el usuario autenticado en self.usuario (o None si se cerró).
"""
import customtkinter as ctk

from config import settings
from app.services import usuario_service
from app.ui import theme

ctk.set_appearance_mode(theme.cargar_apariencia())
ctk.set_default_color_theme("green")


class AuthWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.usuario = None
        self._setup = not usuario_service.hay_usuarios()

        titulo = "Crear super administrador" if self._setup else "Iniciar sesión"
        self.title(f"{settings.APP_NOMBRE} — {titulo}")
        self.resizable(False, False)
        self._centrar(400, 470 if self._setup else 410)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(expand=True, fill="both", padx=34, pady=24)

        ctk.CTkLabel(cont, text="Kiosko", font=theme.fuente(28, "bold"),
                     text_color=theme.PRIMARY).pack(pady=(6, 2))
        sub = ("Creá el usuario super administrador para empezar." if self._setup
               else "Ingresá con tu usuario y contraseña.")
        ctk.CTkLabel(cont, text=sub, font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).pack(pady=(0, 18))

        ctk.CTkLabel(cont, text="Usuario", anchor="w").pack(fill="x")
        self.ent_user = ctk.CTkEntry(cont, height=42, font=theme.fuente(15))
        self.ent_user.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(cont, text="Contraseña", anchor="w").pack(fill="x")
        self.ent_pass = ctk.CTkEntry(cont, height=42, show="•", font=theme.fuente(15))
        self.ent_pass.pack(fill="x", pady=(2, 12))

        self.ent_pass2 = None
        if self._setup:
            ctk.CTkLabel(cont, text="Repetir contraseña", anchor="w").pack(fill="x")
            self.ent_pass2 = ctk.CTkEntry(cont, height=42, show="•",
                                          font=theme.fuente(15))
            self.ent_pass2.pack(fill="x", pady=(2, 12))

        self.lbl_error = ctk.CTkLabel(cont, text="", text_color="orange")
        self.lbl_error.pack(pady=(0, 4))

        ctk.CTkButton(cont, text="Crear y entrar" if self._setup else "Ingresar",
                      height=46, font=theme.fuente(16, "bold"),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._enviar).pack(fill="x", pady=(6, 0))

        self.bind("<Return>", lambda _e: self._enviar())
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.after(80, self.ent_user.focus_set)

    def _centrar(self, w: int, h: int) -> None:
        x = max(0, (self.winfo_screenwidth() - w) // 2)
        y = max(0, (self.winfo_screenheight() - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _cerrar(self) -> None:
        self.usuario = None
        self.destroy()

    def _enviar(self) -> None:
        user = self.ent_user.get().strip()
        pw = self.ent_pass.get()
        if self._setup:
            if pw != self.ent_pass2.get():
                self.lbl_error.configure(text="Las contraseñas no coinciden")
                return
            try:
                usuario_service.crear_super_admin(user, pw)
            except usuario_service.UsuarioError as e:
                self.lbl_error.configure(text=str(e))
                return
            self.usuario = usuario_service.autenticar(user, pw)
            self.destroy()
        else:
            u = usuario_service.autenticar(user, pw)
            if u is None:
                self.lbl_error.configure(text="Usuario o contraseña incorrectos")
                return
            self.usuario = u
            self.destroy()
