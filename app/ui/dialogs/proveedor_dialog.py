"""Modales simples para proveedores: alta y registro de pago."""
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.ui.dialogs.base import ModalBase


class ProveedorDialog(ModalBase):
    """Alta o edición de proveedor. Devuelve dict {nombre, cuit, telefono,
    email} o None. Si se pasa `proveedor`, precarga los campos para editar."""

    def __init__(self, master, proveedor=None):
        super().__init__(master,
                         "Editar proveedor" if proveedor else "Nuevo proveedor")
        self._entries = {}
        valores = {
            "nombre": getattr(proveedor, "nombre", "") or "",
            "cuit": getattr(proveedor, "cuit", "") or "",
            "telefono": getattr(proveedor, "telefono", "") or "",
            "email": getattr(proveedor, "email", "") or "",
        }
        for fila, (etiqueta, clave) in enumerate(
                [("Nombre", "nombre"), ("CUIT", "cuit"),
                 ("Teléfono", "telefono"), ("Correo", "email")]):
            ctk.CTkLabel(self, text=etiqueta, anchor="w").grid(
                row=fila, column=0, sticky="w", padx=(20, 8), pady=6)
            ent = ctk.CTkEntry(self, width=240)
            if valores[clave]:
                ent.insert(0, valores[clave])
            ent.grid(row=fila, column=1, padx=(8, 20), pady=6)
            self._entries[clave] = ent

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
        self.lbl_error.grid(row=4, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=5, column=0, columnspan=2, pady=(8, 20))
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
        self._aceptar({
            "nombre": nombre,
            "cuit": self._entries["cuit"].get().strip() or None,
            "telefono": self._entries["telefono"].get().strip() or None,
            "email": self._entries["email"].get().strip() or None,
        })


class MontoDialog(ModalBase):
    """Pide un monto positivo. Devuelve Decimal o None."""

    def __init__(self, master, titulo: str, prompt: str):
        super().__init__(master, titulo)
        ctk.CTkLabel(self, text=prompt, font=("", 15)).pack(padx=24, pady=(20, 8))
        self.ent = ctk.CTkEntry(self, width=200, justify="right", font=("", 18))
        self.ent.pack(padx=24, pady=8)
        self.ent.bind("<Return>", lambda _e: self._confirmar())
        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
        self.lbl_error.pack(padx=24)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(padx=24, pady=(8, 20))
        ctk.CTkButton(cont, text="Cancelar", width=110, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Aceptar", width=130,
                      command=self._confirmar).pack(side="left", padx=8)
        self._pie_atajos(bind_enter=False)
        self.after(50, self.ent.focus_set)

    def _confirmar(self) -> None:
        texto = self.ent.get().strip().replace(",", ".")
        try:
            monto = Decimal(texto)
        except InvalidOperation:
            self.lbl_error.configure(text="⚠ Monto inválido")
            return
        if monto <= 0:
            self.lbl_error.configure(text="⚠ Debe ser mayor a cero")
            return
        self._aceptar(monto)


class PagoDialog(ModalBase):
    """Pide monto y medio de pago. Devuelve {monto: Decimal, metodo: str} o None.

    El medio de pago hace que el arqueo del cierre cuente solo lo que entró o
    salió en efectivo (un pago por transferencia no toca la caja)."""

    METODOS = ["Efectivo", "Transferencia", "Tarjeta"]
    _CLAVE = {"Efectivo": "EFECTIVO", "Transferencia": "TRANSFERENCIA",
              "Tarjeta": "TARJETA"}

    def __init__(self, master, titulo: str, prompt: str):
        super().__init__(master, titulo)
        ctk.CTkLabel(self, text=prompt, font=("", 15)).pack(padx=24, pady=(20, 8))
        self.ent = ctk.CTkEntry(self, width=220, justify="right", font=("", 18))
        self.ent.pack(padx=24, pady=8)
        self.ent.bind("<Return>", lambda _e: self._confirmar())

        ctk.CTkLabel(self, text="Medio de pago", anchor="w").pack(
            padx=24, pady=(6, 2), anchor="w")
        self.seg_metodo = ctk.CTkSegmentedButton(self, values=self.METODOS)
        self.seg_metodo.set("Efectivo")
        self.seg_metodo.pack(padx=24, pady=(0, 4), fill="x")

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
        self.lbl_error.pack(padx=24)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(padx=24, pady=(8, 20))
        ctk.CTkButton(cont, text="Cancelar", width=110, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Aceptar", width=130,
                      command=self._confirmar).pack(side="left", padx=8)
        self._pie_atajos(bind_enter=False)
        self.after(50, self.ent.focus_set)

    def _confirmar(self) -> None:
        texto = self.ent.get().strip().replace(",", ".")
        try:
            monto = Decimal(texto)
        except InvalidOperation:
            self.lbl_error.configure(text="⚠ Monto inválido")
            return
        if monto <= 0:
            self.lbl_error.configure(text="⚠ Debe ser mayor a cero")
            return
        self._aceptar({"monto": monto,
                       "metodo": self._CLAVE[self.seg_metodo.get()]})
