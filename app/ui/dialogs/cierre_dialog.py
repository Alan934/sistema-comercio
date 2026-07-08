"""Modal de cierre de caja: muestra los totales del período, el admin ingresa
el fondo inicial y el efectivo contado, y ve el esperado y la diferencia.

Devuelve {fondo, contado, nota} o None si se cancela.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.core import formato

from app.ui import theme
from app.ui.dialogs.base import ModalBase


def _money(v) -> str:
    return formato.moneda(v)


def _dec(texto) -> Decimal:
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return Decimal("0")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return Decimal("0")


def _fmt_desde(desde) -> str:
    if not desde:
        return "desde el inicio"
    try:
        d = datetime.fromisoformat(desde)
        return "desde " + d.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return "desde el último cierre"


class CierreDialog(ModalBase):
    def __init__(self, master, resumen: dict):
        super().__init__(master, "Cierre de caja")
        self.resumen = resumen

        ctk.CTkLabel(self, text="Cierre de caja", font=theme.fuente(20, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, columnspan=2,
                                                padx=20, pady=(18, 2))
        ctk.CTkLabel(self, text=_fmt_desde(resumen.get("desde")),
                     font=theme.fuente(12), text_color=theme.TXT_MUTED).grid(
            row=1, column=0, columnspan=2, padx=20, pady=(0, 10))

        filas = [
            ("Ventas", str(resumen["ventas_cantidad"])),
            ("Total vendido", _money(resumen["total_vendido"])),
            ("Ventas en efectivo", _money(resumen["efectivo"])),
            ("Transferencia / MP", _money(resumen["transferencia"])),
            ("Tarjeta", _money(resumen["tarjeta"])),
            ("Fiado (no es plata aún)", _money(resumen["fiado"])),
            ("+ Cobros de fiado en efectivo", _money(resumen["cobros_efectivo"])),
            ("− Pagos a proveedores en efectivo", _money(resumen["pagos_efectivo"])),
            ("− Gastos en efectivo", _money(resumen["gastos_efectivo"])),
        ]
        r = 2
        for etiqueta, valor in filas:
            ctk.CTkLabel(self, text=etiqueta, anchor="w", font=theme.fuente(13),
                         text_color=theme.TXT_MUTED).grid(
                row=r, column=0, sticky="w", padx=(24, 8), pady=2)
            ctk.CTkLabel(self, text=valor, anchor="e", font=theme.fuente(14),
                         text_color=theme.TXT).grid(
                row=r, column=1, sticky="e", padx=(8, 24), pady=2)
            r += 1

        ctk.CTkFrame(self, height=1, fg_color=theme.GHOST).grid(
            row=r, column=0, columnspan=2, sticky="ew", padx=24, pady=8)
        r += 1

        ctk.CTkLabel(self, text="Fondo inicial (caja)", anchor="w").grid(
            row=r, column=0, sticky="w", padx=(24, 8), pady=4)
        self.ent_fondo = ctk.CTkEntry(self, width=160, justify="right")
        self.ent_fondo.insert(0, "0")
        self.ent_fondo.grid(row=r, column=1, padx=(8, 24), pady=4)
        self.ent_fondo.bind("<KeyRelease>", self._recalcular)
        r += 1

        ctk.CTkLabel(self, text="Efectivo contado", anchor="w").grid(
            row=r, column=0, sticky="w", padx=(24, 8), pady=4)
        self.ent_contado = ctk.CTkEntry(self, width=160, justify="right")
        self.ent_contado.grid(row=r, column=1, padx=(8, 24), pady=4)
        self.ent_contado.bind("<KeyRelease>", self._recalcular)
        r += 1

        ctk.CTkLabel(self, text="Efectivo esperado", anchor="w",
                     font=theme.fuente(13), text_color=theme.TXT_MUTED).grid(
            row=r, column=0, sticky="w", padx=(24, 8), pady=(6, 2))
        self.lbl_esperado = ctk.CTkLabel(self, text="$0,00", anchor="e",
                                         font=theme.fuente(15, "bold"))
        self.lbl_esperado.grid(row=r, column=1, sticky="e", padx=(8, 24), pady=(6, 2))
        r += 1

        ctk.CTkLabel(self, text="Diferencia", anchor="w",
                     font=theme.fuente(13), text_color=theme.TXT_MUTED).grid(
            row=r, column=0, sticky="w", padx=(24, 8), pady=2)
        self.lbl_dif = ctk.CTkLabel(self, text="$0,00", anchor="e",
                                    font=theme.fuente(16, "bold"))
        self.lbl_dif.grid(row=r, column=1, sticky="e", padx=(8, 24), pady=2)
        r += 1

        ctk.CTkLabel(self, text="Nota (opcional)", anchor="w").grid(
            row=r, column=0, sticky="w", padx=(24, 8), pady=(6, 4))
        self.ent_nota = ctk.CTkEntry(self, width=240)
        self.ent_nota.grid(row=r, column=1, padx=(8, 24), pady=(6, 4))
        r += 1

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=r, column=0, columnspan=2, pady=(10, 16))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Confirmar cierre", width=170,
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.after(50, self.ent_contado.focus_set)
        self._recalcular()

    def _recalcular(self, _event=None) -> None:
        fondo = _dec(self.ent_fondo.get())
        contado = _dec(self.ent_contado.get())
        esperado = (fondo + self.resumen["efectivo"]
                    + self.resumen["cobros_efectivo"]
                    - self.resumen["pagos_efectivo"]
                    - self.resumen["gastos_efectivo"])
        dif = contado - esperado
        self.lbl_esperado.configure(text=_money(esperado))
        if dif > 0:
            self.lbl_dif.configure(text=f"{_money(dif)}  (sobrante)",
                                   text_color=theme.VERDE)
        elif dif < 0:
            self.lbl_dif.configure(text=f"{_money(dif)}  (faltante)",
                                   text_color=theme.ROJO)
        else:
            self.lbl_dif.configure(text="$0,00  (exacto)", text_color=theme.VERDE)

    def _confirmar(self) -> None:
        self._aceptar({
            "fondo": _dec(self.ent_fondo.get()),
            "contado": _dec(self.ent_contado.get()),
            "nota": self.ent_nota.get().strip() or None,
        })
