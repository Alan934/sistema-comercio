"""Ventana raíz: menú lateral (sidebar de marca) + área de contenido que
conmuta entre vistas.

Las vistas se crean una sola vez y se apilan; cambiar de sección solo trae al
frente la elegida (tkraise), así la Caja conserva su carrito al navegar.
"""
from tkinter import messagebox

import customtkinter as ctk

from config import settings
from app.core.sync_manager import SyncManager
from app.core import updater
from app.ui import theme
from app.ui.views.ventas_view import VentasView
from app.ui.views.stock_view import StockView
from app.ui.views.proveedores_view import ProveedoresView
from app.ui.views.clientes_view import ClientesView
from app.ui.views.reportes_view import ReportesView

ctk.set_appearance_mode(theme.cargar_apariencia())
ctk.set_default_color_theme("green")   # armoniza los botones por defecto con el teal


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{settings.APP_NOMBRE} v{settings.APP_VERSION}")
        self.geometry("1180x740")
        self.minsize(1040, 660)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar de marca ---
        side = ctk.CTkFrame(self, width=190, corner_radius=0, fg_color=theme.SIDEBAR_BG)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)

        marca = ctk.CTkFrame(side, fg_color="transparent")
        marca.pack(fill="x", padx=16, pady=(20, 22))
        ctk.CTkLabel(marca, text="K", width=34, height=34,
                     corner_radius=8, fg_color=theme.BRAND_MARK_BG,
                     text_color=theme.BRAND_MARK_FG,
                     font=theme.fuente(18, "bold")).pack(side="left")
        ctk.CTkLabel(marca, text="Kiosko", text_color=theme.NAV_TXT,
                     font=theme.fuente(17, "bold")).pack(side="left", padx=10)

        # --- Área de contenido ---
        contenido = ctk.CTkFrame(self, fg_color=theme.APP_BG, corner_radius=0)
        contenido.grid(row=0, column=1, sticky="nsew")
        contenido.grid_rowconfigure(0, weight=1)
        contenido.grid_columnconfigure(0, weight=1)

        self._vistas = {
            "caja": VentasView(contenido),
            "stock": StockView(contenido),
            "proveedores": ProveedoresView(contenido),
            "clientes": ClientesView(contenido),
            "reportes": ReportesView(contenido),
        }
        for vista in self._vistas.values():
            vista.grid(row=0, column=0, sticky="nsew")

        # --- Botones de navegación ---
        self._botones = {}
        for clave, texto in [("caja", "Caja"), ("stock", "Stock"),
                             ("proveedores", "Proveedores"),
                             ("clientes", "Clientes"),
                             ("reportes", "Reportes")]:
            btn = ctk.CTkButton(
                side, text=texto, anchor="w", height=42, corner_radius=8,
                font=theme.fuente(14), fg_color="transparent",
                text_color=theme.NAV_TXT_INACT, hover_color=theme.NAV_HOVER,
                command=lambda k=clave: self.mostrar(k))
            btn.pack(fill="x", padx=12, pady=3)
            self._botones[clave] = btn

        # --- Pie: tema, versión y actualización ---
        self.btn_update = ctk.CTkButton(
            side, text="Buscar actualización", height=34, corner_radius=8,
            font=theme.fuente(13), fg_color="transparent",
            text_color=theme.NAV_TXT_INACT, hover_color=theme.NAV_HOVER,
            command=self._buscar_actualizacion)
        self.btn_update.pack(side="bottom", fill="x", padx=12, pady=(4, 14))
        ctk.CTkLabel(side, text=f"v{settings.APP_VERSION}",
                     text_color=theme.NAV_TXT_INACT,
                     font=theme.fuente(12)).pack(side="bottom", pady=(0, 2))
        modo = ctk.get_appearance_mode().lower()
        self.btn_tema = ctk.CTkButton(
            side, text="Modo claro" if modo == "dark" else "Modo oscuro",
            height=34, corner_radius=8, font=theme.fuente(13),
            fg_color="transparent", text_color=theme.NAV_TXT_INACT,
            hover_color=theme.NAV_HOVER, command=self._toggle_tema)
        self.btn_tema.pack(side="bottom", fill="x", padx=12, pady=(4, 2))

        self.mostrar("caja")

        # --- Sincronización en segundo plano ---
        self.sync = SyncManager()
        self.sync.start()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    def mostrar(self, clave: str) -> None:
        self._activa = clave
        vista = self._vistas[clave]
        if hasattr(vista, "al_mostrar"):
            vista.al_mostrar()
        vista.tkraise()
        for k, btn in self._botones.items():
            if k == clave:
                btn.configure(fg_color=theme.NAV_ACTIVE_BG, text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent",
                              text_color=theme.NAV_TXT_INACT)

    def _toggle_tema(self) -> None:
        nuevo = "dark" if ctk.get_appearance_mode().lower() == "light" else "light"
        ctk.set_appearance_mode(nuevo)
        theme.guardar_apariencia(nuevo)
        self.btn_tema.configure(text="Modo claro" if nuevo == "dark"
                                else "Modo oscuro")
        # Redibuja la vista activa (los gráficos en Canvas necesitan repintarse
        # con los colores del nuevo modo).
        vista = self._vistas.get(self._activa)
        if vista is not None and hasattr(vista, "al_mostrar"):
            vista.al_mostrar()

    def _buscar_actualizacion(self) -> None:
        self.btn_update.configure(text="Buscando...")
        self.update_idletasks()
        res = updater.buscar_actualizacion()
        self.btn_update.configure(text="Buscar actualización")

        if not res["ok"]:
            messagebox.showwarning(
                "Actualización", f"No se pudo verificar:\n{res['motivo']}")
            return
        if not res["hay"]:
            messagebox.showinfo("Actualización", res.get("motivo", "Estás al día."))
            return
        if not updater.esta_compilado():
            messagebox.showinfo(
                "Actualización",
                f"Hay una versión nueva (v{res['version']}), pero la "
                "actualización automática solo funciona en el .exe compilado.")
            return
        if not messagebox.askyesno(
                "Actualización disponible",
                f"Versión nueva: v{res['version']}\n\n"
                "¿Descargar e instalar ahora? La app se cerrará y volverá a "
                "abrirse sola (puede tardar un momento)."):
            return
        try:
            self.btn_update.configure(text="Descargando...")
            self.update_idletasks()
            updater.aplicar_actualizacion(res)
        except Exception as e:  # noqa: BLE001
            self.btn_update.configure(text="Buscar actualización")
            messagebox.showerror("Error al actualizar", str(e))
            return
        self.sync.stop()
        self.destroy()

    def _al_cerrar(self) -> None:
        self.sync.stop()
        self.destroy()
