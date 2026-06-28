"""Ventana raíz: menú lateral + área de contenido que conmuta entre vistas.

Las vistas se crean una sola vez y se apilan; cambiar de sección solo trae al
frente la elegida (tkraise), así la Caja conserva su carrito al navegar.
"""
import customtkinter as ctk

from config import settings
from app.core.sync_manager import SyncManager
from app.ui.views.ventas_view import VentasView
from app.ui.views.stock_view import StockView
from app.ui.views.proveedores_view import ProveedoresView
from app.ui.views.reportes_view import ReportesView

ctk.set_appearance_mode("light")       # 'light' | 'dark' | 'system'
ctk.set_default_color_theme("blue")


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{settings.APP_NOMBRE} v{settings.APP_VERSION}")
        self.geometry("1120x720")
        self.minsize(1000, 640)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Menú lateral ---
        side = ctk.CTkFrame(self, width=190, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text=settings.APP_NOMBRE,
                     font=("", 20, "bold")).pack(padx=16, pady=(24, 20))

        # --- Área de contenido ---
        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.grid(row=0, column=1, sticky="nsew")
        contenido.grid_rowconfigure(0, weight=1)
        contenido.grid_columnconfigure(0, weight=1)

        self._vistas = {
            "caja": VentasView(contenido),
            "stock": StockView(contenido),
            "proveedores": ProveedoresView(contenido),
            "reportes": ReportesView(contenido),
        }
        for vista in self._vistas.values():
            vista.grid(row=0, column=0, sticky="nsew")

        # --- Botones de navegación ---
        self._botones = {}
        for clave, texto in [("caja", "Caja"), ("stock", "Stock"),
                             ("proveedores", "Proveedores"),
                             ("reportes", "Reportes")]:
            btn = ctk.CTkButton(
                side, text=texto, anchor="w", height=44,
                fg_color="transparent", text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray30"),
                command=lambda k=clave: self.mostrar(k))
            btn.pack(fill="x", padx=12, pady=4)
            self._botones[clave] = btn

        self.mostrar("caja")

        # --- Sincronización en segundo plano ---
        self.sync = SyncManager()
        self.sync.start()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    def mostrar(self, clave: str) -> None:
        vista = self._vistas[clave]
        if hasattr(vista, "al_mostrar"):
            vista.al_mostrar()
        vista.tkraise()
        for k, btn in self._botones.items():
            btn.configure(fg_color=("gray75", "gray25") if k == clave
                          else "transparent")

    def _al_cerrar(self) -> None:
        self.sync.stop()
        self.destroy()
