"""Ventana raíz: menú lateral + área de contenido que conmuta entre vistas.

Las vistas se crean una sola vez y se apilan; cambiar de sección solo trae al
frente la elegida (tkraise), así la Caja conserva su carrito al navegar.
"""
from tkinter import messagebox

import customtkinter as ctk

from config import settings
from app.core.sync_manager import SyncManager
from app.core import updater
from app.ui.views.ventas_view import VentasView
from app.ui.views.stock_view import StockView
from app.ui.views.proveedores_view import ProveedoresView
from app.ui.views.clientes_view import ClientesView
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
                side, text=texto, anchor="w", height=44,
                fg_color="transparent", text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray30"),
                command=lambda k=clave: self.mostrar(k))
            btn.pack(fill="x", padx=12, pady=4)
            self._botones[clave] = btn

        # --- Pie del menú: versión + botón de actualización ---
        self.btn_update = ctk.CTkButton(
            side, text="Buscar actualización", height=36,
            fg_color="transparent", text_color=("gray10", "gray90"),
            hover_color=("gray80", "gray30"),
            command=self._buscar_actualizacion)
        self.btn_update.pack(side="bottom", fill="x", padx=12, pady=(4, 12))
        ctk.CTkLabel(side, text=f"v{settings.APP_VERSION}",
                     text_color="gray").pack(side="bottom", pady=(0, 2))

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
        # Cerrar la app para que el .bat pueda reemplazar el .exe.
        self.sync.stop()
        self.destroy()

    def _al_cerrar(self) -> None:
        self.sync.stop()
        self.destroy()
