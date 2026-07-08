"""Modal para elegir un producto cuando la búsqueda por nombre da varios."""
import customtkinter as ctk

from app.core import formato

from app.models.producto import Producto
from app.ui.dialogs.base import ModalBase


class BuscarProductoDialog(ModalBase):
    def __init__(self, master, resultados: list[Producto]):
        super().__init__(master, "Elegir producto")
        ctk.CTkLabel(self, text="Resultados de la búsqueda",
                     font=("", 16, "bold")).pack(padx=20, pady=(16, 8))

        lista = ctk.CTkScrollableFrame(self, width=420, height=320)
        lista.pack(padx=16, pady=(0, 16), fill="both", expand=True)

        for prod in resultados:
            unidad = "/kg" if prod.es_pesable else ""
            texto = f"{prod.nombre}   —   {formato.moneda(prod.precio_venta)}{unidad}"
            ctk.CTkButton(
                lista, text=texto, anchor="w", height=40,
                command=lambda p=prod: self._aceptar(p),
            ).pack(fill="x", padx=4, pady=3)
