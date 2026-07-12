"""Vista de Stock: listado de productos, alta/edición, recepción de remitos
y alertas (stock bajo y vencimientos)."""
from decimal import Decimal
from math import ceil

import customtkinter as ctk

from app.core import formato
from app.core.utils import sin_acentos

from app.services import stock_service, compra_service, categoria_service
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

# Productos por página. Se pagina en vez de dibujar cientos de filas de una
# (cada fila son ~7-9 widgets de CustomTkinter, caros de crear: dibujar cientos
# congela la app en una PC de gama baja). Los filtros corren sobre TODO el
# catálogo y el resultado se pagina.
PAGE_SIZE = 50
# Filas que se pintan por tanda antes de ceder el control al event loop (con
# after). Mantiene la app responsiva mientras la tabla se llena: con tandas
# chicas cada bloqueo dura poco (~60 ms) y el tecleo del buscador se ve fluido
# (si la tanda es grande, los caracteres tipeados aparecen "de a uno").
FILAS_POR_TANDA = 10
# Espera (ms) antes de re-dibujar al tipear en el buscador: evita reconstruir la
# tabla en cada tecla (debounce).
DEBOUNCE_MS = 250
# Mínimo de letras para filtrar por nombre. Con menos, en vez de dibujar cientos
# de filas (lo más caro) se muestra una pista y se espera a que la búsqueda sea
# más específica; así tipear las primeras letras no traba la vista.
MIN_BUSQUEDA = 3

# --- Opciones de los filtros (los textos son también las claves) ------------
CAT_TODAS = "Todas las categorías"
CAT_SIN = "Sin categoría"
EST_TODOS = "Todo el stock"
EST_SItem = "Sin stock"
EST_BAJO = "Stock bajo"
EST_CERCA = "Cerca de bajo"
EST_CON = "Con stock"
ESTADOS = [EST_TODOS, EST_SItem, EST_BAJO, EST_CERCA, EST_CON]
VENC_TODOS = "Vencimiento: todos"
VENC_POR = "Por vencer (7 días)"
VENC_VENCIDOS = "Vencidos"
VENCIMIENTOS = [VENC_TODOS, VENC_POR, VENC_VENCIDOS]
ORD_NOMBRE = "Nombre (A→Z)"
ORD_STOCK = "Menos stock primero"
ORD_PRECIO = "Mayor precio primero"
ORDENES = [ORD_NOMBRE, ORD_STOCK, ORD_PRECIO]
# Factor para "cerca de bajo": por encima del mínimo pero sin pasar este múltiplo.
CERCA_FACTOR = Decimal("1.5")


