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
        self.configure(fg_color=theme.APP_BG)
        self._centrar(420, 560 if self._setup else 500)

        # Envoltorio centrado.
        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(expand=True, fill="both", padx=30, pady=26)

        # --- Marca: cuadro "K" teal + nombre ---
        marca = ctk.CTkFrame(cont, fg_color="transparent")
        marca.pack(pady=(4, 18))
        ctk.CTkLabel(marca, text="K", width=48, height=48, corner_radius=12,
                     fg_color=theme.PRIMARY, text_color="#FFFFFF",
                     font=theme.fuente(26, "bold")).pack(side="left")
        ctk.CTkLabel(marca, text="Kiosko", font=theme.fuente(26, "bold"),
                     text_color=theme.TXT).pack(side="left", padx=12)

        # --- Tarjeta con el formulario ---
        card = ctk.CTkFrame(cont, fg_color=theme.CARD_BG, corner_radius=16)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=26, pady=24)

        ctk.CTkLabel(inner, text=titulo, font=theme.fuente(19, "bold"),
                     text_color=theme.TXT, anchor="w").pack(fill="x")
        sub = ("Creá el usuario super administrador para empezar." if self._setup
               else "Ingresá con tu usuario y contraseña.")
        ctk.CTkLabel(inner, text=sub, font=theme.fuente(13),
                     text_color=theme.TXT_MUTED, anchor="w",
                     justify="left", wraplength=320).pack(fill="x", pady=(2, 18))

        ctk.CTkLabel(inner, text="Usuario", anchor="w", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).pack(fill="x")
        self.ent_user = ctk.CTkEntry(inner, height=44, corner_radius=10,
                                     font=theme.fuente(15),
                                     placeholder_text="Tu usuario")
        self.ent_user.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(inner, text="Contraseña", anchor="w", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).pack(fill="x")
        self.ent_pass = self._password_con_ojo(inner, "Tu contraseña")
        self.ent_pass.pack(fill="x", pady=(4, 14))

        self.ent_pass2 = None
        if self._setup:
            ctk.CTkLabel(inner, text="Repetir contraseña", anchor="w",
                         font=theme.fuente(13), text_color=theme.TXT_MUTED).pack(
                fill="x")
            self.ent_pass2 = self._password_con_ojo(inner, "Repetí la contraseña")
            self.ent_pass2.pack(fill="x", pady=(4, 14))

        self.lbl_error = ctk.CTkLabel(inner, text="", text_color=theme.ROJO,
                                      font=theme.fuente(13), anchor="w",
                                      justify="left", wraplength=320)
        self.lbl_error.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(inner, text="Crear y entrar" if self._setup else "Ingresar",
                      height=48, corner_radius=10, font=theme.fuente(16, "bold"),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._enviar).pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(cont, text=f"v{settings.APP_VERSION}",
                     font=theme.fuente(11), text_color=theme.TXT_MUTED).pack(
            side="bottom", pady=(14, 0))

        self.bind("<Return>", lambda _e: self._enviar())
        self.bind("<KeyRelease>", self._limpiar_error, add="+")
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.after(80, self.ent_user.focus_set)

    def _limpiar_error(self, evento=None) -> None:
        """Borra el mensaje de error al escribir (no al confirmar con Enter)."""
        if evento is not None and getattr(evento, "keysym", "") in (
                "Return", "KP_Enter"):
            return
        if self.lbl_error.cget("text"):
            self.lbl_error.configure(text="")

    def _password_con_ojo(self, parent, placeholder: str) -> ctk.CTkEntry:
        """Campo de contraseña con el típico botón de ojito para mostrar/ocultar
        lo escrito. El ojito se ubica dentro del campo, a la derecha."""
        ent = ctk.CTkEntry(parent, height=44, corner_radius=10, show="•",
                           font=theme.fuente(15), placeholder_text=placeholder)
        ojo = ctk.CTkButton(ent, text="👁", width=34, height=34, corner_radius=8,
                            fg_color="transparent", hover_color=theme.GHOST,
                            text_color=theme.TXT_MUTED, font=theme.fuente(15))

        def alternar() -> None:
            if ent.cget("show"):          # está oculta -> mostrar
                ent.configure(show="")
                ojo.configure(text="🙈")
            else:                         # está visible -> ocultar
                ent.configure(show="•")
                ojo.configure(text="👁")

        ojo.configure(command=alternar)
        ojo.place(relx=1.0, rely=0.5, x=-5, anchor="e")
        return ent

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
