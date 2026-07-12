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

        # Overlay "Cargando…": se muestra sobre el contenido apenas se hace click
        # en una sección, ANTES de reconstruir la tabla (que bloquea un momento),
        # así el usuario ve que su click se registró. Se crea oculto.
        self._overlay = ctk.CTkFrame(contenido, fg_color=theme.APP_BG,
                                     corner_radius=0)
        self._overlay_lbl = ctk.CTkLabel(
            self._overlay, text="⏳   Cargando…", font=theme.fuente(17, "bold"),
            text_color=theme.TXT_MUTED)
        self._overlay_lbl.place(relx=0.5, rely=0.5, anchor="center")

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
        etiquetas = self._etiquetas = {
            "caja": "Caja", "stock": "Stock", "carne": "Carne",
            "proveedores": "Proveedores", "clientes": "Clientes",
            "reportes": "Reportes", "cierres": "Cierre de caja",
            "usuarios": "Usuarios"}
        # Íconos (emoji: peso 0, no requieren imágenes ni Pillow).
        iconos = {"caja": "🛒", "stock": "📦", "carne": "🥩", "proveedores": "🚚",
                  "clientes": "👥", "reportes": "📊", "cierres": "💰",
                  "usuarios": "👤"}
        # Atajos de teclado para saltar entre secciones (Ctrl+1..8). La tecla es
        # fija por sección (no depende del rol), así la memoria muscular no cambia
        # aunque un rol tenga menos secciones. Se muestran en el botón y se
        # enlazan más abajo.
        atajos = {"caja": "1", "stock": "2", "carne": "3", "proveedores": "4",
                  "clientes": "5", "reportes": "6", "cierres": "7",
                  "usuarios": "8"}
        secciones = SECCIONES_POR_ROL.get(usuario.rol, ["caja"])

        # Bandera anti-doble-click: mientras una sección se está cargando
        # ignoramos los clicks que llegan (ver mostrar()).
        self._cargando = False

        self._vistas = {}
        self._botones = {}
        self._hints = {}
        for clave in secciones:
            vista = constructores[clave]()
            # Fondo OPACO (mismo color que el área de contenido): las vistas se
            # apilan en la misma celda y se alternan con tkraise. Con fondo
            # "transparent" la vista de adelante no tapa a la de atrás, y mientras
            # una vista lenta (ej. Stock, que dibuja muchas filas) termina de
            # pintarse, se ve la vista anterior transparentándose por detrás. Un
            # fondo opaco del mismo color se ve igual pero oculta a las demás.
            vista.configure(fg_color=theme.APP_BG)
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
            # Pista del atajo, alineada a la derecha del botón. El fondo se pinta
            # explícito (no "transparent"): sobre el botón, "transparent" se
            # resuelve al color del marco de la barra lateral y no al color que
            # el botón dibuja encima, así que en el botón activo quedaba un
            # recuadro oscuro. Lo mantenemos igual al color del botón por estado.
            hint = ctk.CTkLabel(btn, text=f"Ctrl+{atajos[clave]}",
                                font=theme.fuente(11), fg_color=theme.SIDEBAR_BG,
                                text_color=theme.NAV_TXT_INACT)
            hint.place(relx=1.0, rely=0.5, anchor="e", x=-12)
            hint.bind("<Button-1>", lambda _e, k=clave: self.mostrar(k))
            # El botón cambia de color al pasar el mouse; la pista lo acompaña.
            btn.bind("<Enter>", lambda _e, k=clave: self._hint_hover(k, True))
            btn.bind("<Leave>", lambda _e, k=clave: self._hint_hover(k, False))
            self._hints[clave] = hint
            # Atajo de teclado: Ctrl+N salta a esta sección desde cualquier
            # lado. Usamos <Control-Key-N> (y no <Control-N>, que en Tk sería
            # Ctrl+click del botón 1 del mouse).
            self.bind(f"<Control-Key-{atajos[clave]}>",
                      lambda _e, k=clave: self.mostrar(k))

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
        # Anti-doble-click: la carga de una sección bloquea el hilo un momento
        # (recarga de datos + armado de la tabla). Durante ese rato Tkinter
        # ENCOLA los clicks que el usuario siga haciendo y, al terminar, los
        # despacha de golpe, recargando la vista N veces. Con este guard el
        # primer click carga y los siguientes se ignoran hasta que termina.
        if self._cargando:
            return
        self._cargando = True
        try:
            self._activa = clave
            vista = self._vistas[clave]

            # 1) Feedback inmediato del click: resaltar el botón y mostrar el
            #    overlay "Cargando…". Forzamos el repintado ANTES de reconstruir
            #    la tabla (que bloquea un momento) para que el usuario vea que
            #    entró ya.
            for k, btn in self._botones.items():
                if k == clave:
                    btn.configure(fg_color=theme.NAV_ACTIVE_BG,
                                  text_color="#FFFFFF")
                    self._hints[k].configure(fg_color=theme.NAV_ACTIVE_BG,
                                             text_color="#FFFFFF")
                else:
                    btn.configure(fg_color="transparent",
                                  text_color=theme.NAV_TXT_INACT)
                    self._hints[k].configure(fg_color=theme.SIDEBAR_BG,
                                             text_color=theme.NAV_TXT_INACT)
            self._overlay_lbl.configure(
                text=f"⏳   Cargando {self._etiquetas.get(clave, '')}…")
            self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._overlay.lift()
            self.update_idletasks()  # pinta botón + overlay antes de bloquear

            # 2) Trabajo pesado (recarga de datos + reconstrucción de la tabla),
            #    tapado por el overlay para que no se vea el reacomodo de columnas.
            if hasattr(vista, "al_mostrar"):
                vista.al_mostrar()
            vista.update_idletasks()

            # 3) Revelar la vista ya armada y quitar el overlay.
            vista.tkraise()
            self._overlay.place_forget()
        finally:
            # Descarta la ráfaga de clicks encolados durante la carga: al
            # procesarlos ahora, el guard (aún en True) los rechaza. Recién
            # después liberamos la bandera.
            self.update()
            self._cargando = False

    def _hint_hover(self, clave: str, entrando: bool) -> None:
        """Acompaña el hover del botón: pinta el fondo de la pista con el color
        de hover al entrar y lo devuelve al de la barra al salir. El botón
        activo conserva su fondo resaltado (no reacciona al hover)."""
        if clave == getattr(self, "_activa", None):
            return
        self._hints[clave].configure(
            fg_color=theme.NAV_HOVER if entrando else theme.SIDEBAR_BG)

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
