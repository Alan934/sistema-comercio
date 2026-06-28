"""Consulta de precio: busca un producto y muestra su precio/stock SIN tocar
la venta en curso. Pensado para responderle al cliente en el mostrador.

Queda abierto para consultar varios productos seguidos.
"""
from decimal import Decimal

import customtkinter as ctk

from app.services import venta_service
from app.ui import theme
from app.ui.dialogs.base import ModalBase
from app.ui.dialogs.buscar_dialog import BuscarProductoDialog


def _money(v) -> str:
    return f"${Decimal(str(v)):,.2f}"


class ConsultaPrecioDialog(ModalBase):
    def __init__(self, master):
        super().__init__(master, "Consultar precio")

        ctk.CTkLabel(self, text="Escaneá o escribí un producto. No afecta la venta.",
                     font=theme.fuente(13), text_color=theme.TXT_MUTED).pack(
            padx=20, pady=(18, 8))

        self.entry = ctk.CTkEntry(self, width=380, height=46,
                                  font=theme.fuente(16), corner_radius=10,
                                  placeholder_text="Código o nombre…")
        self.entry.pack(padx=20, pady=(0, 12))
        self.entry.bind("<Return>", self._consultar)

        self.card = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=12,
                                 height=128)
        self.card.pack(padx=20, pady=(0, 12), fill="x")
        self.card.pack_propagate(False)
        self.lbl_nombre = ctk.CTkLabel(self.card, text="—", anchor="w",
                                       font=theme.fuente(17, "bold"),
                                       text_color=theme.TXT)
        self.lbl_nombre.pack(anchor="w", padx=16, pady=(18, 2))
        self.lbl_precio = ctk.CTkLabel(self.card, text="", anchor="w",
                                       font=theme.fuente(30, "bold"),
                                       text_color=theme.ACCENT)
        self.lbl_precio.pack(anchor="w", padx=16)
        self.lbl_info = ctk.CTkLabel(
            self.card, text="Escaneá un producto para ver su precio.",
            anchor="w", font=theme.fuente(12), text_color=theme.TXT_MUTED)
        self.lbl_info.pack(anchor="w", padx=16, pady=(2, 14))

        ctk.CTkButton(self, text="Cerrar", width=120, height=38,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._cancelar).pack(pady=(0, 18))

        self.after(60, self.entry.focus_set)

    def _consultar(self, _event=None) -> None:
        texto = self.entry.get().strip()
        self.entry.delete(0, "end")
        if not texto:
            return
        prod = venta_service.buscar_por_codigo(texto)
        if prod is None:
            resultados = venta_service.buscar_por_nombre(texto)
            if not resultados:
                self.lbl_nombre.configure(text="No encontrado")
                self.lbl_precio.configure(text="")
                self.lbl_info.configure(text=f"Sin coincidencias para “{texto}”.")
                self.entry.focus_set()
                return
            prod = BuscarProductoDialog(self, resultados).mostrar()
            if prod is None:
                self.entry.focus_set()
                return
        self._mostrar(prod)
        self.entry.focus_set()

    def _mostrar(self, p) -> None:
        self.lbl_nombre.configure(text=p.nombre)
        if p.es_pesable:
            self.lbl_precio.configure(text=f"{_money(p.precio_venta)} / kg")
            stock = f"{p.stock_actual} kg"
        else:
            self.lbl_precio.configure(text=_money(p.precio_venta))
            stock = f"{p.stock_actual}"
        self.lbl_info.configure(
            text=f"Código: {p.codigo_barra or 'sin código'}  ·  Stock: {stock}")
