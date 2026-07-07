"""Modal para agregar o editar un corte de una pieza.

El precio se define de una de dos formas (toggle): se ingresa el PRECIO POR KG
—y se muestra el total— o se ingresa el MARGEN % —y se muestra el precio por kg
que sale de aplicarlo al costo de la res—. El nombre tiene autocompletado de
productos: si se elige uno existente, el corte carga stock a ese producto; si se
escribe uno nuevo, al confirmar la pieza se crea el producto pesable.

Devuelve un dict o None:
    {"descripcion", "peso", "precio_venta_kg", "margen_pct",
     "es_desperdicio", "producto_id"}
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import customtkinter as ctk

from app.core import pricing
from app.services import despiece_service
from app.ui import theme
from app.ui.autocomplete import AutocompleteBuscador
from app.ui.dialogs.base import ModalBase

CENTAVOS = Decimal("0.01")
POR_PRECIO = "Precio por kg"
POR_MARGEN = "Margen %"


def _num(texto):
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        v = Decimal(texto)
    except InvalidOperation:
        return None
    return v if v >= 0 else None


class CorteDialog(ModalBase):
    def __init__(self, master, costo_kg=Decimal("0"), corte=None):
        super().__init__(master, "Corte")
        self._producto = None
        self._costo_kg = Decimal(str(costo_kg))
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text=("Editar corte" if corte else "Agregar corte"),
                     font=theme.fuente(18, "bold"), text_color=theme.TXT).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(18, 10))

        ctk.CTkLabel(self, text="Corte", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_nombre = ctk.CTkEntry(self, width=280,
                                       placeholder_text="Nombre del corte…")
        self.ent_nombre.grid(row=1, column=1, padx=(8, 20), pady=6, sticky="ew")
        self._auto = AutocompleteBuscador(
            self.ent_nombre, self, on_seleccionar=self._elegir_producto,
            buscar_fn=despiece_service.buscar_productos_carne)
        # Al escribir el nombre también se borra el error previo.
        self.ent_nombre.bind("<KeyRelease>", lambda _e: self._limpiar_error(),
                             add="+")

        ctk.CTkLabel(self, text="Kg", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_peso = ctk.CTkEntry(self, width=280)
        self.ent_peso.grid(row=2, column=1, padx=(8, 20), pady=6, sticky="ew")
        self.ent_peso.bind("<KeyRelease>", self._recalcular)

        # Cómo se define el precio: por precio/kg o por margen %.
        ctk.CTkLabel(self, text="Definir por", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(20, 8), pady=6)
        self.seg_modo = ctk.CTkSegmentedButton(
            self, values=[POR_PRECIO, POR_MARGEN],
            selected_color=theme.PRIMARY, selected_hover_color=theme.PRIMARY_HOVER,
            command=lambda _v: self._cambiar_modo())
        self.seg_modo.set(POR_PRECIO)
        self.seg_modo.grid(row=3, column=1, padx=(8, 20), pady=6, sticky="w")

        self.lbl_valor = ctk.CTkLabel(self, text=POR_PRECIO, anchor="w")
        self.lbl_valor.grid(row=4, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_valor = ctk.CTkEntry(self, width=280)
        self.ent_valor.grid(row=4, column=1, padx=(8, 20), pady=6, sticky="ew")
        self.ent_valor.bind("<KeyRelease>", self._recalcular)

        self.var_desp = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="Es desperdicio / merma (sin venta)",
                        variable=self.var_desp, onvalue=True, offvalue=False,
                        command=self._toggle_desp).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=20, pady=(4, 2))

        self.lbl_calc = ctk.CTkLabel(self, text="", font=theme.fuente(14, "bold"),
                                     text_color=theme.ACCENT)
        self.lbl_calc.grid(row=6, column=0, columnspan=2, padx=20, pady=(4, 0))
        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.grid(row=7, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=8, column=0, columnspan=2, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar", width=140, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        if corte is not None:
            self.ent_nombre.insert(0, corte.descripcion)
            self.ent_peso.insert(0, str(corte.peso))
            if corte.es_desperdicio:
                self.var_desp.set(True)
                self._toggle_desp()
            elif corte.margen_pct is not None:
                self.seg_modo.set(POR_MARGEN)
                self._cambiar_modo()
                self.ent_valor.insert(0, str(corte.margen_pct))
            else:
                self.ent_valor.insert(0, str(corte.precio_venta_kg))
        self.after(60, self.ent_nombre.focus_set)
        self._recalcular()

    # --- Modo precio / margen ----------------------------------------------

    def _por_margen(self) -> bool:
        return self.seg_modo.get() == POR_MARGEN

    def _cambiar_modo(self):
        self.lbl_valor.configure(text="Margen %" if self._por_margen()
                                 else "Precio por kg")
        self.ent_valor.delete(0, "end")   # cambia la unidad: se limpia el campo
        self._recalcular()

    def _precio_kg(self):
        """Precio/kg resultante según el modo (o None si falta dato)."""
        valor = _num(self.ent_valor.get())
        if valor is None:
            return None
        if self._por_margen():
            return pricing.precio_desde_margen(self._costo_kg, valor)
        return valor

    def _elegir_producto(self, prod):
        self._producto = prod
        self.ent_nombre.delete(0, "end")
        self.ent_nombre.insert(0, prod.nombre)
        # Al reusar un producto existente, se trabaja por precio directo.
        if not self.var_desp.get():
            self.seg_modo.set(POR_PRECIO)
            self.lbl_valor.configure(text="Precio por kg")
            self.ent_valor.delete(0, "end")
            self.ent_valor.insert(0, str(prod.precio_venta))
        self._recalcular()

    def _toggle_desp(self):
        estado = "disabled" if self.var_desp.get() else "normal"
        if self.var_desp.get():
            self.ent_valor.delete(0, "end")
        self.ent_valor.configure(state=estado)
        self.seg_modo.configure(state=estado)
        self._recalcular()

    def _limpiar_error(self):
        if self.lbl_error.cget("text"):
            self.lbl_error.configure(text="")

    def _recalcular(self, _e=None):
        self._limpiar_error()   # corregir un campo borra el error anterior
        if self.var_desp.get():
            self.lbl_calc.configure(text="Sin venta (desperdicio)")
            return
        peso = _num(self.ent_peso.get())
        precio = self._precio_kg()
        if peso is None or peso <= 0 or precio is None:
            self.lbl_calc.configure(text="")
            return
        total = (peso * precio).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        if self._por_margen():
            self.lbl_calc.configure(
                text=f"→ Precio por kg: ${precio:,.2f}   ·   Total: ${total:,.2f}")
        else:
            self.lbl_calc.configure(text=f"→ Total del corte: ${total:,.2f}")

    def _confirmar(self):
        nombre = self.ent_nombre.get().strip()
        if not nombre:
            self.lbl_error.configure(text="⚠ Poné el nombre del corte")
            return
        peso = _num(self.ent_peso.get())
        if peso is None or peso <= 0:
            self.lbl_error.configure(text="⚠ Kg inválido (tiene que ser > 0)")
            return
        desp = self.var_desp.get()
        valor = self.ent_valor.get().strip()
        # Solo usar el producto elegido si el texto sigue siendo su nombre.
        prod_id = (self._producto.id
                   if self._producto and self._producto.nombre == nombre else None)
        precio = None if (desp or self._por_margen()) else (valor or None)
        margen = valor or None if (not desp and self._por_margen()) else None
        self._aceptar({
            "descripcion": nombre,
            "peso": self.ent_peso.get().strip(),
            "precio_venta_kg": precio,
            "margen_pct": margen,
            "es_desperdicio": desp,
            "producto_id": prod_id,
        })
