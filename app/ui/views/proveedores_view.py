"""Vista de Proveedores: listado con su deuda (cuenta corriente),
alta de proveedor y registro de pagos."""
from decimal import Decimal
from tkinter import messagebox

import customtkinter as ctk

from app.services import proveedor_service
from app.ui.dialogs.proveedor_dialog import ProveedorDialog, MontoDialog


def _money(v) -> str:
    return f"${Decimal(str(v)):,.2f}"


class ProveedoresView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Proveedores", font=("", 24, "bold")).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Nuevo proveedor", width=150,
                      command=self._nuevo).grid(row=0, column=2, padx=4)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=16)
        for col, (txt, w) in enumerate(
                [("Proveedor", 280), ("Teléfono", 160), ("Deuda", 140), ("", 140)]):
            ctk.CTkLabel(header, text=txt, width=w, anchor="w",
                         font=("", 13, "bold")).grid(row=0, column=col, padx=4)

        self.tabla = ctk.CTkScrollableFrame(self)
        self.tabla.grid(row=2, column=0, sticky="nsew", padx=16, pady=(6, 16))
        self.tabla.grid_columnconfigure(0, weight=1)

    def al_mostrar(self) -> None:
        self._recargar()

    def _recargar(self) -> None:
        proveedores = proveedor_service.listar_activos()
        for w in self.tabla.winfo_children():
            w.destroy()
        for i, p in enumerate(proveedores):
            f = ctk.CTkFrame(self.tabla, fg_color="transparent")
            f.grid(row=i, column=0, sticky="ew", pady=1)
            f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(f, text=p.nombre, width=280, anchor="w").grid(
                row=0, column=0, padx=4, sticky="w")
            ctk.CTkLabel(f, text=(p.telefono or "—"), width=160,
                         anchor="w").grid(row=0, column=1, padx=4)
            color = "#c0392b" if p.saldo_cuenta > 0 else None
            ctk.CTkLabel(f, text=_money(p.saldo_cuenta), width=140,
                         text_color=color).grid(row=0, column=2, padx=4)
            ctk.CTkButton(f, text="Registrar pago", width=130,
                          command=lambda pid=p.id, n=p.nombre:
                          self._pagar(pid, n)).grid(row=0, column=3, padx=4)

    def _nuevo(self) -> None:
        datos = ProveedorDialog(self).mostrar()
        if datos is None:
            return
        try:
            proveedor_service.crear(datos["nombre"], datos["cuit"],
                                    datos["telefono"])
        except proveedor_service.ProveedorError as e:
            messagebox.showerror("No se pudo crear", str(e))
            return
        self._recargar()

    def _pagar(self, proveedor_id: str, nombre: str) -> None:
        monto = MontoDialog(self, "Registrar pago",
                            f"Pago a {nombre}:").mostrar()
        if monto is None:
            return
        try:
            proveedor_service.registrar_pago(proveedor_id, monto)
        except proveedor_service.ProveedorError as e:
            messagebox.showerror("No se pudo registrar", str(e))
            return
        self._recargar()
