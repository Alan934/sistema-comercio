"""Vista de Stock: listado de productos, alta/edición, recepción de remitos
y alertas (stock bajo y vencimientos)."""
from decimal import Decimal

import customtkinter as ctk

from app.core import formato

from app.services import stock_service, compra_service
from app.ui import theme
from app.ui.toast import mostrar_toast
from app.ui.dialogs import notificar
from app.ui.autocomplete import AutocompleteSimple
from app.ui.dialogs.producto_dialog import ProductoDialog
from app.ui.dialogs.remito_dialog import RemitoDialog
from app.ui.dialogs.categorias_dialog import CategoriasManager
from app.ui.dialogs.alertas_dialog import AlertasDialog
from app.ui.dialogs.vencimientos_dialog import VencimientosDialog


def _money(v) -> str:
    return formato.moneda(v)


# Ancho fijo de la celda de acciones (botón Vencim. + Editar). Se reserva igual
# en TODAS las filas —tengan o no el botón de vencimiento— para que las columnas
# queden alineadas con el encabezado (si no, la fila con Vencim. corre el resto).
ANCHO_VENCIM = 108   # 104 del botón + 4 de separación
ANCHO_EDITAR = 100
ANCHO_ACC = ANCHO_VENCIM + ANCHO_EDITAR


