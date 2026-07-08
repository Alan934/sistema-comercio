"""Modal de alertas de stock: reemplaza el `messagebox.showinfo` con viñetas
por una lista temática y legible de un vistazo.

- Stock bajo: acento rojo, muestra actual vs. mínimo.
- Por vencer: acento ámbar, muestra fecha y días restantes.
"""
import customtkinter as ctk

from app.core import formato

from app.ui import theme
from app.ui.dialogs.base import ModalBase


class AlertasDialog(ModalBase):
    def __init__(self, master, bajos: list[dict], vencs: list[dict]):
        super().__init__(master, "Alertas de stock")

        ctk.CTkLabel(self, text="Alertas de stock", font=theme.fuente(20, "bold"),
                     text_color=theme.TXT).pack(padx=26, pady=(22, 4), anchor="w")

        resumen = []
        if bajos:
            resumen.append(f"{len(bajos)} con stock bajo")
        if vencs:
            resumen.append(f"{len(vencs)} por vencer")
        ctk.CTkLabel(self, text=("  ·  ".join(resumen) if resumen
                                 else "Todo en orden, sin alertas."),
                     font=theme.fuente(13), text_color=theme.TXT_MUTED).pack(
            padx=26, anchor="w")

        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                        width=440, height=360)
        cuerpo.pack(padx=20, pady=14, fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=1)

        if not bajos and not vencs:
            ctk.CTkLabel(cuerpo, text="✓  No hay productos con stock bajo\n"
                                      "ni próximos a vencer.",
                         font=theme.fuente(15), text_color=theme.VERDE,
                         justify="center").pack(pady=60)

        if bajos:
            self._seccion(cuerpo, "STOCK BAJO", theme.ROJO)
            for b in bajos:
                self._fila(
                    cuerpo, theme.ROJO, b["nombre"],
                    f"Quedan {formato.numero(b['stock_actual'])}  ·  mínimo {formato.numero(b['stock_minimo'])}")

        if vencs:
            self._seccion(cuerpo, "POR VENCER (7 días)", theme.BADGE_KG_TXT)
            for v in vencs:
                dias = v["dias_restantes"]
                detalle = ("vence hoy" if dias == 0
                           else f"en {dias} día{'s' if dias != 1 else ''}")
                self._fila(cuerpo, theme.BADGE_KG_TXT, v["producto"],
                           f"{v['fecha_vencimiento']}  ·  {detalle}")

        ctk.CTkButton(self, text="Entendido", width=160, height=42,
                      corner_radius=10, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._cancelar).pack(pady=(0, 22))

    def _seccion(self, parent, texto, color) -> None:
        ctk.CTkLabel(parent, text=texto, anchor="w",
                     font=theme.fuente(12, "bold"), text_color=color).pack(
            fill="x", pady=(12, 4))

    def _fila(self, parent, color, titulo, detalle) -> None:
        f = ctk.CTkFrame(parent, fg_color=theme.CARD_BG, corner_radius=10)
        f.pack(fill="x", pady=3)
        f.grid_columnconfigure(1, weight=1)
        # Barra de color a la izquierda (indicador de severidad).
        ctk.CTkFrame(f, width=5, height=42, corner_radius=3, fg_color=color).grid(
            row=0, column=0, rowspan=2, padx=(8, 12), pady=8)
        ctk.CTkLabel(f, text=titulo, anchor="w", font=theme.fuente(15, "bold"),
                     text_color=theme.TXT).grid(row=0, column=1, sticky="w",
                                                pady=(8, 0))
        ctk.CTkLabel(f, text=detalle, anchor="w", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(row=1, column=1, sticky="w",
                                                      pady=(0, 8))
