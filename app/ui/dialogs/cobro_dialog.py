"""Modal de cobro: pago dividido (efectivo, transferencia, tarjeta) y fiado.

Reglas:
  - La suma de transferencia + tarjeta + fiado no puede superar el total.
  - El resto lo cubre el efectivo. Si pagan con más efectivo del necesario, se
    muestra el VUELTO (pero se registra solo lo que corresponde, así pagos_venta
    suma exactamente el total).
  - El selector de cliente aparece SOLO si se carga un monto en Fiado; ahí se
    puede buscar el cliente o crear uno nuevo al instante.

Devuelve (lista_de_pagos, cliente_id) o None si se cancela.
"""
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.models.venta import Pago, EFECTIVO, TRANSFERENCIA, TARJETA, FIADO
from app.ui import theme
from app.ui.dialogs.base import ModalBase
from app.ui.dialogs.buscar_cliente_dialog import BuscarClienteDialog

CERO = Decimal("0.00")


def _dec(texto: str) -> Decimal | None:
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return CERO
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    return valor if valor >= 0 else None


class CobroDialog(ModalBase):
    def __init__(self, master, total: Decimal):
        super().__init__(master, "Cobrar")
        self.total = total
        self._cliente_id = None
        self._cliente_nombre = None

        ctk.CTkLabel(self, text=f"Total a cobrar: ${total:,.2f}",
                     font=theme.fuente(22, "bold")).grid(
            row=0, column=0, columnspan=2, padx=24, pady=(20, 16))

        self.entries: dict[str, ctk.CTkEntry] = {}
        filas = [
            ("Efectivo (paga con)", "efectivo"),
            ("Transferencia / MP", TRANSFERENCIA),
            ("Tarjeta", TARJETA),
            ("Fiado", FIADO),
        ]
        for i, (etiqueta, clave) in enumerate(filas, start=1):
            ctk.CTkLabel(self, text=etiqueta, anchor="w",
                         font=theme.fuente(14)).grid(
                row=i, column=0, padx=(24, 8), pady=4, sticky="w")
            ent = ctk.CTkEntry(self, width=160, justify="right", placeholder_text="0")
            ent.grid(row=i, column=1, padx=(8, 24), pady=4)
            ent.bind("<KeyRelease>", self._recalcular)
            self.entries[clave] = ent

        ctk.CTkButton(self, text="Efectivo exacto", width=140, height=28,
                      fg_color="transparent", text_color=theme.ACCENT,
                      border_width=1, border_color=theme.GHOST,
                      hover_color=theme.GHOST,
                      command=self._efectivo_exacto).grid(
            row=5, column=0, columnspan=2, pady=(4, 8))

        # Fila de cliente: oculta hasta que haya monto en Fiado.
        self.fila_cliente = ctk.CTkFrame(self, fg_color="transparent")
        self.fila_cliente.grid(row=6, column=0, columnspan=2, padx=24,
                               pady=4, sticky="ew")
        self.fila_cliente.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.fila_cliente, text="Cliente del fiado:", anchor="w",
                     font=theme.fuente(14)).grid(row=0, column=0, padx=(0, 8))
        self.btn_cliente = ctk.CTkButton(
            self.fila_cliente, text="Buscar o crear cliente", height=34,
            corner_radius=8, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            command=self._elegir_cliente)
        self.btn_cliente.grid(row=0, column=1, sticky="ew")
        self.fila_cliente.grid_remove()

        self.lbl_estado = ctk.CTkLabel(self, text="", font=theme.fuente(14, "bold"))
        self.lbl_estado.grid(row=7, column=0, columnspan=2, padx=24, pady=(10, 8))

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=8, column=0, columnspan=2, pady=(4, 20))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Confirmar cobro", width=160,
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self.after(50, self.entries["efectivo"].focus_set)
        self._recalcular()

    # --- Cliente (solo visible con fiado) -----------------------------------

    def _toggle_cliente(self) -> None:
        fiado = _dec(self.entries[FIADO].get())
        if fiado and fiado > 0:
            self.fila_cliente.grid()
        else:
            self.fila_cliente.grid_remove()

    def _elegir_cliente(self) -> None:
        cli = BuscarClienteDialog(self).mostrar()
        if cli is None:
            return
        self._cliente_id = cli.id
        self._cliente_nombre = cli.nombre
        self.btn_cliente.configure(text=cli.nombre)

    # --- Cálculo en vivo ----------------------------------------------------

    def _leer(self) -> dict | None:
        valores = {}
        for clave, ent in self.entries.items():
            v = _dec(ent.get())
            if v is None:
                return None
            valores[clave] = v
        return valores

    def _calcular(self):
        v = self._leer()
        if v is None:
            return None
        otros = v[TRANSFERENCIA] + v[TARJETA] + v[FIADO]
        efectivo_necesario = self.total - otros
        tendered = v["efectivo"]
        if efectivo_necesario < 0:
            return ("EXCESO", otros, None, None)
        if efectivo_necesario == 0:
            return (otros, CERO, tendered, CERO)
        restante = efectivo_necesario - tendered
        if restante > 0:
            return (otros, efectivo_necesario, CERO, restante)
        return (otros, efectivo_necesario, tendered - efectivo_necesario, CERO)

    def _recalcular(self, _event=None) -> None:
        self._toggle_cliente()
        calc = self._calcular()
        if calc is None:
            self.lbl_estado.configure(text="⚠ Hay un monto inválido",
                                      text_color="orange")
            return
        if calc[0] == "EXCESO":
            self.lbl_estado.configure(
                text="⚠ Los otros pagos superan el total", text_color="orange")
            return
        _otros, _efectivo_nec, vuelto, restante = calc
        if restante and restante > 0:
            self.lbl_estado.configure(text=f"Falta: ${restante:,.2f}",
                                      text_color="orange")
        elif vuelto and vuelto > 0:
            self.lbl_estado.configure(text=f"Vuelto: ${vuelto:,.2f}",
                                      text_color="green")
        else:
            self.lbl_estado.configure(text="✓ Pago completo", text_color="green")

    def _efectivo_exacto(self) -> None:
        v = self._leer()
        if v is None:
            return
        otros = v[TRANSFERENCIA] + v[TARJETA] + v[FIADO]
        falta = self.total - otros
        ent = self.entries["efectivo"]
        ent.delete(0, "end")
        ent.insert(0, f"{max(falta, CERO):.2f}")
        self._recalcular()

    # --- Confirmación -------------------------------------------------------

    def _confirmar(self) -> None:
        calc = self._calcular()
        if calc is None or calc[0] == "EXCESO":
            self._recalcular()
            return
        _otros, efectivo_nec, _vuelto, restante = calc
        if restante and restante > 0:
            self.lbl_estado.configure(
                text=f"⚠ Falta cubrir ${restante:,.2f}", text_color="orange")
            return

        v = self._leer()
        pagos = []
        if efectivo_nec > 0:
            pagos.append(Pago(EFECTIVO, efectivo_nec))
        if v[TRANSFERENCIA] > 0:
            pagos.append(Pago(TRANSFERENCIA, v[TRANSFERENCIA]))
        if v[TARJETA] > 0:
            pagos.append(Pago(TARJETA, v[TARJETA]))

        cliente_id = None
        if v[FIADO] > 0:
            if self._cliente_id is None:
                self.lbl_estado.configure(
                    text="⚠ Elegí un cliente para el fiado", text_color="orange")
                return
            cliente_id = self._cliente_id
            pagos.append(Pago(FIADO, v[FIADO]))

        if not pagos:
            self.lbl_estado.configure(text="⚠ No ingresaste ningún pago",
                                      text_color="orange")
            return

        self._aceptar((pagos, cliente_id))
