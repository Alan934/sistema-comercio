"""Modal de alta de gasto (fijo o variable, opcionalmente ligado a proveedor).

Devuelve {tipo, descripcion, monto, proveedor_id, metodo} o None si se cancela.
"""
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.models.gasto import FIJO, VARIABLE
from app.services import proveedor_service
from app.ui.autocomplete import AutocompleteSimple
from app.ui.dialogs.base import ModalBase

SIN_PROVEEDOR = "(ninguno)"


class GastoDialog(ModalBase):
    def __init__(self, master):
        super().__init__(master, "Registrar gasto")
        self._proveedores = proveedor_service.listar_activos()
        self._mapa_prov = {p.nombre: p.id for p in self._proveedores}

        ctk.CTkLabel(self, text="Tipo", anchor="w").grid(
            row=0, column=0, sticky="w", padx=(20, 8), pady=6)
        self.seg_tipo = ctk.CTkSegmentedButton(self, values=["Fijo", "Variable"])
        self.seg_tipo.set("Fijo")
        self.seg_tipo.grid(row=0, column=1, padx=(8, 20), pady=6, sticky="w")

        ctk.CTkLabel(self, text="Descripción", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_desc = ctk.CTkEntry(self, width=260)
        self.ent_desc.grid(row=1, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="Monto", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_monto = ctk.CTkEntry(self, width=260, justify="right")
        self.ent_monto.grid(row=2, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="Medio de pago", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(20, 8), pady=6)
        self.seg_metodo = ctk.CTkSegmentedButton(
            self, values=["Efectivo", "Transferencia", "Tarjeta"])
        self.seg_metodo.set("Efectivo")
        self.seg_metodo.grid(row=3, column=1, padx=(8, 20), pady=6, sticky="w")

        ctk.CTkLabel(self, text="Proveedor (opcional)", anchor="w").grid(
            row=4, column=0, sticky="w", padx=(20, 8), pady=6)
        nombres = [SIN_PROVEEDOR] + list(self._mapa_prov.keys())
        self.ent_prov = ctk.CTkEntry(self, width=260)
        self.ent_prov.insert(0, SIN_PROVEEDOR)
        self.ent_prov.grid(row=4, column=1, padx=(8, 20), pady=6)
        self._auto_prov = AutocompleteSimple(self.ent_prov, self, nombres)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
        self.lbl_error.grid(row=5, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=6, column=0, columnspan=2, pady=(8, 20))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar", width=140,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.after(50, self.ent_desc.focus_set)

    def _confirmar(self) -> None:
        desc = self.ent_desc.get().strip()
        if not desc:
            self.lbl_error.configure(text="⚠ La descripción es obligatoria")
            return
        try:
            monto = Decimal(self.ent_monto.get().strip().replace(",", "."))
        except InvalidOperation:
            self.lbl_error.configure(text="⚠ Monto inválido")
            return
        if monto <= 0:
            self.lbl_error.configure(text="⚠ El monto debe ser mayor a cero")
            return

        metodos = {"Efectivo": "EFECTIVO", "Transferencia": "TRANSFERENCIA",
                   "Tarjeta": "TARJETA"}
        self._aceptar({
            "tipo": FIJO if self.seg_tipo.get() == "Fijo" else VARIABLE,
            "descripcion": desc,
            "monto": monto,
            "proveedor_id": self._mapa_prov.get(self.ent_prov.get().strip()),
            "metodo": metodos[self.seg_metodo.get()],
        })
