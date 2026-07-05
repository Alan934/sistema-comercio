"""Diálogos temáticos que reemplazan a `messagebox` (los cuadros grises del
sistema operativo) por modales que respetan la paleta teal y el modo claro/oscuro.

- `informar(widget, titulo, mensaje)`  -> aviso con un botón "Entendido".
- `error(widget, titulo, mensaje)`     -> aviso de error (acento rojo).
- `confirmar(widget, titulo, mensaje)` -> devuelve True/False (sí/no).

Bloquean como los messagebox, pero se ven como el resto de la app.
"""
import customtkinter as ctk

from app.ui import theme
from app.ui.dialogs.base import ModalBase

_ICONOS = {
    "ok": (theme.VERDE, "✓"),
    "error": (theme.ROJO, "✕"),
    "info": (theme.ACCENT, "ℹ"),
    "pregunta": (theme.ACCENT, "?"),
}


class _AvisoDialog(ModalBase):
    def __init__(self, master, titulo, mensaje, tipo="info",
                 confirmar_txt="Entendido", cancelar_txt=None):
        super().__init__(master, titulo)
        color, icono = _ICONOS.get(tipo, _ICONOS["info"])

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(padx=28, pady=(26, 8), fill="x")

        ctk.CTkLabel(cont, text=icono, width=48, height=48, corner_radius=24,
                     fg_color=color, text_color="#FFFFFF",
                     font=theme.fuente(24, "bold")).grid(
            row=0, column=0, rowspan=2, padx=(0, 16))
        ctk.CTkLabel(cont, text=titulo, anchor="w", font=theme.fuente(18, "bold"),
                     text_color=theme.TXT).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(cont, text=mensaje, anchor="w", justify="left",
                     wraplength=360, font=theme.fuente(14),
                     text_color=theme.TXT_MUTED).grid(row=1, column=1, sticky="w",
                                                      pady=(2, 0))

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=(12, 22))
        if cancelar_txt is not None:
            ctk.CTkButton(botones, text=cancelar_txt, width=120, height=40,
                          corner_radius=10, fg_color="transparent",
                          text_color=theme.TXT_MUTED, border_width=1,
                          border_color=theme.GHOST, hover_color=theme.GHOST,
                          command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(botones, text=confirmar_txt, width=150, height=40,
                      corner_radius=10, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=lambda: self._aceptar(True)).pack(side="left", padx=8)

        self._activar_enter()

    def _confirmar(self):  # para el Enter de ModalBase
        self._aceptar(True)


def informar(widget, titulo, mensaje, tipo="ok"):
    _AvisoDialog(widget, titulo, mensaje, tipo=tipo).mostrar()


def error(widget, titulo, mensaje):
    _AvisoDialog(widget, titulo, mensaje, tipo="error").mostrar()


def confirmar(widget, titulo, mensaje, confirmar_txt="Sí", cancelar_txt="No") -> bool:
    res = _AvisoDialog(widget, titulo, mensaje, tipo="pregunta",
                       confirmar_txt=confirmar_txt,
                       cancelar_txt=cancelar_txt).mostrar()
    return res is True
