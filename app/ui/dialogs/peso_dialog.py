"""Modal para ingresar el peso (kg) de un producto pesable."""
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.core import formato

from app.models.producto import Producto
from app.ui.dialogs.base import ModalBase


def _parse_kg(texto: str) -> Decimal | None:
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    return valor if valor > 0 else None


class PesoDialog(ModalBase):
    def __init__(self, master, producto: Producto):
        super().__init__(master, "Ingresar peso")
        self.producto = producto

        ctk.CTkLabel(self, text=producto.nombre,
                     font=("", 18, "bold")).pack(padx=20, pady=(20, 2))
        ctk.CTkLabel(self, text=f"Precio: {formato.moneda(producto.precio_venta)} / kg").pack(padx=20)

        self.entry = ctk.CTkEntry(self, width=200, justify="center",
                                  placeholder_text="Ej: 0.750", font=("", 20))
        self.entry.pack(padx=20, pady=12)
        self.entry.bind("<KeyRelease>", self._recalcular)
        self.entry.bind("<Return>", lambda _e: self._confirmar())

        self.lbl_subtotal = ctk.CTkLabel(self, text="Subtotal: $0.00",
                                         font=("", 16, "bold"))
        self.lbl_subtotal.pack(padx=20, pady=(0, 8))

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(padx=20, pady=(0, 20))
        ctk.CTkButton(cont, text="Cancelar", width=100, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=6)
        ctk.CTkButton(cont, text="Agregar", width=100,
                      command=self._confirmar).pack(side="left", padx=6)

        self._pie_atajos(bind_enter=False)
        self.after(50, self.entry.focus_set)

    def _recalcular(self, _event=None) -> None:
        kg = _parse_kg(self.entry.get())
        if kg is None:
            self.lbl_subtotal.configure(text="Subtotal: $0.00")
        else:
            self.lbl_subtotal.configure(
                text=f"Subtotal: {formato.moneda(kg * self.producto.precio_venta)}")

    def _confirmar(self) -> None:
        kg = _parse_kg(self.entry.get())
        if kg is None:
            self.lbl_subtotal.configure(text="⚠ Ingresá un peso válido (> 0)")
            return
        self._aceptar(kg)
