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

from app.core import formato

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

        self.grid_columnconfigure(0, weight=1)

        # --- Encabezado: tarjeta teal con el total bien grande ---------------
        cabecera = ctk.CTkFrame(self, fg_color=theme.PRIMARY, corner_radius=0)
        cabecera.grid(row=0, column=0, sticky="ew")
        cabecera.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cabecera, text="TOTAL A COBRAR", text_color="#CFEDE3",
                     font=theme.fuente(13, "bold")).grid(
            row=0, column=0, padx=28, pady=(18, 0))
        ctk.CTkLabel(cabecera, text=f"{formato.moneda(total)}", text_color="#FFFFFF",
                     font=theme.fuente(38, "bold")).grid(
            row=1, column=0, padx=28, pady=(0, 18))

        # --- Cuerpo: filas de medios de pago ---------------------------------
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.grid(row=1, column=0, sticky="ew", padx=24, pady=(18, 4))
        cuerpo.grid_columnconfigure(0, weight=1)

        self.entries: dict[str, ctk.CTkEntry] = {}
        filas = [
            ("💵", "Efectivo", "con cuánto paga", "efectivo"),
            ("🏦", "Transferencia / MP", "", TRANSFERENCIA),
            ("💳", "Tarjeta", "", TARJETA),
            ("📝", "Fiado", "queda a cuenta", FIADO),
        ]
        for i, (icono, etiqueta, ayuda, clave) in enumerate(filas):
            fila = ctk.CTkFrame(cuerpo, fg_color=theme.CARD_BG, corner_radius=10)
            fila.grid(row=i, column=0, sticky="ew", pady=3)
            fila.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(fila, text=icono, font=theme.fuente(18)).grid(
                row=0, column=0, rowspan=2 if ayuda else 1, padx=(14, 10),
                pady=10)
            ctk.CTkLabel(fila, text=etiqueta, anchor="w",
                         font=theme.fuente(15, "bold"), text_color=theme.TXT).grid(
                row=0, column=1, sticky="w", pady=(10, 0) if ayuda else 10)
            if ayuda:
                ctk.CTkLabel(fila, text=ayuda, anchor="w", font=theme.fuente(11),
                             text_color=theme.TXT_MUTED).grid(
                    row=1, column=1, sticky="w", pady=(0, 8))
            ent = ctk.CTkEntry(fila, width=140, height=40, justify="right",
                               font=theme.fuente(18), placeholder_text="0",
                               corner_radius=8)
            ent.grid(row=0, column=2, rowspan=2 if ayuda else 1, padx=(8, 8),
                     pady=10)
            ent.bind("<KeyRelease>", self._recalcular)
            self.entries[clave] = ent

            # Botón que rellena ESTE campo con lo que falta para el total.
            ctk.CTkButton(
                fila, text="= Total", width=72, height=40, corner_radius=8,
                font=theme.fuente(12, "bold"), fg_color="transparent",
                text_color=theme.ACCENT, border_width=1,
                border_color=theme.GHOST, hover_color=theme.GHOST,
                command=lambda c=clave: self._completar_campo(c)).grid(
                row=0, column=3, rowspan=2 if ayuda else 1, padx=(0, 14),
                pady=10)

        # Fila de cliente: oculta hasta que haya monto en Fiado.
        self.fila_cliente = ctk.CTkFrame(self, fg_color="transparent")
        self.fila_cliente.grid(row=2, column=0, padx=24, pady=(2, 0), sticky="ew")
        self.fila_cliente.grid_columnconfigure(0, weight=1)
        self.btn_cliente = ctk.CTkButton(
            self.fila_cliente, text="👤  Elegir cliente del fiado", height=40,
            corner_radius=8, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            command=self._elegir_cliente)
        self.btn_cliente.grid(row=0, column=0, sticky="ew")
        self.fila_cliente.grid_remove()

        # --- Pill de estado (vuelto / falta / completo) ----------------------
        self.pill = ctk.CTkFrame(self, fg_color=theme.GHOST, corner_radius=12)
        self.pill.grid(row=3, column=0, padx=24, pady=(14, 8), sticky="ew")
        self.pill.grid_columnconfigure(0, weight=1)
        self.lbl_estado = ctk.CTkLabel(self.pill, text="", font=theme.fuente(20, "bold"))
        self.lbl_estado.grid(row=0, column=0, padx=16, pady=12)

        # --- Botones ---------------------------------------------------------
        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=4, column=0, pady=(4, 18))
        ctk.CTkButton(cont, text="Cancelar", width=130, height=44,
                      corner_radius=10, fg_color="transparent",
                      text_color=theme.TXT_MUTED, border_width=1,
                      border_color=theme.GHOST, hover_color=theme.GHOST,
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Confirmar cobro", width=190, height=44,
                      corner_radius=10, font=theme.fuente(15, "bold"),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.after(50, self.entries["efectivo"].focus_set)
        self._recalcular()

    # --- Estado (pill de color) ---------------------------------------------

    def _set_estado(self, texto: str, color, fondo) -> None:
        self.pill.configure(fg_color=fondo)
        self.lbl_estado.configure(text=texto, text_color=color)

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
        self.btn_cliente.configure(text=f"👤  {cli.nombre}")

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
            self._set_estado("Hay un monto inválido", theme.ROJO, theme.GHOST)
            return
        if calc[0] == "EXCESO":
            self._set_estado("Los otros pagos superan el total",
                             theme.ROJO, theme.GHOST)
            return
        _otros, _efectivo_nec, vuelto, restante = calc
        if restante and restante > 0:
            self._set_estado(f"Falta:  {formato.moneda(restante)}", theme.ROJO, theme.GHOST)
        elif vuelto and vuelto > 0:
            self._set_estado(f"Vuelto:  {formato.moneda(vuelto)}", "#FFFFFF", theme.VERDE)
        else:
            self._set_estado("✓  Pago completo", "#FFFFFF", theme.VERDE)

    def _completar_campo(self, clave: str) -> None:
        """Rellena `clave` con lo que falta para el total según los demás campos."""
        v = self._leer()
        if v is None:
            return
        otros = sum((valor for k, valor in v.items() if k != clave), CERO)
        falta = self.total - otros
        ent = self.entries[clave]
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
            self._set_estado(f"Falta cubrir {formato.moneda(restante)}", theme.ROJO,
                             theme.GHOST)
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
                self._set_estado("Elegí un cliente para el fiado", theme.ROJO,
                                 theme.GHOST)
                return
            cliente_id = self._cliente_id
            pagos.append(Pago(FIADO, v[FIADO]))

        if not pagos:
            self._set_estado("No ingresaste ningún pago", theme.ROJO, theme.GHOST)
            return

        self._aceptar((pagos, cliente_id))