class StockView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._productos = []
        # nombre normalizado (sin acentos, minúscula) por producto, precalculado
        # en _recargar: filtrar por nombre no recalcula sin_acentos en cada tecla.
        self._nombre_norm = {}
        self._venc_map = {}
        self._cat_por_nombre = {}   # nombre de categoría -> id (para el filtro)
        self._pagina = 0            # página actual (0-based)
        self._visibles = []         # productos que pasan los filtros (todas las páginas)
        # Id del after() pendiente del debounce del buscador (para cancelarlo).
        self._debounce_id = None
        # Id del after() del pintado en tandas en curso (para cancelarlo).
        self._pintar_id = None
        # True cuando el campo de escaneo muestra un código ya buscado: el
        # próximo carácter nuevo arranca un código distinto (no concatena).
        self._scan_listo = False
        # Al escanear un código, la tabla muestra ESE producto exacto (por id),
        # no un filtro por nombre: así aparece aunque su nombre sea muy corto
        # (1-2 letras) o sea subcadena de otros. Cualquier acción de filtrado
        # del usuario lo vuelve a None y retoma la búsqueda normal.
        self._solo_producto_id = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)   # la tabla es la fila que se estira

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
        self.ent_buscar.bind("<KeyRelease>", lambda _e: self._render_debounced())
        ctk.CTkButton(top, text="Categorías", width=110, height=38,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.GHOST_BTN_BG, text_color=theme.ACCENT,
                      border_width=1, border_color=theme.GHOST_BTN_BORDER,
                      hover_color=theme.GHOST_BTN_HOVER,
                      command=self._gestionar_categorias).grid(row=0, column=2, padx=4)
        ctk.CTkButton(top, text="Nuevo producto", width=140, height=38,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.GHOST_BTN_BG, text_color=theme.ACCENT,
                      border_width=1, border_color=theme.GHOST_BTN_BORDER,
                      hover_color=theme.GHOST_BTN_HOVER,
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

        # --- Barra de filtros combinables ---
        self._construir_filtros()

        # --- Banner de alertas ---
        self.banner = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=10)
        self.banner.grid(row=2, column=0, sticky="ew", padx=20, pady=(2, 8))
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
        header.grid(row=3, column=0, sticky="ew", padx=28)
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
        self.tabla.grid(row=4, column=0, sticky="nsew", padx=20, pady=(6, 6))
        self.tabla.grid_columnconfigure(0, weight=1)

        # --- Paginador ---
        pag = ctk.CTkFrame(self, fg_color="transparent")
        pag.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 14))
        pag.grid_columnconfigure(1, weight=1)
        self.btn_prev = ctk.CTkButton(
            pag, text="‹ Anterior", width=110, height=32, corner_radius=8,
            font=theme.fuente(13), fg_color=theme.GHOST_BTN_BG,
            text_color=theme.ACCENT, border_width=1,
            border_color=theme.GHOST_BTN_BORDER, hover_color=theme.GHOST_BTN_HOVER,
            command=self._pagina_prev)
        self.btn_prev.grid(row=0, column=0, sticky="w")
        self.lbl_pagina = ctk.CTkLabel(pag, text="", font=theme.fuente(13),
                                       text_color=theme.TXT_MUTED)
        self.lbl_pagina.grid(row=0, column=1)
        self.btn_next = ctk.CTkButton(
            pag, text="Siguiente ›", width=110, height=32, corner_radius=8,
            font=theme.fuente(13), fg_color=theme.GHOST_BTN_BG,
            text_color=theme.ACCENT, border_width=1,
            border_color=theme.GHOST_BTN_BORDER, hover_color=theme.GHOST_BTN_HOVER,
            command=self._pagina_next)
        self.btn_next.grid(row=0, column=2, sticky="e")

    def _construir_filtros(self) -> None:
        """Barra de filtros combinables (fila 1): categoría, estado de stock,
        vencimiento, ubicación y orden. Cualquier cambio re-filtra y vuelve a la
        página 1."""
        barra = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=10)
        barra.grid(row=1, column=0, sticky="ew", padx=20, pady=(2, 4))
        barra.grid_columnconfigure(6, weight=1)  # empuja "Limpiar" a la derecha

        def _menu(col, values, ancho):
            m = ctk.CTkOptionMenu(
                barra, values=values, width=ancho, height=32,
                font=theme.fuente(13), dropdown_font=theme.fuente(13),
                fg_color=theme.GHOST_BTN_BG, button_color=theme.GHOST_BTN_BG,
                button_hover_color=theme.GHOST_BTN_HOVER, text_color=theme.TXT,
                command=lambda _v: self._filtro_inmediato())
            m.grid(row=0, column=col, padx=(8, 4), pady=8)
            return m

        self._f_categoria = _menu(0, [CAT_TODAS], 200)
        self._f_estado = _menu(1, ESTADOS, 150)
        self._f_venc = _menu(2, VENCIMIENTOS, 170)
        self.ent_ubic = ctk.CTkEntry(barra, width=150, height=32,
                                     font=theme.fuente(13),
                                     placeholder_text="Ubicación")
        self.ent_ubic.grid(row=0, column=3, padx=4, pady=8)
        self._auto_ubic = AutocompleteSimple(
            self.ent_ubic, self, [],
            on_seleccionar=lambda _v: self._filtro_inmediato())
        self.ent_ubic.bind("<KeyRelease>",
                           lambda _e: self._render_debounced(), add="+")
        self._f_orden = _menu(4, ORDENES, 190)
        ctk.CTkButton(barra, text="Limpiar filtros", width=120, height=32,
                      corner_radius=8, font=theme.fuente(13),
                      fg_color="transparent", text_color=theme.ACCENT,
                      hover_color=theme.GHOST,
                      command=self._limpiar_filtros).grid(
            row=0, column=7, padx=(4, 8), pady=8)

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
            self._solo_producto_id = None
            self._pagina = 0
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
            self._solo_producto_id = prod.id
            self._pagina = 0
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
        self._solo_producto_id = None
        self._productos = stock_service.listar_productos()
        self._nombre_norm = {p.id: sin_acentos(p.nombre.lower())
                             for p in self._productos}
        self._venc_map = stock_service.vencimientos_por_producto(7)
        self._auto_ubic.set_opciones(stock_service.listar_ubicaciones())
        self._refrescar_categorias()
        self._pagina = 0
        self._render_tabla()
        self._render_alertas()

    def _refrescar_categorias(self) -> None:
        """Actualiza las opciones del filtro de categoría según las activas."""
        cats = categoria_service.listar_activas()
        self._cat_por_nombre = {c.nombre: c.id for c in cats}
        valores = [CAT_TODAS] + [c.nombre for c in cats] + [CAT_SIN]
        actual = self._f_categoria.get()
        self._f_categoria.configure(values=valores)
        if actual not in valores:
            self._f_categoria.set(CAT_TODAS)

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

    # --- Filtros ------------------------------------------------------------

    def _filtro_inmediato(self) -> None:
        """Un filtro cambió (dropdown/ubicación): vuelve a la 1ra página y dibuja."""
        self._solo_producto_id = None
        self._pagina = 0
        self._render_tabla()

    def _limpiar_filtros(self) -> None:
        self.ent_buscar.delete(0, "end")
        self.ent_ubic.delete(0, "end")
        self.ent_scan.delete(0, "end")
        self._scan_listo = False
        self._solo_producto_id = None
        self._f_categoria.set(CAT_TODAS)
        self._f_estado.set(EST_TODOS)
        self._f_venc.set(VENC_TODOS)
        self._f_orden.set(ORD_NOMBRE)
        self._pagina = 0
        self._render_tabla()

    def _filtrar(self) -> list:
        """Aplica TODOS los filtros activos (combinables) sobre el catálogo y
        devuelve la lista ya ordenada."""
        # Vista de un solo producto (tras escanear su código): se muestra ese
        # producto exacto, sin importar el largo del nombre ni los demás filtros.
        if self._solo_producto_id is not None:
            return [p for p in self._productos
                    if p.id == self._solo_producto_id]
        nombre_raw = self.ent_buscar.get().strip()
        nombre_q = sin_acentos(nombre_raw.lower())
        # Con MIN_BUSQUEDA+ letras se busca por subcadena; con 1-2 letras solo se
        # acepta la coincidencia EXACTA del nombre: así no se traen cientos de
        # filas por un prefijo corto, pero un producto de nombre muy corto
        # (ej. "Te") igual se encuentra tecleándolo.
        por_substring = len(nombre_raw) >= MIN_BUSQUEDA
        ubic = self.ent_ubic.get().strip().lower()
        cat = self._f_categoria.get()
        estado = self._f_estado.get()
        venc = self._f_venc.get()
        cat_id = self._cat_por_nombre.get(cat)
        res = []
        for p in self._productos:
            if nombre_q:
                nn = self._nombre_norm.get(p.id, "")
                if (nombre_q not in nn) if por_substring else (nn != nombre_q):
                    continue
            if ubic and ubic not in (p.ubicacion or "").lower():
                continue
            if cat == CAT_SIN:
                if p.categoria_id:
                    continue
            elif cat != CAT_TODAS and p.categoria_id != cat_id:
                continue
            if estado != EST_TODOS and not self._cumple_estado(p, estado):
                continue
            if venc != VENC_TODOS:
                dias = self._venc_map.get(p.id)
                if venc == VENC_POR and not (dias is not None and dias >= 0):
                    continue
                if venc == VENC_VENCIDOS and not (dias is not None and dias < 0):
                    continue
            res.append(p)
        return self._ordenar(res)

    @staticmethod
    def _cumple_estado(p, estado: str) -> bool:
        stock = p.stock_actual
        minimo = p.stock_minimo
        if estado == EST_SItem:
            return stock <= 0
        if estado == EST_CON:
            return stock > 0
        if estado == EST_BAJO:
            return p.controla_stock and stock <= minimo
        if estado == EST_CERCA:
            return (p.controla_stock and minimo > 0
                    and stock > minimo and stock <= minimo * CERCA_FACTOR)
        return True

    def _ordenar(self, prods: list) -> list:
        orden = self._f_orden.get()
        if orden == ORD_STOCK:
            return sorted(prods, key=lambda p: p.stock_actual)
        if orden == ORD_PRECIO:
            return sorted(prods, key=lambda p: p.precio_venta, reverse=True)
        return sorted(prods, key=lambda p: p.nombre.lower())

    # --- Render + paginación ------------------------------------------------

    def _render_debounced(self) -> None:
        """Programa el re-dibujo tras una pausa de tecleo, cancelando el anterior
        (debounce). Al tipear se vuelve a la 1ra página."""
        self._pagina = 0
        # Tipear en el buscador retoma la búsqueda normal (sale de la vista de un
        # solo producto que deja el escaneo).
        self._solo_producto_id = None
        # Corta cualquier pintado en tandas que siga en curso de un tecleo
        # anterior: mientras pinta, el hilo de UI está ocupado y los caracteres
        # nuevos tardan en aparecer. Cancelarlo deja el tecleo fluido; el
        # re-dibujo definitivo se dispara al terminar el debounce.
        self._cancelar_pintado()
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(DEBOUNCE_MS, self._render_tabla)

    def _hay_otros_filtros(self) -> bool:
        """True si hay algún filtro activo además del nombre (ubicación,
        categoría, estado o vencimiento)."""
        return bool(self.ent_ubic.get().strip()
                    or self._f_categoria.get() != CAT_TODAS
                    or self._f_estado.get() != EST_TODOS
                    or self._f_venc.get() != VENC_TODOS)

    def _cancelar_pintado(self) -> None:
        """Cancela el pintado en tandas que pudiera estar en curso."""
        if self._pintar_id is not None:
            self.after_cancel(self._pintar_id)
            self._pintar_id = None

    def esta_pintando(self) -> bool:
        """True mientras quedan filas por pintar en tandas. La ventana lo consulta
        para mantener el overlay 'Cargando…' hasta que la tabla esté completa (así
        no se ven las filas apareciendo de a tandas al entrar a Stock)."""
        return self._pintar_id is not None

    def _render_tabla(self) -> None:
        self._debounce_id = None
        self._cancelar_pintado()
        for w in self.tabla.winfo_children():
            w.destroy()
        self._visibles = self._filtrar()
        # Con 1-2 letras, sin otros filtros y sin coincidencia EXACTA de nombre,
        # mostramos una pista en vez de dibujar cientos de filas (lo más caro).
        # Si el nombre corto coincide exacto con un producto (ej. "Te"), _filtrar
        # ya lo trajo y se dibuja normal. El escaneo (self._solo_producto_id)
        # tampoco cae acá: muestra el producto exacto.
        nombre = self.ent_buscar.get().strip()
        if (self._solo_producto_id is None and 0 < len(nombre) < MIN_BUSQUEDA
                and not self._hay_otros_filtros() and not self._visibles):
            self.lbl_pagina.configure(text="")
            self.btn_prev.configure(state="disabled")
            self.btn_next.configure(state="disabled")
            ctk.CTkLabel(
                self.tabla,
                text=f"Escribí al menos {MIN_BUSQUEDA} letras para buscar por "
                     "nombre…", font=theme.fuente(14),
                text_color=theme.TXT_MUTED, justify="center").pack(pady=36)
            return
        total = len(self._visibles)
        paginas = max(1, ceil(total / PAGE_SIZE))
        self._pagina = max(0, min(self._pagina, paginas - 1))
        self._actualizar_paginador(total, paginas)
        if total == 0:
            hay_filtro = bool(
                self.ent_buscar.get().strip() or self.ent_ubic.get().strip()
                or self._f_categoria.get() != CAT_TODAS
                or self._f_estado.get() != EST_TODOS
                or self._f_venc.get() != VENC_TODOS)
            txt = ("Ningún producto coincide con los filtros."
                   if hay_filtro
                   else "No hay productos.\nCargá el primero o recibí un remito.")
            ctk.CTkLabel(self.tabla, text=txt, font=theme.fuente(14),
                         text_color=theme.TXT_MUTED, justify="center").pack(pady=36)
            return
        # Solo se dibuja la página actual (PAGE_SIZE filas como mucho) y EN TANDAS
        # (after) para no bloquear el event loop: la app sigue respondiendo.
        ini = self._pagina * PAGE_SIZE
        self._pintar_tanda(self._visibles[ini:ini + PAGE_SIZE], 0)

    def _pintar_tanda(self, items: list, desde: int) -> None:
        fin = min(desde + FILAS_POR_TANDA, len(items))
        for i in range(desde, fin):
            self._fila(items[i], i)
        if fin < len(items):
            self._pintar_id = self.after(
                1, lambda: self._pintar_tanda(items, fin))
        else:
            self._pintar_id = None

    def _actualizar_paginador(self, total: int, paginas: int) -> None:
        if total == 0:
            self.lbl_pagina.configure(text="Sin productos")
        else:
            desde = self._pagina * PAGE_SIZE + 1
            hasta = min((self._pagina + 1) * PAGE_SIZE, total)
            self.lbl_pagina.configure(
                text=f"{desde}–{hasta} de {total}   ·   "
                     f"Página {self._pagina + 1} de {paginas}")
        self.btn_prev.configure(
            state="normal" if self._pagina > 0 else "disabled")
        self.btn_next.configure(
            state="normal" if self._pagina < paginas - 1 else "disabled")

    def _pagina_prev(self) -> None:
        if self._pagina > 0:
            self._pagina -= 1
            self._render_tabla()

    def _pagina_next(self) -> None:
        if (self._pagina + 1) * PAGE_SIZE < len(self._visibles):
            self._pagina += 1
            self._render_tabla()

    def _fila(self, p, i: int) -> None:
        """Dibuja una fila de producto. Se arma con los mínimos widgets posibles
        (crear widgets de CTk es lo caro): el sub-frame del nombre solo se usa si
        hay ubicación o aviso de vencimiento, y el hueco del botón Vencim. se
        reserva con grid en vez de un frame placeholder."""
        f = ctk.CTkFrame(self.tabla,
                         fg_color=theme.ROW_ALT if i % 2 else "transparent",
                         corner_radius=8)
        f.pack(fill="x", padx=6, pady=1)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(5, minsize=ANCHO_VENCIM)  # reserva hueco Vencim.
        stock_txt = (f"{formato.numero(p.stock_actual)} kg"
                     if p.es_pesable else formato.numero(p.stock_actual))
        # Stock en rojo si está bajo, ámbar si está cerca del mínimo (se ve el
        # estado sin necesidad de filtrar).
        stock_color = theme.TXT
        if p.controla_stock:
            if p.stock_actual <= p.stock_minimo:
                stock_color = theme.ROJO
            elif (p.stock_minimo > 0
                  and p.stock_actual <= p.stock_minimo * CERCA_FACTOR):
                stock_color = theme.BADGE_KG_TXT
        dias = self._venc_map.get(p.id)
        # Columna 0: nombre. Solo si hay ubicación o vencimiento se usa un
        # sub-frame para apilar los renglones extra; si no, un label directo.
        if p.ubicacion or dias is not None:
            celda = ctk.CTkFrame(f, fg_color="transparent")
            celda.grid(row=0, column=0, padx=4, sticky="w")
            ctk.CTkLabel(celda, text=p.nombre, width=246, anchor="w",
                         font=theme.fuente(15), text_color=theme.TXT).pack(anchor="w")
            if p.ubicacion:
                ctk.CTkLabel(celda, text=f"Ubic. {p.ubicacion}", anchor="w",
                             font=theme.fuente(11),
                             text_color=theme.TXT_MUTED).pack(anchor="w")
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
        else:
            ctk.CTkLabel(f, text=p.nombre, width=246, anchor="w",
                         font=theme.fuente(15), text_color=theme.TXT).grid(
                row=0, column=0, padx=4, sticky="w")
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
                     font=theme.fuente(14), text_color=stock_color).grid(
            row=0, column=4, padx=4)
        if p.controla_vencimiento:
            ctk.CTkButton(f, text="📅  Vencim.", width=104, height=32,
                          corner_radius=8, font=theme.fuente(13),
                          fg_color="transparent", text_color=theme.ACCENT,
                          hover_color=theme.GHOST,
                          command=lambda pid=p.id, n=p.nombre, ps=p.es_pesable:
                              self._gestionar_vencimientos(pid, n, ps)).grid(
                row=0, column=5, padx=4)
        ctk.CTkButton(f, text="✏  Editar", width=ANCHO_EDITAR, height=32,
                      corner_radius=8, font=theme.fuente(13),
                      fg_color="transparent", text_color=theme.ACCENT,
                      hover_color=theme.GHOST,
                      command=lambda pid=p.id: self._editar_producto(pid)).grid(
            row=0, column=6, padx=4)

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
