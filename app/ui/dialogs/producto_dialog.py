"""Modal de alta/edición de producto, con categoría y margen de ganancia.

Si el producto tiene margen (propio o por su categoría), el precio se calcula
solo a partir del costo. Si no, el precio es manual.

Devuelve un dict con los datos (sin id) o None si se cancela.
"""
import tkinter as tk
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.core import pricing
from app.services import categoria_service, stock_service
from app.ui import theme
from app.ui.autocomplete import AutocompleteSimple
from app.ui.dialogs.base import ModalBase

SIN_CATEGORIA = "(sin categoría)"


def _num(texto: str) -> Decimal | None:
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return Decimal("0")
    try:
        v = Decimal(texto)
    except InvalidOperation:
        return None
    return v if v >= 0 else None


class ProductoDialog(ModalBase):
    def __init__(self, master, producto: dict | None = None,
                 codigo_inicial: str | None = None):
        self.es_edicion = producto is not None
        super().__init__(master, "Editar producto" if self.es_edicion
                         else "Nuevo producto")
        p = producto or {}

        self._categorias = categoria_service.listar_activas()
        self._cat_id = {SIN_CATEGORIA: None}
        self._cat_margen = {}
        for c in self._categorias:
            self._cat_id[c.nombre] = c.id
            self._cat_margen[c.id] = c.margen_pct

        self._entries: dict[str, ctk.CTkEntry] = {}

        def _fila_entry(fila, etiqueta, clave, valor):
            ctk.CTkLabel(self, text=etiqueta, anchor="w").grid(
                row=fila, column=0, sticky="w", padx=(20, 8), pady=5)
            ent = ctk.CTkEntry(self, width=260)
            if valor:
                ent.insert(0, valor)
            ent.grid(row=fila, column=1, padx=(8, 20), pady=5)
            self._entries[clave] = ent
            return ent

        _fila_entry(0, "Nombre", "nombre", str(p.get("nombre", "")))
        _fila_entry(1, "Código de barra", "codigo_barra",
                    str(p.get("codigo_barra") or codigo_inicial or ""))

        # Categoría: campo con autocompletado (filtra mientras se escribe).
        ctk.CTkLabel(self, text="Categoría", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=5)
        actual = SIN_CATEGORIA
        for nombre, cid in self._cat_id.items():
            if cid == p.get("categoria_id"):
                actual = nombre
        self.ent_cat = ctk.CTkEntry(self, width=260)
        self.ent_cat.insert(0, actual)
        self.ent_cat.grid(row=2, column=1, padx=(8, 20), pady=5, sticky="w")
        self._auto_cat = AutocompleteSimple(
            self.ent_cat, self, list(self._cat_id.keys()),
            on_seleccionar=lambda _v: self._recalcular())
        self.ent_cat.bind("<KeyRelease>", self._recalcular, add="+")

        c = _fila_entry(3, "Costo de compra", "costo_compra",
                        str(p.get("costo_compra", "0")))
        c.bind("<KeyRelease>", self._recalcular)
        m = _fila_entry(4, "Margen % (opcional)", "margen_pct",
                        "" if p.get("margen_pct") is None else str(p.get("margen_pct")))
        m.bind("<KeyRelease>", self._recalcular)
        _fila_entry(5, "Precio de venta", "precio_venta",
                    str(p.get("precio_venta", "0")))
        _fila_entry(6, "Stock mínimo", "stock_minimo",
                    str(p.get("stock_minimo", "0")))

        # Ubicación: campo con autocompletado de las ubicaciones ya usadas
        # (filtra mientras se escribe, como el buscador de la caja).
        ctk.CTkLabel(self, text="Ubicación", anchor="w").grid(
            row=7, column=0, sticky="w", padx=(20, 8), pady=5)
        self.ent_ubicacion = ctk.CTkEntry(self, width=260)
        self.ent_ubicacion.insert(0, p.get("ubicacion") or "")
        self.ent_ubicacion.grid(row=7, column=1, padx=(8, 20), pady=5, sticky="w")
        self._auto_ubic = AutocompleteSimple(
            self.ent_ubicacion, self, stock_service.listar_ubicaciones())

        # Stock editable: en el alta es el stock inicial; en la edición permite
        # corregir el stock actual (queda como movimiento de AJUSTE). La vista
        # de Stock solo la ven admin/superadmin, así que la acción ya está
        # restringida por el acceso a la pantalla.
        if self.es_edicion:
            _fila_entry(8, "Stock actual", "stock_actual",
                        str(p.get("stock_actual", "0")))
        else:
            _fila_entry(8, "Stock inicial", "stock_actual", "0")
        fila = 9

        self.lbl_hint = ctk.CTkLabel(self, text="", text_color=theme.TXT_MUTED,
                                     font=theme.fuente(12), anchor="w")
        self.lbl_hint.grid(row=fila, column=0, columnspan=2, sticky="w", padx=20)
        fila += 1

        self.var_pesable = tk.IntVar(value=1 if p.get("es_pesable") else 0)
        self.var_venc = tk.IntVar(value=1 if p.get("controla_vencimiento") else 0)
        self.var_stock = tk.IntVar(value=1 if p.get("controla_stock", 1) else 0)
        ctk.CTkCheckBox(self, text="Se vende al peso (kg)",
                        variable=self.var_pesable).grid(
            row=fila, column=0, columnspan=2, sticky="w", padx=20, pady=3)
        fila += 1
        ctk.CTkCheckBox(self, text="Controla vencimiento (perecedero)",
                        variable=self.var_venc, command=self._toggle_venc).grid(
            row=fila, column=0, columnspan=2, sticky="w", padx=20, pady=3)
        fila += 1
        # Fila de fecha: solo visible si se controla vencimiento.
        self.fila_venc = ctk.CTkFrame(self, fg_color="transparent")
        self.fila_venc.grid(row=fila, column=0, columnspan=2, sticky="w",
                            padx=20, pady=(0, 3))
        self.ent_venc = None
        if self.es_edicion:
            # En edición las fechas se gestionan con el gestor de lotes; el
            # producto puede tener varias fechas conviviendo.
            ctk.CTkLabel(
                self.fila_venc,
                text="Las fechas se gestionan con el botón «📅 Vencim.» "
                     "de la lista de Stock.",
                anchor="w", font=theme.fuente(12),
                text_color=theme.TXT_MUTED).pack(side="left", padx=(20, 8))
        else:
            ctk.CTkLabel(self.fila_venc, text="Fecha de vencimiento",
                         anchor="w").pack(side="left", padx=(20, 8))
            self.ent_venc = ctk.CTkEntry(self.fila_venc, width=160,
                                         placeholder_text="dd/mm/aaaa")
            self.ent_venc.pack(side="left")
        fila += 1
        ctk.CTkCheckBox(self, text="Controla stock",
                        variable=self.var_stock).grid(
            row=fila, column=0, columnspan=2, sticky="w", padx=20, pady=3)
        fila += 1
        self._toggle_venc()

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.grid(row=fila, column=0, columnspan=2, padx=20)
        fila += 1

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=fila, column=0, columnspan=2, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar", width=140, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.after(50, self._entries["nombre"].focus_set)
        self._recalcular()

    def _toggle_venc(self) -> None:
        """Muestra el campo de fecha solo cuando se controla vencimiento."""
        if self.var_venc.get():
            self.fila_venc.grid()
        else:
            self.fila_venc.grid_remove()

    # --- Precio calculado en vivo ------------------------------------------

    def _margen_aplicable(self) -> Decimal | None:
        mtxt = self._entries["margen_pct"].get().strip().replace(",", ".")
        if mtxt:
            try:
                return Decimal(mtxt)
            except InvalidOperation:
                return None
        return self._cat_margen.get(self._cat_id.get(self.ent_cat.get().strip()))

    def _recalcular(self, _event=None) -> None:
        margen = self._margen_aplicable()
        if margen is None:
            self.lbl_hint.configure(text="Sin margen: el precio es manual.")
            return
        costo = _num(self._entries["costo_compra"].get())
        if costo is None:
            return
        precio = pricing.precio_desde_margen(costo, margen)
        self._entries["precio_venta"].delete(0, "end")
        self._entries["precio_venta"].insert(0, str(precio))
        self.lbl_hint.configure(text=f"Precio calculado con margen {margen}%.")

    # --- Confirmación -------------------------------------------------------

    def _confirmar(self) -> None:
        nombre = self._entries["nombre"].get().strip()
        if not nombre:
            self.lbl_error.configure(text="⚠ El nombre es obligatorio")
            return

        numericos = {}
        for clave in ("precio_venta", "costo_compra", "stock_minimo"):
            v = _num(self._entries[clave].get())
            if v is None:
                self.lbl_error.configure(text=f"⚠ Valor inválido en {clave}")
                return
            numericos[clave] = str(v)

        mtxt = self._entries["margen_pct"].get().strip().replace(",", ".")
        if mtxt:
            try:
                if Decimal(mtxt) < 0:
                    raise InvalidOperation
            except InvalidOperation:
                self.lbl_error.configure(text="⚠ Margen inválido")
                return

        # En el alta, si controla vencimiento la fecha del primer lote es
        # obligatoria. En edición no hay campo de fecha (se usa el gestor).
        fecha_venc = None
        if self.var_venc.get() and self.ent_venc is not None:
            fecha_venc = stock_service.parse_fecha(self.ent_venc.get())
            if fecha_venc is None:
                self.lbl_error.configure(
                    text="⚠ Indicá la fecha de vencimiento (dd/mm/aaaa)")
                return

        datos = {
            "nombre": nombre,
            "codigo_barra": self._entries["codigo_barra"].get().strip() or None,
            "categoria_id": self._cat_id.get(self.ent_cat.get().strip()),
            "margen_pct": mtxt or None,
            "ubicacion": self.ent_ubicacion.get().strip() or None,
            "es_pesable": bool(self.var_pesable.get()),
            "controla_vencimiento": bool(self.var_venc.get()),
            "fecha_vencimiento": fecha_venc,
            "controla_stock": bool(self.var_stock.get()),
            **numericos,
        }
        v = _num(self._entries["stock_actual"].get())
        if v is None:
            self.lbl_error.configure(
                text="⚠ Stock inválido" if self.es_edicion
                else "⚠ Stock inicial inválido")
            return
        datos["stock_actual"] = str(v)

        self._aceptar(datos)
