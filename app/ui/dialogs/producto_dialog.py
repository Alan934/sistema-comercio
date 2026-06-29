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
    def __init__(self, master, producto: dict | None = None):
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
                    str(p.get("codigo_barra") or ""))

        # Categoría
        ctk.CTkLabel(self, text="Categoría", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=5)
        self.opt_cat = ctk.CTkOptionMenu(self, width=260,
                                         values=list(self._cat_id.keys()),
                                         command=lambda _v: self._recalcular())
        actual = SIN_CATEGORIA
        for nombre, cid in self._cat_id.items():
            if cid == p.get("categoria_id"):
                actual = nombre
        self.opt_cat.set(actual)
        self.opt_cat.grid(row=2, column=1, padx=(8, 20), pady=5, sticky="w")

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

        # Ubicación: combobox editable que sugiere las ubicaciones ya usadas.
        ctk.CTkLabel(self, text="Ubicación", anchor="w").grid(
            row=7, column=0, sticky="w", padx=(20, 8), pady=5)
        self.cmb_ubicacion = ctk.CTkComboBox(
            self, width=260, values=stock_service.listar_ubicaciones())
        self.cmb_ubicacion.set(p.get("ubicacion") or "")
        self.cmb_ubicacion.grid(row=7, column=1, padx=(8, 20), pady=5, sticky="w")

        fila = 8
        if not self.es_edicion:
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
                        variable=self.var_venc).grid(
            row=fila, column=0, columnspan=2, sticky="w", padx=20, pady=3)
        fila += 1
        ctk.CTkCheckBox(self, text="Controla stock",
                        variable=self.var_stock).grid(
            row=fila, column=0, columnspan=2, sticky="w", padx=20, pady=3)
        fila += 1

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
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

    # --- Precio calculado en vivo ------------------------------------------

    def _margen_aplicable(self) -> Decimal | None:
        mtxt = self._entries["margen_pct"].get().strip().replace(",", ".")
        if mtxt:
            try:
                return Decimal(mtxt)
            except InvalidOperation:
                return None
        return self._cat_margen.get(self._cat_id.get(self.opt_cat.get()))

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

        datos = {
            "nombre": nombre,
            "codigo_barra": self._entries["codigo_barra"].get().strip() or None,
            "categoria_id": self._cat_id.get(self.opt_cat.get()),
            "margen_pct": mtxt or None,
            "ubicacion": self.cmb_ubicacion.get().strip() or None,
            "es_pesable": bool(self.var_pesable.get()),
            "controla_vencimiento": bool(self.var_venc.get()),
            "controla_stock": bool(self.var_stock.get()),
            **numericos,
        }
        if not self.es_edicion:
            v = _num(self._entries["stock_actual"].get())
            if v is None:
                self.lbl_error.configure(text="⚠ Stock inicial inválido")
                return
            datos["stock_actual"] = str(v)

        self._aceptar(datos)
