"""Modal de alta/edición de producto.

Devuelve un dict con los datos cargados (sin id) o None si se cancela.
La vista decide si llamar a crear_producto o actualizar_producto.
"""
import tkinter as tk
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.ui.dialogs.base import ModalBase


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

        self._entries: dict[str, ctk.CTkEntry] = {}
        campos = [
            ("Nombre", "nombre", str(p.get("nombre", ""))),
            ("Código de barra", "codigo_barra", str(p.get("codigo_barra") or "")),
            ("Precio de venta", "precio_venta", str(p.get("precio_venta", "0"))),
            ("Costo de compra", "costo_compra", str(p.get("costo_compra", "0"))),
            ("Stock mínimo", "stock_minimo", str(p.get("stock_minimo", "0"))),
        ]
        fila = 0
        for etiqueta, clave, valor in campos:
            ctk.CTkLabel(self, text=etiqueta, anchor="w").grid(
                row=fila, column=0, sticky="w", padx=(20, 8), pady=6)
            ent = ctk.CTkEntry(self, width=260)
            ent.insert(0, valor)
            ent.grid(row=fila, column=1, padx=(8, 20), pady=6)
            self._entries[clave] = ent
            fila += 1

        # Stock inicial solo en alta (después se mueve por compras/ventas).
        if not self.es_edicion:
            ctk.CTkLabel(self, text="Stock inicial", anchor="w").grid(
                row=fila, column=0, sticky="w", padx=(20, 8), pady=6)
            ent = ctk.CTkEntry(self, width=260)
            ent.insert(0, "0")
            ent.grid(row=fila, column=1, padx=(8, 20), pady=6)
            self._entries["stock_actual"] = ent
            fila += 1

        self.var_pesable = tk.IntVar(value=1 if p.get("es_pesable") else 0)
        self.var_venc = tk.IntVar(value=1 if p.get("controla_vencimiento") else 0)
        self.var_stock = tk.IntVar(value=1 if p.get("controla_stock", 1) else 0)
        ctk.CTkCheckBox(self, text="Se vende al peso (kg)",
                        variable=self.var_pesable).grid(
            row=fila, column=0, columnspan=2, sticky="w", padx=20, pady=4)
        fila += 1
        ctk.CTkCheckBox(self, text="Controla vencimiento (perecedero)",
                        variable=self.var_venc).grid(
            row=fila, column=0, columnspan=2, sticky="w", padx=20, pady=4)
        fila += 1
        ctk.CTkCheckBox(self, text="Controla stock",
                        variable=self.var_stock).grid(
            row=fila, column=0, columnspan=2, sticky="w", padx=20, pady=4)
        fila += 1

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
        self.lbl_error.grid(row=fila, column=0, columnspan=2, padx=20)
        fila += 1

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=fila, column=0, columnspan=2, pady=(8, 20))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar", width=140,
                      command=self._confirmar).pack(side="left", padx=8)

        self.after(50, self._entries["nombre"].focus_set)

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

        datos = {
            "nombre": nombre,
            "codigo_barra": self._entries["codigo_barra"].get().strip() or None,
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
