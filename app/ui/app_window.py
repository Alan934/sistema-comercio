"""Ventana raíz: menú lateral (sidebar de marca) + área de contenido que
conmuta entre vistas.

Las vistas se crean una sola vez y se apilan; cambiar de sección solo trae al
frente la elegida (tkraise), así la Caja conserva su carrito al navegar.
"""
import customtkinter as ctk

from config import settings
from app.core.sync_manager import SyncManager
from app.core import updater
from app.ui import theme
from app.ui.scan_catcher import ScanCatcher
from app.ui.dialogs import notificar
from app.models.usuario import SECCIONES_POR_ROL, etiqueta_rol
from app.ui.views.ventas_view import VentasView
from app.ui.views.stock_view import StockView
from app.ui.views.carne_view import CarneView
from app.ui.views.proveedores_view import ProveedoresView
from app.ui.views.clientes_view import ClientesView
from app.ui.views.reportes_view import ReportesView
from app.ui.views.cierres_view import CierresView
from app.ui.views.usuarios_view import UsuariosView

ctk.set_appearance_mode(theme.cargar_apariencia())
ctk.set_default_color_theme("green")   # armoniza los botones por defecto con el teal


class AppWindow(ctk.CTk):
    def __init__(self, usuario):
        super().__init__()
        self.usuario = usuario
        self.cerrar_sesion = False
        self.title(f"{settings.APP_NOMBRE} v{settings.APP_VERSION}")
        self.minsize(900, 600)
        # Abre grande (88% de la pantalla, no completa): es la única app en uso
        # y casi siempre se maximiza. Se adapta a cualquier monitor.
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self._centrar_ventana(int(sw * 0.88), int(sh * 0.88))
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

        # --- Vistas y navegación según el ROL del usuario ---
        constructores = {
            "caja": lambda: VentasView(contenido),
            "stock": lambda: StockView(contenido),
            "carne": lambda: CarneView(contenido),
            "proveedores": lambda: ProveedoresView(contenido),
            "clientes": lambda: ClientesView(contenido, self.usuario),
            "reportes": lambda: ReportesView(contenido),
            "cierres": lambda: CierresView(contenido, self.usuario),
            "usuarios": lambda: UsuariosView(contenido, self.usuario),
        }
        etiquetas = {"caja": "Caja", "stock": "Stock", "carne": "Carne",
                     "proveedores": "Proveedores", "clientes": "Clientes",
                     "reportes": "Reportes", "cierres": "Cierre de caja",
                     "usuarios": "Usuarios"}
        # Íconos (emoji: peso 0, no requieren imágenes ni Pillow).
        iconos = {"caja": "🛒", "stock": "📦", "carne": "🥩", "proveedores": "🚚",
                  "clientes": "👥", "reportes": "📊", "cierres": "💰",
                  "usuarios": "👤"}
        secciones = SECCIONES_POR_ROL.get(usuario.rol, ["caja"])

        self._vistas = {}
        self._botones = {}
        for clave in secciones:
            vista = constructores[clave]()
            vista.grid(row=0, column=0, sticky="nsew")
            self._vistas[clave] = vista
            btn = ctk.CTkButton(
                side, text=f"{iconos[clave]}   {etiquetas[clave]}", anchor="w",
                height=44, corner_radius=8, font=theme.fuente(14),
                fg_color="transparent", text_color=theme.NAV_TXT_INACT,
                hover_color=theme.NAV_HOVER,
                command=lambda k=clave: self.mostrar(k))
            btn.pack(fill="x", padx=12, pady=3)
            self._botones[clave] = btn

        # --- Pie: usuario, cerrar sesión, tema, versión y actualización ---
        self.btn_update = ctk.CTkButton(
            side, text="⟳   Buscar actualización", anchor="w", height=36,
            corner_radius=8, font=theme.fuente(13), fg_color="transparent",
            text_color=theme.NAV_TXT_INACT, hover_color=theme.NAV_HOVER,
            command=self._buscar_actualizacion)
        self.btn_update.pack(side="bottom", fill="x", padx=12, pady=(4, 14))
        ctk.CTkLabel(side, text=f"v{settings.APP_VERSION}",
                     text_color=theme.NAV_TXT_INACT,
                     font=theme.fuente(12)).pack(side="bottom", pady=(0, 2))
        modo = ctk.get_appearance_mode().lower()
        self.btn_tema = ctk.CTkButton(
            side, text="☀   Modo claro" if modo == "dark" else "🌙   Modo oscuro",
            anchor="w", height=36, corner_radius=8, font=theme.fuente(13),
            fg_color="transparent", text_color=theme.NAV_TXT_INACT,
            hover_color=theme.NAV_HOVER, command=self._toggle_tema)
        self.btn_tema.pack(side="bottom", fill="x", padx=12, pady=(4, 2))

        # Usuario actual + cerrar sesión (arriba del cluster inferior).
        ctk.CTkButton(
            side, text="🚪   Cerrar sesión", anchor="w", height=36,
            corner_radius=8, font=theme.fuente(13), fg_color="transparent",
            text_color=theme.NAV_TXT_INACT, hover_color=theme.NAV_HOVER,
            command=self._cerrar_sesion).pack(side="bottom", fill="x",
                                              padx=12, pady=(4, 2))
        # Separador tenue entre la navegación y el cluster inferior.
        ctk.CTkFrame(side, height=1, fg_color=theme.NAV_ACTIVE_BG).pack(
            side="bottom", fill="x", padx=12, pady=(6, 6))
        rol_txt = etiqueta_rol(usuario.rol)
        cuenta = ctk.CTkFrame(side, fg_color="transparent")
        cuenta.pack(side="bottom", fill="x", padx=12, pady=(0, 2))
        ctk.CTkLabel(cuenta, text="👤", font=theme.fuente(16)).pack(side="left")
        ctk.CTkLabel(cuenta, text=f"{usuario.username}\n{rol_txt}",
                     justify="left", anchor="w", text_color=theme.NAV_TXT,
                     font=theme.fuente(12)).pack(side="left", padx=8)

        self.mostrar(secciones[0])

        # --- Captura global del lector de código de barra ---
        # Escanear funciona en Caja/Stock sin importar dónde esté el foco: el
        # catcher detecta la ráfaga de la pistola y la enruta a la vista activa.
        self._scan = ScanCatcher(self, self._enrutar_escaneo)

        # --- Sincronización en segundo plano ---
        self.sync = SyncManager()
        self.sync.start()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    def _centrar_ventana(self, w: int, h: int) -> None:
        """Abre la ventana centrada. Si la pantalla es más chica que la ventana,
        la achica para que entre (deja margen para la barra de tareas)."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(w, sw)
        h = min(h, sh - 50)
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _enrutar_escaneo(self, codigo: str) -> None:
        """Le entrega el código escaneado a la vista activa si sabe procesarlo
        (Caja lo agrega al carrito, Stock lo muestra o abre el alta)."""
        vista = self._vistas.get(self._activa)
        if vista is not None and hasattr(vista, "recibir_escaneo"):
            vista.recibir_escaneo(codigo)

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
            notificar.error(self, "Actualización",
                            f"No se pudo verificar: {res['motivo']}")
            return
        if not res["hay"]:
            notificar.informar(self, "Actualización",
                               res.get("motivo", "Estás al día."), tipo="ok")
            return
        if not updater.esta_compilado():
            notificar.informar(
                self, "Actualización",
                f"Hay una versión nueva (v{res['version']}), pero la "
                "actualización automática solo funciona en el .exe compilado.",
                tipo="info")
            return
        if not notificar.confirmar(
                self, "Actualización disponible",
                f"Versión nueva: v{res['version']}. ¿Descargar e instalar ahora? "
                "La app se cerrará y volverá a abrirse sola (puede tardar un "
                "momento).",
                confirmar_txt="Actualizar ahora", cancelar_txt="Después"):
            return
        try:
            self.btn_update.configure(text="Descargando...")
            self.update_idletasks()
            updater.aplicar_actualizacion(res)
        except Exception as e:  # noqa: BLE001
            self.btn_update.configure(text="Buscar actualización")
            notificar.error(self, "Error al actualizar", str(e))
            return
        self.sync.stop()
        self.destroy()

    def _cerrar_sesion(self) -> None:
        self.cerrar_sesion = True
        self.sync.stop()
        self.destroy()

    def _al_cerrar(self) -> None:
        self.sync.stop()
        self.destroy()
