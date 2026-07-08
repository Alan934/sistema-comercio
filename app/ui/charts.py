"""Gráficos livianos dibujados sobre tkinter.Canvas (sin matplotlib).

Cada gráfico es un CTkFrame con un Canvas adentro que se redibuja cuando
cambia de tamaño (<Configure>). Los colores se resuelven al modo claro/oscuro
en el momento de dibujar.
"""
import tkinter as tk

import customtkinter as ctk

from app.core import formato

from app.ui import theme


def _hex(color) -> str:
    """Resuelve una tupla (claro, oscuro) al color del modo actual."""
    if isinstance(color, (tuple, list)):
        return color[1] if ctk.get_appearance_mode().lower() == "dark" else color[0]
    return color


def _money(v) -> str:
    return formato.moneda(v, decimales=0)


class _BaseChart(ctk.CTkFrame):
    def __init__(self, master, alto: int = 190):
        super().__init__(master, fg_color="transparent")
        self.canvas = tk.Canvas(self, height=alto, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._dibujar())

    def _vacio(self, w, h) -> None:
        self.canvas.create_text(w / 2, h / 2, text="Sin datos en el período",
                                fill=_hex(theme.TXT_MUTED), font=("", 11))

    def _dibujar(self) -> None:  # lo implementan las subclases
        raise NotImplementedError


class BarChart(_BaseChart):
    """Gráfico de barras verticales. puntos = [(etiqueta, valor)]."""

    def __init__(self, master, alto: int = 190):
        super().__init__(master, alto)
        self._puntos = []
        self._color = theme.ACCENT

    def set_data(self, puntos, color=None) -> None:
        self._puntos = puntos or []
        if color is not None:
            self._color = color
        self._dibujar()

    def _dibujar(self) -> None:
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            return
        c.configure(bg=_hex(theme.CARD_BG))
        valores = [float(v) for _, v in self._puntos]
        if not valores or max(valores) <= 0:
            self._vacio(w, h)
            return

        ml, mr, mt, mb = 12, 12, 16, 26
        base_y = h - mb
        plot_h = base_y - mt
        n = len(self._puntos)
        maxv = max(valores)
        gap = 4 if n <= 40 else 2
        bw = max(2, (w - ml - mr - gap * (n - 1)) / n)
        col = _hex(self._color)
        muted = _hex(theme.TXT_MUTED)

        c.create_line(ml, base_y, w - mr, base_y, fill=muted)
        c.create_text(ml, mt - 6, text=_money(maxv), fill=muted,
                      font=("", 9), anchor="w")
        for i, (_, v) in enumerate(self._puntos):
            x0 = ml + i * (bw + gap)
            bh = plot_h * (float(v) / maxv)
            c.create_rectangle(x0, base_y - bh, x0 + bw, base_y,
                               fill=col, width=0)
        paso = max(1, n // 8)
        for i in range(0, n, paso):
            x = ml + i * (bw + gap) + bw / 2
            c.create_text(x, base_y + 13, text=self._puntos[i][0],
                          fill=muted, font=("", 9))


class DonutChart(_BaseChart):
    """Gráfico de dona con leyenda. items = [(etiqueta, valor)]."""

    def __init__(self, master, alto: int = 180):
        super().__init__(master, alto)
        self._items = []

    def set_data(self, items) -> None:
        self._items = [(str(l), float(v)) for l, v in (items or []) if float(v) > 0]
        self._dibujar()

    def _dibujar(self) -> None:
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            return
        c.configure(bg=_hex(theme.CARD_BG))
        total = sum(v for _, v in self._items)
        if total <= 0:
            self._vacio(w, h)
            return

        d = min(h - 16, w * 0.46)
        x0, y0 = 10, (h - d) / 2
        x1, y1 = x0 + d, y0 + d
        cx, cy = x0 + d / 2, y0 + d / 2

        if len(self._items) == 1:
            c.create_oval(x0, y0, x1, y1,
                          fill=_hex(theme.CHART_PALETTE[0]), outline="")
        else:
            ini = 90.0
            for i, (_, v) in enumerate(self._items):
                ext = -359.999 * (v / total)
                color = _hex(theme.CHART_PALETTE[i % len(theme.CHART_PALETTE)])
                c.create_arc(x0, y0, x1, y1, start=ini, extent=ext,
                             fill=color, outline="", style="pieslice")
                ini += ext
        hueco = d * 0.56
        c.create_oval(cx - hueco / 2, cy - hueco / 2, cx + hueco / 2,
                      cy + hueco / 2, fill=_hex(theme.CARD_BG), outline="")

        lx = x1 + 16
        ly = cy - len(self._items) * 9
        for i, (lab, v) in enumerate(self._items):
            color = _hex(theme.CHART_PALETTE[i % len(theme.CHART_PALETTE)])
            yy = ly + i * 18
            c.create_rectangle(lx, yy, lx + 12, yy + 12, fill=color, outline="")
            pct = round(100 * v / total)
            c.create_text(lx + 18, yy + 6, text=f"{lab}  {pct}%",
                          fill=_hex(theme.TXT), font=("", 10), anchor="w")
