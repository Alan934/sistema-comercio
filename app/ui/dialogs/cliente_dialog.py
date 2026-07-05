"""Modal de alta de cliente (cuenta corriente / fiado).

Devuelve {nombre, telefono, limite_credito} o None si se cancela.
"""
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.ui.dialogs.base import ModalBase


class ClienteDialog(ModalBase):
    def __init__(self, master, cliente=None):
        super().__init__(master,
                         "Editar cliente" if cliente else "Nuevo cliente")
        self._entries = {}
        if cliente is not None:
            campos = [
                ("Nombre", "nombre", cliente.nombre or ""),
                ("Teléfono", "telefono", cliente.telefono or ""),
                ("Límite de crédito", "limite_credito",
                 str(cliente.limite_credito)),
            ]
        else:
            campos = [
                ("Nombre", "nombre", ""),
                ("Teléfono", "telefono", ""),
                ("Límite de crédito", "limite_credito", "0"),
            ]
        for fila, (etiqueta, clave, valor) in enumerate(campos):
            ctk.CTkLabel(self, text=etiqueta, anchor="w").grid(
                row=fila, column=0, sticky="w", padx=(20, 8), pady=6)
            ent = ctk.CTkEntry(self, width=240)
            if valor:
                ent.insert(0, valor)
            ent.grid(row=fila, column=1, padx=(8, 20), pady=6)
            self._entries[clave] = ent

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.grid(row=3, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=4, column=0, columnspan=2, pady=(8, 20))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar", width=140,
                      command=self._confirmar).pack(side="left", padx=8)
        self._pie_atajos(grid_row=99)
        self.after(50, self._entries["nombre"].focus_set)

    def _confirmar(self) -> None:
        nombre = self._entries["nombre"].get().strip()
        if not nombre:
            self.lbl_error.configure(text="⚠ El nombre es obligatorio")
            return
        texto = self._entries["limite_credito"].get().strip().replace(",", ".")
        try:
            limite = Decimal(texto) if texto else Decimal("0")
        except InvalidOperation:
            self.lbl_error.configure(text="⚠ Límite de crédito inválido")
            return
        if limite < 0:
            self.lbl_error.configure(text="⚠ El límite no puede ser negativo")
            return
        self._aceptar({
            "nombre": nombre,
            "telefono": self._entries["telefono"].get().strip() or None,
            "limite_credito": limite,
        })
