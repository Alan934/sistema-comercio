"""Vista de Proveedores: listado con su deuda (cuenta corriente),
alta de proveedor y registro de pagos."""
from decimal import Decimal
from tkinter import messagebox

import customtkinter as ctk

from app.services import proveedor_service
from app.ui import theme
from app.ui.dialogs.proveedor_dialog import ProveedorDialog, MontoDialog


def _money(v) -> str:
    return f"${Decimal(str(v)):,.2f}"


def _texto_saldo(saldo):
    """Muestra la deuda en palabras: positivo = le debemos; negativo = a favor."""
    if saldo > 0:
        return f"Le debés {_money(saldo)}", theme.ROJO
    if saldo < 0:
        return f"{_money(abs(saldo))} a favor", theme.VERDE
    return "Al día", theme.TXT_MUTED


class ProveedoresView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Proveedores", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Nuevo proveedor", width=160, height=40,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._nuevo).grid(row=0, column=2)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=28)
        header.grid_columnconfigure(0, weight=1)
        for col, (txt, w) in enumerate(
                [("Proveedor", 280), ("Teléfono", 160), ("Deuda", 140), ("", 150)]):
            ctk.CTkLabel(header, text=txt, width=w, anchor="w",
                         font=theme.fuente(12, "bold"),
                         text_color=theme.TXT_MUTED).grid(row=0, column=col, padx=4)

        self.tabla = ctk.CTkScrollableFrame(self, fg_color=theme.CARD_BG,
                                            corner_radius=12)
        self.tabla.grid(row=2, column=0, sticky="nsew", padx=20, pady=(6, 18))
        self.tabla.grid_columnconfigure(0, weight=1)

    def al_mostrar(self) -> None:
        self._recargar()

    def _recargar(self) -> None:
        proveedores = proveedor_service.listar_activos()
        for w in self.tabla.winfo_children():
            w.destroy()
        if not proveedores:
            ctk.CTkLabel(self.tabla, text="Todavía no hay proveedores.\n"
                         "Creá el primero con “Nuevo proveedor”.",
                         font=theme.fuente(14), text_color=theme.TXT_MUTED,
                         justify="center").pack(pady=36)
            return
        for i, p in enumerate(proveedores):
            f = ctk.CTkFrame(self.tabla, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=3)
            f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(f, text=p.nombre, width=280, anchor="w",
                         font=theme.fuente(15), text_color=theme.TXT).grid(
                row=0, column=0, padx=4, sticky="w")
            ctk.CTkLabel(f, text=(p.telefono or "—"), width=160, anchor="w",
                         font=theme.fuente(13), text_color=theme.TXT_MUTED).grid(
                row=0, column=1, padx=4)
            txt, color = _texto_saldo(p.saldo_cuenta)
            ctk.CTkLabel(f, text=txt, width=140, anchor="w",
                         font=theme.fuente(15, "bold"), text_color=color).grid(
                row=0, column=2, padx=4)
            ctk.CTkButton(f, text="Registrar pago", width=140, height=32,
                          corner_radius=8, font=theme.fuente(13),
                          fg_color="transparent", text_color=theme.ACCENT,
                          hover_color=theme.GHOST,
                          command=lambda pid=p.id, n=p.nombre, s=p.saldo_cuenta:
                          self._pagar(pid, n, s)).grid(row=0, column=3, padx=4)

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

    def _pagar(self, proveedor_id: str, nombre: str, saldo) -> None:
        monto = MontoDialog(self, "Registrar pago",
                            f"Pago a {nombre}:").mostrar()
        if monto is None:
            return
        if monto > saldo:
            if saldo > 0:
                msg = (f"Le debés {_money(saldo)} y vas a registrar un pago de "
                       f"{_money(monto)}.\nLe quedarán {_money(monto - saldo)} a "
                       "favor tuyo. ¿Continuar?")
            else:
                msg = (f"{nombre} no tiene deuda. El pago de {_money(monto)} le "
                       "quedará a favor tuyo. ¿Continuar?")
            if not messagebox.askyesno("Pago mayor a la deuda", msg):
                return
        try:
            proveedor_service.registrar_pago(proveedor_id, monto)
        except proveedor_service.ProveedorError as e:
            messagebox.showerror("No se pudo registrar", str(e))
            return
        self._recargar()
