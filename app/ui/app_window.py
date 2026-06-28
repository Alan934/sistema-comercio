"""Ventana raíz de la aplicación."""
import customtkinter as ctk

from config import settings
from app.ui.views.ventas_view import VentasView

ctk.set_appearance_mode("light")       # 'light' | 'dark' | 'system'
ctk.set_default_color_theme("blue")


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{settings.APP_NOMBRE} v{settings.APP_VERSION}")
        self.geometry("1024x680")
        self.minsize(900, 600)

        # Por ahora la app es directamente la caja. Más adelante,
        # acá va un menú lateral para Stock, Proveedores, Reportes, etc.
        self.vista = VentasView(self)
        self.vista.pack(fill="both", expand=True)