class StockView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._productos = []
        self._venc_map = {}
        # True cuando el campo de escaneo muestra un código ya buscado: el
        # próximo carácter nuevo arranca un código distinto (no concatena).
        self._scan_listo = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- Encabezado: título + búsqueda + acciones ---
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Stock", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        self.ent_buscar = ctk.CTkEntry(
            top, placeholder_text="Buscar por nombre…", width=240, height=38,
            corner_radius=10, font=theme.fuente(14))
        self.ent_buscar.grid(row=0, column=1, sticky="e", padx=8)
        self.ent_buscar.bind("<KeyRelease>", lambda _e: self._render_tabla())
        ctk.CTkButton(top, text="Categorías", width=110, height=38,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color="transparent", text_color=theme.ACCENT,
                      border_width=1, border_color=theme.GHOST,
                      hover_color=theme.GHOST,
                      command=self._gestionar_categorias).grid(row=0, column=2, padx=4)
        ctk.CTkButton(top, text="Nuevo producto", width=140, height=38,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color="transparent", text_color=theme.ACCENT,
                      border_width=1, border_color=theme.GHOST,
                      hover_color=theme.GHOST,
                      command=self._nuevo_producto).grid(row=0, column=3, padx=4)
        ctk.CTkButton(top, text="Recibir remito", width=140, height=38,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._recibir_remito).grid(row=0, column=4)

        # Lector de código de barra (segunda línea): la pistolita escribe acá y
        # al Enter, si el código existe muestra el producto para ver su stock; si
        # no existe, abre el alta con el código ya cargado.
        ctk.CTkLabel(top, text="Escanear:", font=theme.fuente(13, "bold"),
                     text_color=theme.ACCENT).grid(row=1, column=0, sticky="w",
                                                   pady=(8, 0))
        self.ent_scan = ctk.CTkEntry(
            top, height=38, corner_radius=10, font=theme.fuente(15),
            placeholder_text="Escaneá un código con la pistola…")
        self.ent_scan.grid(row=1, column=1, columnspan=4, sticky="ew",
                           padx=8, pady=(8, 0))
        self.ent_scan.bind("<Return>", self._on_scan)
        self.ent_scan.bind("<KP_Enter>", self._on_scan)
        # Empezar un código nuevo tras uno ya buscado (pistola o tecleo) limpia
        # el anterior; vaciar el código a mano limpia también el nombre.
        self.ent_scan.bind("<Key>", self._scan_nueva_tecla, add="+")
        self.ent_scan.bind("<KeyRelease>", self._scan_editado, add="+")

        # Filtro por ubicación (tercera línea del encabezado): campo con
        # autocompletado que filtra la ubicación mientras se escribe.
        ctk.CTkLabel(top, text="Ubicación:", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(row=2, column=0, sticky="w",
                                                      pady=(8, 0))
        self.ent_ubic = ctk.CTkEntry(
            top, width=220, height=32, font=theme.fuente(13),
            placeholder_text="Todas")
        self.ent_ubic.grid(row=2, column=1, sticky="w", padx=8, pady=(8, 0))
        self._auto_ubic = AutocompleteSimple(
            self.ent_ubic, self, [],
            on_seleccionar=lambda _v: self._render_tabla())
        self.ent_ubic.bind("<KeyRelease>", lambda _e: self._render_tabla(), add="+")

        # --- Banner de alertas ---
        self.banner = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=10)
        self.banner.grid(row=1, column=0, sticky="ew", padx=20, pady=(2, 8))
        self.banner.grid_columnconfigure(0, weight=1)
        self.lbl_alertas = ctk.CTkLabel(self.banner, text="", anchor="w",
                                        font=theme.fuente(14, "bold"))
        self.lbl_alertas.grid(row=0, column=0, sticky="w", padx=16, pady=10)
        self.btn_ver = ctk.CTkButton(self.banner, text="Ver detalle", width=120,
                                     height=32, corner_radius=8,
                                     font=theme.fuente(13, "bold"),
                                     fg_color=theme.ROJO, hover_color=theme.PRIMARY_HOVER,
                                     command=self._ver_alertas)
        self.btn_ver.grid(row=0, column=1, padx=8)

        # --- Encabezado de tabla ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=2, column=0, sticky="ew", padx=28)
        header.grid_columnconfigure(0, weight=1)
        for col, (txt, w) in enumerate(
                [("Producto", 250), ("Código", 130), ("Precio", 100),
                 ("Costo", 100), ("Stock", 80), ("", ANCHO_ACC)]):
            ctk.CTkLabel(header, text=txt, width=w, anchor="w",
                         font=theme.fuente(12, "bold"),
                         text_color=theme.TXT_MUTED).grid(row=0, column=col, padx=4)

        # --- Tabla ---
        self.tabla = ctk.CTkScrollableFrame(self, fg_color=theme.CARD_BG,
                                            corner_radius=12)
        self.tabla.grid(row=3, column=0, sticky="nsew", padx=20, pady=(6, 18))
        self.tabla.grid_columnconfigure(0, weight=1)

    def al_mostrar(self) -> None:
        self._recargar()
        self.after(120, self.ent_scan.focus_set)

    # --- Escaneo ------------------------------------------------------------

    def _on_scan(self, _event=None) -> str:
        """Enter en el campo de escaneo: delega en recibir_escaneo. Devuelve
        'break' para consumir el Enter y que no lo reprocese la captura global.
        No borra el código: si el producto existe, queda a la vista."""
        codigo = self.ent_scan.get().strip()
        self.recibir_escaneo(codigo)
        return "break"

    def _scan_nueva_tecla(self, event) -> None:
        """Tras un escaneo ya resuelto, el primer carácter nuevo (otra pistola o
        tecleo) arranca un código distinto: limpia el anterior para no
        concatenar. No dispara con Enter ni con teclas de edición/navegación."""
        if self._scan_listo and event.char and event.char.isprintable():
            self.ent_scan.delete(0, "end")
            self._scan_listo = False

    def _scan_editado(self, _event=None) -> None:
        """Si el usuario vacía el código a mano, limpia también el nombre para no
        dejar la tabla filtrada por un producto sin código a la vista."""
        if not self.ent_scan.get().strip() and self.ent_buscar.get().strip():
            self.ent_buscar.delete(0, "end")
            self._render_tabla()

    def recibir_escaneo(self, codigo: str) -> None:
        """Procesa un código escaneado, venga del campo de escaneo o de la
        captura global (con el foco en cualquier lado): si existe, muestra el
        producto para ver su stock; si no existe, abre el alta con el código ya
        cargado."""
        codigo = (codigo or "").strip()
        if not codigo:
            self.ent_scan.focus_set()
            return
        prod = stock_service.buscar_por_codigo(codigo)
        if prod is not None:
            # Existe: dejo el código a la vista (por si vino de la captura
            # global) y filtro la tabla por su nombre para que se vea su stock.
            # Ambos campos quedan vinculados: borrar el código limpia el nombre.
            self.ent_scan.delete(0, "end")
            self.ent_scan.insert(0, codigo)
            self._scan_listo = True
            self.ent_ubic.delete(0, "end")
            self.ent_buscar.delete(0, "end")
            self.ent_buscar.insert(0, prod.nombre)
            self._render_tabla()
            stock_txt = (f"{formato.numero(prod.stock_actual)} kg"
                         if prod.es_pesable else formato.numero(prod.stock_actual))
            mostrar_toast(self, f"{prod.nombre} · stock {stock_txt}", tipo="ok")
        else:
            # No existe: alta de producto nuevo con el código precargado.
            self.ent_scan.delete(0, "end")
            self._scan_listo = False
            datos = ProductoDialog(self, codigo_inicial=codigo).mostrar()
            if datos is not None:
                try:
                    stock_service.crear_producto(datos)
                except stock_service.StockError as e:
                    notificar.error(self, "No se pudo crear", str(e))
                    self.ent_scan.focus_set()
                    return
                self._recargar()
                mostrar_toast(self, "Producto creado", tipo="ok")
        self.ent_scan.focus_set()

    # --- Datos --------------------------------------------------------------

    def _recargar(self) -> None:
        self._productos = stock_service.listar_productos()
        self._venc_map = stock_service.vencimientos_por_producto(7)
        self._auto_ubic.set_opciones(stock_service.listar_ubicaciones())
        self._render_tabla()
        self._render_alertas()

    def _render_alertas(self) -> None:
        bajos = stock_service.alertas_stock_bajo()
        vencs = stock_service.alertas_vencimientos(7)
        partes = []
        if bajos:
            partes.append(f"{len(bajos)} con stock bajo")
        if vencs:
            partes.append(f"{len(vencs)} por vencer")
        if partes:
            self.banner.configure(fg_color=theme.ROJO_BG)
            self.lbl_alertas.configure(text="⚠   " + "   ·   ".join(partes),
                                       text_color=theme.ROJO)
            self.btn_ver.grid()
        else:
            self.banner.configure(fg_color=theme.VERDE_BG)
            self.lbl_alertas.configure(text="✓   Sin alertas de stock",
                                       text_color=theme.VERDE)
            self.btn_ver.grid_remove()

    def _render_tabla(self) -> None:
        filtro = self.ent_buscar.get().strip().lower()
        ubic_sel = self.ent_ubic.get().strip().lower()
        for w in self.tabla.winfo_children():
            w.destroy()
        visibles = [
            p for p in self._productos
            if (not filtro or filtro in p.nombre.lower())
            and (not ubic_sel or ubic_sel in (p.ubicacion or "").lower())]
        if not visibles:
            txt = ("No hay productos.\nCargá el primero o recibí un remito."
                   if not filtro and not ubic_sel
                   else "Ningún producto coincide con el filtro.")
            ctk.CTkLabel(self.tabla, text=txt, font=theme.fuente(14),
                         text_color=theme.TXT_MUTED, justify="center").pack(pady=36)
            return
        for i, p in enumerate(visibles):
            f = ctk.CTkFrame(self.tabla,
                             fg_color=theme.ROW_ALT if i % 2 else "transparent",
                             corner_radius=8)
            f.pack(fill="x", padx=6, pady=1)
            f.grid_columnconfigure(0, weight=1)
            stock_txt = (f"{formato.numero(p.stock_actual)} kg" if p.es_pesable else formato.numero(p.stock_actual))
            # Nombre + ubicación (debajo, en gris).
            celda = ctk.CTkFrame(f, fg_color="transparent")
            celda.grid(row=0, column=0, padx=4, sticky="w")
            ctk.CTkLabel(celda, text=p.nombre, width=246, anchor="w",
                         font=theme.fuente(15), text_color=theme.TXT).pack(anchor="w")
            if p.ubicacion:
                ctk.CTkLabel(celda, text=f"Ubic. {p.ubicacion}", anchor="w",
                             font=theme.fuente(11),
                             text_color=theme.TXT_MUTED).pack(anchor="w")
            dias = self._venc_map.get(p.id)
            if dias is not None:
                if dias < 0:
                    txt, color = f"⚠ Vencido hace {-dias} día{'s' if dias != -1 else ''}", theme.ROJO
                elif dias == 0:
                    txt, color = "⚠ Vence hoy", theme.ROJO
                else:
                    txt, color = (f"⚠ Vence en {dias} día{'s' if dias != 1 else ''}",
                                  theme.BADGE_KG_TXT)
                ctk.CTkLabel(celda, text=txt, anchor="w",
                             font=theme.fuente(11, "bold"),
                             text_color=color).pack(anchor="w")
            ctk.CTkLabel(f, text=(p.codigo_barra or "—"), width=130, anchor="w",
                         font=theme.fuente(13), text_color=theme.TXT_MUTED).grid(
                row=0, column=1, padx=4)
            ctk.CTkLabel(f, text=_money(p.precio_venta), width=100, anchor="w",
                         font=theme.fuente(14), text_color=theme.TXT).grid(
                row=0, column=2, padx=4)
            ctk.CTkLabel(f, text=_money(p.costo_compra), width=100, anchor="w",
                         font=theme.fuente(14), text_color=theme.TXT_MUTED).grid(
                row=0, column=3, padx=4)
            ctk.CTkLabel(f, text=stock_txt, width=80, anchor="w",
                         font=theme.fuente(14), text_color=theme.TXT).grid(
                row=0, column=4, padx=4)
            # Ancho fijo (pack_propagate False) para que todas las filas midan
            # lo mismo y queden alineadas, tengan o no el botón de vencimiento.
            acc = ctk.CTkFrame(f, fg_color="transparent",
                               width=ANCHO_ACC, height=32)
            acc.grid(row=0, column=5, padx=4)
            acc.pack_propagate(False)
            if p.controla_vencimiento:
                ctk.CTkButton(acc, text="📅  Vencim.", width=104, height=32,
                              corner_radius=8, font=theme.fuente(13),
                              fg_color="transparent", text_color=theme.ACCENT,
                              hover_color=theme.GHOST,
                              command=lambda pid=p.id, n=p.nombre, ps=p.es_pesable:
                                  self._gestionar_vencimientos(pid, n, ps)).pack(
                    side="left", padx=(0, 4))
            else:
                # Placeholder invisible que reserva el hueco del botón Vencim.
                ctk.CTkFrame(acc, fg_color="transparent",
                             width=ANCHO_VENCIM, height=32).pack(side="left")
            ctk.CTkButton(acc, text="✏  Editar", width=ANCHO_EDITAR, height=32,
                          corner_radius=8, font=theme.fuente(13),
                          fg_color="transparent", text_color=theme.ACCENT,
                          hover_color=theme.GHOST,
                          command=lambda pid=p.id: self._editar_producto(pid)).pack(
                side="left")

    # --- Acciones -----------------------------------------------------------

    def _nuevo_producto(self) -> None:
        datos = ProductoDialog(self).mostrar()
        if datos is None:
            return
        try:
            stock_service.crear_producto(datos)
        except stock_service.StockError as e:
            notificar.error(self, "No se pudo crear", str(e))
            return
        self._recargar()
        mostrar_toast(self, "Producto creado", tipo="ok")

    def _editar_producto(self, producto_id: str) -> None:
        actual = stock_service.obtener_producto(producto_id)
        if actual is None:
            return
        datos = ProductoDialog(self, producto=actual).mostrar()
        if datos is None:
            return
        try:
            stock_service.actualizar_producto(producto_id, datos)
        except stock_service.StockError as e:
            notificar.error(self, "No se pudo guardar", str(e))
            return
        self._recargar()
        mostrar_toast(self, "Cambios guardados", tipo="ok")

    def _recibir_remito(self) -> None:
        remito = RemitoDialog(self).mostrar()
        if remito is None:
            return
        try:
            compra_service.registrar_compra(
                remito["proveedor_id"], remito["items"],
                nro_remito=remito["nro_remito"], condicion=remito["condicion"])
        except compra_service.CompraError as e:
            notificar.error(self, "No se pudo registrar el remito", str(e))
            return
        self._recargar()
        mostrar_toast(self, "Remito registrado · stock y costos actualizados",
                      tipo="ok")

    def _gestionar_vencimientos(self, producto_id: str, nombre: str,
                                es_pesable: bool = False) -> None:
        VencimientosDialog(self, producto_id, nombre, es_pesable).mostrar()
        self._recargar()  # cambió el mapa de vencimientos / alertas

    def _gestionar_categorias(self) -> None:
        CategoriasManager(self).mostrar()
        self._recargar()  # los precios pueden haber cambiado

    def _ver_alertas(self) -> None:
        bajos = stock_service.alertas_stock_bajo()
        vencs = stock_service.alertas_vencimientos(7)
        AlertasDialog(self, bajos, vencs).mostrar()
