"""Vista de Clientes: listado con su deuda (cuenta corriente / fiado),
alta de cliente y registro de pagos cuando saldan su cuenta."""
from decimal import Decimal
from tkinter import messagebox

import customtkinter as ctk

from app.services import cliente_service
from app.ui import theme
from app.ui.dialogs.cliente_dialog import ClienteDialog
from app.ui.dialogs.proveedor_dialog import MontoDialog


def _money(v) -> str:
    return f"${Decimal(str(v)):,.2f}"


class ClientesView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Clientes", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Nuevo cliente", width=150, height=40,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._nuevo).grid(row=0, column=2)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=28)
        header.grid_columnconfigure(0, weight=1)
        for col, (txt, w) in enumerate(
                [("Cliente", 280), ("Teléfono", 160), ("Nos debe", 140), ("", 150)]):
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
        clientes = cliente_service.listar_activos()
        for w in self.tabla.winfo_children():
            w.destroy()
        if not clientes:
            ctk.CTkLabel(self.tabla, text="Todavía no hay clientes.\n"
                         "Creá el primero con “Nuevo cliente”.",
                         font=theme.fuente(14), text_color=theme.TXT_MUTED,
                         justify="center").pack(pady=36)
            return
        for i, c in enumerate(clientes):
            f = ctk.CTkFrame(self.tabla, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=3)
            f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(f, text=c.nombre, width=280, anchor="w",
                         font=theme.fuente(15), text_color=theme.TXT).grid(
                row=0, column=0, padx=4, sticky="w")
            ctk.CTkLabel(f, text=(c.telefono or "—"), width=160, anchor="w",
                         font=theme.fuente(13), text_color=theme.TXT_MUTED).grid(
                row=0, column=1, padx=4)
            color = theme.ROJO if c.saldo_cuenta > 0 else theme.TXT_MUTED
            ctk.CTkLabel(f, text=_money(c.saldo_cuenta), width=140, anchor="w",
                         font=theme.fuente(15, "bold"), text_color=color).grid(
                row=0, column=2, padx=4)
            ctk.CTkButton(f, text="Registrar pago", width=140, height=32,
                          corner_radius=8, font=theme.fuente(13),
                          fg_color="transparent", text_color=theme.ACCENT,
                          hover_color=theme.GHOST,
                          command=lambda cid=c.id, n=c.nombre:
                          self._pagar(cid, n)).grid(row=0, column=3, padx=4)

    def _nuevo(self) -> None:
        datos = ClienteDialog(self).mostrar()
        if datos is None:
            return
        try:
            cliente_service.crear(datos["nombre"], datos["telefono"],
                                  datos["limite_credito"])
        except cliente_service.ClienteError as e:
            messagebox.showerror("No se pudo crear", str(e))
            return
        self._recargar()

    def _pagar(self, cliente_id: str, nombre: str) -> None:
        monto = MontoDialog(self, "Registrar pago",
                            f"Pago de {nombre}:").mostrar()
        if monto is None:
            return
        try:
            cliente_service.registrar_pago(cliente_id, monto)
        except cliente_service.ClienteError as e:
            messagebox.showerror("No se pudo registrar", str(e))
            return
        self._recargar()
