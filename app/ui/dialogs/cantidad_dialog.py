"""Modal para fijar la cantidad de un ítem del carrito (o el peso si es pesable).

Devuelve un Decimal con la cantidad, o None si se cancela.
"""
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.ui import theme
from app.ui.dialogs.base import ModalBase


class CantidadDialog(ModalBase):
    def __init__(self, master, descripcion: str, cantidad_actual, es_pesable: bool):
        super().__init__(master, "Cantidad")
        self.es_pesable = es_pesable

        ctk.CTkLabel(self, text=descripcion, font=theme.fuente(16, "bold")).pack(
            padx=24, pady=(18, 2))
        ctk.CTkLabel(self, text="Peso (kg)" if es_pesable else "Cantidad",
                     text_color=theme.TXT_MUTED, font=theme.fuente(13)).pack()

        self.ent = ctk.CTkEntry(self, width=160, justify="center",
                                font=theme.fuente(22))
        self.ent.insert(0, str(cantidad_actual))
        self.ent.pack(padx=24, pady=10)
        self.ent.bind("<Return>", lambda _e: self._confirmar())

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.pack()

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(padx=24, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=110, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Aceptar", width=130, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(bind_enter=False)
        self.after(60, self.ent.focus_set)

    def _confirmar(self) -> None:
        texto = self.ent.get().strip().replace(",", ".")
        try:
            valor = Decimal(texto)
        except InvalidOperation:
            self.lbl_error.configure(text="⚠ Valor inválido")
            return
        if valor <= 0:
            self.lbl_error.configure(text="⚠ Debe ser mayor a cero")
            return
        if not self.es_pesable and valor != valor.to_integral_value():
            self.lbl_error.configure(text="⚠ La cantidad debe ser entera")
            return
        self._aceptar(valor)
