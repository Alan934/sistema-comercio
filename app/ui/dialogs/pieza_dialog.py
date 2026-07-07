"""Modal para agregar una pieza (Espalda, Pierna, ...) a una res.

Devuelve {"nombre", "margen_pct"} o None si se cancela.
"""
import customtkinter as ctk

from app.ui import theme
from app.ui.dialogs.base import ModalBase

SUGERENCIAS = ["Espalda", "Pierna", "Delantero", "Costillar", "Vacío", "Rueda"]


class PiezaDialog(ModalBase):
    def __init__(self, master):
        super().__init__(master, "Nueva pieza")
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Nueva pieza", font=theme.fuente(18, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, columnspan=2,
                                                padx=20, pady=(18, 12))

        # Desplegable con las piezas típicas, pero editable: se puede escribir
        # un nombre propio si la pieza no está en la lista.
        ctk.CTkLabel(self, text="Nombre", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.cmb_nombre = ctk.CTkComboBox(
            self, width=240, values=SUGERENCIAS,
            button_color=theme.PRIMARY, button_hover_color=theme.PRIMARY_HOVER)
        self.cmb_nombre.set("")   # arranca vacío para que elija a propósito
        self.cmb_nombre.grid(row=1, column=1, padx=(8, 20), pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Margen % (opcional)", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_margen = ctk.CTkEntry(
            self, width=240, placeholder_text="Si se deja vacío, hereda de la res")
        self.ent_margen.grid(row=2, column=1, padx=(8, 20), pady=6, sticky="ew")

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.grid(row=3, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=4, column=0, columnspan=2, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Agregar", width=140, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.after(60, self.cmb_nombre.focus_set)

    def _confirmar(self):
        nombre = self.cmb_nombre.get().strip()
        if not nombre:
            self.lbl_error.configure(text="⚠ Elegí o escribí un nombre (ej. Espalda)")
            return
        self._aceptar({"nombre": nombre,
                       "margen_pct": self.ent_margen.get().strip() or None})
