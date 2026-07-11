"""Vista de Cierre de caja (solo admin): resumen del período abierto, botón
para hacer el cierre, e historial con las diferencias (para las métricas)."""
from datetime import datetime
from decimal import Decimal

import customtkinter as ctk

from app.core import formato

from app.services import cierre_service
from app.ui import theme
from app.ui.tablas import PintorEnTandas
from app.ui.dialogs import notificar
from app.ui.dialogs.cierre_dialog import CierreDialog


def _money(v) -> str:
    return formato.moneda(v)


def _fmt(ts) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromisoformat(ts).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return str(ts)[:16]


class CierresView(ctk.CTkFrame):
    def __init__(self, master, usuario):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Cierre de caja", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Realizar cierre", width=170, height=40,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._realizar).grid(row=0, column=2)

        # Tarjeta con el período abierto (desde el último cierre).
        self.card = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=12)
        self.card.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 8))

        # Historial de cierres.
        ctk.CTkLabel(self, text="Historial de cierres",
                     font=theme.fuente(14, "bold"), text_color=theme.TXT_MUTED).grid(
            row=2, column=0, sticky="nw", padx=24, pady=(2, 0))
        self.tabla = ctk.CTkScrollableFrame(self, fg_color=theme.CARD_BG,
                                            corner_radius=12)
        self.tabla.grid(row=3, column=0, sticky="nsew", padx=20, pady=(24, 18))
        self.tabla.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._pintor = PintorEnTandas(self.tabla)

    def al_mostrar(self) -> None:
        self._recargar()

    def _recargar(self) -> None:
        r = cierre_service.resumen_periodo_abierto()
        for w in self.card.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.card, text="Período sin cerrar", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).pack(anchor="w", padx=16, pady=(12, 0))
        resumen = (f"{r['ventas_cantidad']} ventas  ·  vendido {_money(r['total_vendido'])}"
                   f"  ·  efectivo {_money(r['efectivo'])}  ·  gastos {_money(r['gastos'])}")
        ctk.CTkLabel(self.card, text=resumen, font=theme.fuente(15),
                     text_color=theme.TXT).pack(anchor="w", padx=16, pady=(2, 0))
        # Efectivo que entró/salió por cuenta corriente (fiados cobrados, pagos).
        neto = (f"+ cobros de fiado {_money(r['cobros_efectivo'])}"
                f"   ·   − pagos a proveedores {_money(r['pagos_efectivo'])}")
        ctk.CTkLabel(self.card, text=neto, font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).pack(anchor="w", padx=16,
                                                      pady=(0, 12))

        for w in self.tabla.winfo_children():
            w.destroy()
        self._pintor.cancelar()
        cierres = cierre_service.listar_cierres()
        if not cierres:
            ctk.CTkLabel(self.tabla, text="Todavía no hiciste ningún cierre.",
                         text_color=theme.TXT_MUTED).pack(pady=30)
            return
        self._pintor.pintar(cierres, self._fila_cierre)

    def _fila_cierre(self, c, i: int) -> None:
        f = ctk.CTkFrame(self.tabla,
                         fg_color=theme.ROW_ALT if i % 2 else "transparent",
                         corner_radius=8)
        f.pack(fill="x", padx=6, pady=1)
        f.grid_columnconfigure(4, weight=1)
        dif = Decimal(str(c["diferencia"]))
        col = theme.VERDE if dif >= 0 else theme.ROJO
        etiqueta = "sobrante" if dif > 0 else ("faltante" if dif < 0 else "exacto")
        ctk.CTkLabel(f, text=_fmt(c["fecha"]), width=150, anchor="w",
                     font=theme.fuente(14), text_color=theme.TXT).grid(
            row=0, column=0, padx=4)
        ctk.CTkLabel(f, text=f"vendido {_money(c['total_vendido'])}", width=170,
                     anchor="w", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(row=0, column=1, padx=4)
        ctk.CTkLabel(f, text=f"efvo {_money(c['efectivo_ventas'])}", width=150,
                     anchor="w", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(row=0, column=2, padx=4)
        ctk.CTkLabel(f, text=f"contó {_money(c['efectivo_contado'])}", width=150,
                     anchor="w", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(row=0, column=3, padx=4)
        ctk.CTkLabel(f, text=f"{_money(dif)} ({etiqueta})", anchor="e",
                     font=theme.fuente(14, "bold"), text_color=col).grid(
            row=0, column=4, sticky="e", padx=8)

    def _realizar(self) -> None:
        resumen = cierre_service.resumen_periodo_abierto()
        if resumen["ventas_cantidad"] == 0 and resumen["gastos"] == 0:
            if not notificar.confirmar(
                    self, "Cierre de caja",
                    "No hubo ventas ni gastos en este período. ¿Cerrar igual?",
                    confirmar_txt="Cerrar igual", cancelar_txt="No"):
                return
        datos = CierreDialog(self, resumen).mostrar()
        if datos is None:
            return
        res = cierre_service.realizar_cierre(
            self.usuario, resumen, datos["fondo"], datos["contado"], datos["nota"])
        dif = res["diferencia"]
        estado = ("Caja exacta." if dif == 0
                  else (f"Sobrante de {_money(dif)}." if dif > 0
                        else f"Faltante de {_money(abs(dif))}."))
        tipo = "ok" if dif == 0 else "info"
        notificar.informar(
            self, "Cierre registrado",
            f"Esperado en caja: {_money(res['efectivo_esperado'])}. {estado}",
            tipo=tipo)
        self._recargar()
