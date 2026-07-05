"""Buscador de clientes para el fiado: filtra por nombre o teléfono y permite
crear uno nuevo al instante. Devuelve un Cliente o None si se cancela.
"""
from decimal import Decimal

import customtkinter as ctk

from app.models.cliente import Cliente
from app.services import cliente_service
from app.ui import theme
from app.ui.dialogs import notificar
from app.ui.dialogs.base import ModalBase
from app.ui.dialogs.cliente_dialog import ClienteDialog


class BuscarClienteDialog(ModalBase):
    def __init__(self, master):
        super().__init__(master, "Cliente del fiado")
        self._todos = cliente_service.listar_activos()

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=16, pady=(16, 8))
        barra.grid_columnconfigure(0, weight=1)
        self.ent = ctk.CTkEntry(
            barra, height=40, font=theme.fuente(15),
            placeholder_text="Buscar por nombre o teléfono…")
        self.ent.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.ent.bind("<KeyRelease>", lambda _e: self._filtrar())
        ctk.CTkButton(barra, text="Nuevo cliente", width=130, height=40,
                      corner_radius=8, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._nuevo).grid(row=0, column=1)

        self.lista = ctk.CTkScrollableFrame(self, width=440, height=300,
                                            fg_color=theme.CARD_BG, corner_radius=12)
        self.lista.pack(padx=16, pady=(0, 8), fill="both", expand=True)
        self.lista.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(self, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(pady=(0, 16))

        self.after(60, self.ent.focus_set)
        self._filtrar()

    def _filtrar(self) -> None:
        q = self.ent.get().strip().lower()
        for w in self.lista.winfo_children():
            w.destroy()
        filtrados = [c for c in self._todos
                     if not q or q in c.nombre.lower()
                     or (c.telefono and q in c.telefono.lower())]
        if not filtrados:
            ctk.CTkLabel(self.lista, text="Sin resultados.\nCrealo con "
                         "“Nuevo cliente”.", text_color=theme.TXT_MUTED,
                         justify="center").pack(pady=30)
            return
        for c in filtrados:
            sub = f"  ·  {c.telefono}" if c.telefono else ""
            ctk.CTkButton(self.lista, text=f"{c.nombre}{sub}", anchor="w",
                          height=40, corner_radius=8, fg_color="transparent",
                          text_color=theme.TXT, hover_color=theme.GHOST,
                          font=theme.fuente(15),
                          command=lambda cli=c: self._aceptar(cli)).pack(
                fill="x", padx=6, pady=2)

    def _nuevo(self) -> None:
        datos = ClienteDialog(self).mostrar()
        if datos is None:
            return
        try:
            cid = cliente_service.crear(datos["nombre"], datos["telefono"],
                                        datos["limite_credito"])
        except cliente_service.ClienteError as e:
            notificar.error(self, "No se pudo crear", str(e))
            return
        self._aceptar(Cliente(id=cid, nombre=datos["nombre"],
                              saldo_cuenta=Decimal("0"),
                              limite_credito=datos["limite_credito"],
                              telefono=datos["telefono"]))
