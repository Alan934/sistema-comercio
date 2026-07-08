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


def _money(v) -> str:
    return formato.moneda(v)


class StockView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._productos = []

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

        # Filtro por ubicación (segunda línea del encabezado): campo con
        # autocompletado que filtra la ubicación mientras se escribe.
        ctk.CTkLabel(top, text="Ubicación:", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(row=1, column=0, sticky="w",
                                                      pady=(8, 0))
        self.ent_ubic = ctk.CTkEntry(
            top, width=220, height=32, font=theme.fuente(13),
            placeholder_text="Todas")
        self.ent_ubic.grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
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
                 ("Costo", 100), ("Stock", 80), ("", 80)]):
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

    # --- Datos --------------------------------------------------------------

    def _recargar(self) -> None:
        self._productos = stock_service.listar_productos()
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
            ctk.CTkButton(f, text="✏  Editar", width=100, height=32,
                          corner_radius=8, font=theme.fuente(13),
                          fg_color="transparent", text_color=theme.ACCENT,
                          hover_color=theme.GHOST,
                          command=lambda pid=p.id: self._editar_producto(pid)).grid(
                row=0, column=5, padx=4)

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

    def _gestionar_categorias(self) -> None:
        CategoriasManager(self).mostrar()
        self._recargar()  # los precios pueden haber cambiado

    def _ver_alertas(self) -> None:
        bajos = stock_service.alertas_stock_bajo()
        vencs = stock_service.alertas_vencimientos(7)
        AlertasDialog(self, bajos, vencs).mostrar()
