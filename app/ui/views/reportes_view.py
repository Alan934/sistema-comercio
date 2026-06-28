"""Vista de Reportes + Gastos: período seleccionable, tarjetas de resumen
(con la ganancia neta destacada), desgloses y alta de gastos."""
from datetime import date, timedelta
from decimal import Decimal
from tkinter import messagebox

import customtkinter as ctk

from app.services import reporte_service, gasto_service
from app.ui import theme
from app.ui.charts import BarChart, DonutChart
from app.ui.dialogs.gasto_dialog import GastoDialog


def _money(v) -> str:
    return f"${Decimal(str(v)):,.2f}"


class ReportesView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Reportes", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        self.seg_periodo = ctk.CTkSegmentedButton(
            top, values=["Hoy", "Semana", "Mes", "Año"],
            font=theme.fuente(13), selected_color=theme.PRIMARY,
            selected_hover_color=theme.PRIMARY_HOVER,
            command=lambda _v: self._render())
        self.seg_periodo.set("Mes")
        self.seg_periodo.grid(row=0, column=1, padx=8)
        ctk.CTkButton(top, text="Registrar gasto", width=150, height=40,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._registrar_gasto).grid(row=0, column=2, padx=4)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(6, 18))
        self.scroll.grid_columnconfigure(0, weight=1)

    def al_mostrar(self) -> None:
        self._render()

    # --- Período ------------------------------------------------------------

    def _periodo(self) -> tuple[date, date]:
        hoy = date.today()
        sel = self.seg_periodo.get()
        if sel == "Hoy":
            return hoy, hoy
        if sel == "Semana":
            return hoy - timedelta(days=6), hoy
        if sel == "Año":
            return hoy.replace(month=1, day=1), hoy
        return hoy.replace(day=1), hoy

    # --- Render -------------------------------------------------------------

    def _render(self) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()
        desde, hasta = self._periodo()

        ctk.CTkLabel(self.scroll, text=f"Del {desde} al {hasta}",
                     font=theme.fuente(13), text_color=theme.TXT_MUTED).pack(
            anchor="w", padx=2, pady=(2, 8))

        r = reporte_service.resumen(desde, hasta)
        self._tarjetas(r)

        # Gráfico de tendencia de ventas (barras).
        serie = reporte_service.ventas_serie(desde, hasta)
        card = self._card(serie["titulo"])
        grafico = BarChart(card, alto=190)
        grafico.pack(fill="x", padx=14, pady=(0, 12))
        grafico.set_data(serie["puntos"], theme.ACCENT)

        # Dos donas lado a lado: métodos de pago y gastos por tipo.
        fila = ctk.CTkFrame(self.scroll, fg_color="transparent")
        fila.pack(fill="x", padx=2, pady=6)
        fila.grid_columnconfigure((0, 1), weight=1, uniform="donas")
        self._dona(fila, 0, "Ventas por método de pago", [
            (m["metodo"], m["total"])
            for m in reporte_service.ventas_por_metodo(desde, hasta)])
        self._dona(fila, 1, "Gastos por tipo", [
            (g["tipo"], g["total"])
            for g in reporte_service.gastos_por_tipo(desde, hasta)])

        self._seccion("Productos más vendidos", [
            (f"{t['producto']}  ({t['cantidad']})", _money(t["total"]))
            for t in reporte_service.top_productos(desde, hasta, 10)])

        pp = reporte_service.por_proveedor(desde, hasta)
        self._seccion("Compras por proveedor", [
            (c["proveedor"], _money(c["total"])) for c in pp["compras"]])
        self._seccion("Gastos por proveedor", [
            (g["proveedor"], _money(g["total"])) for g in pp["gastos"]])

        self._seccion("Detalle de gastos del período", [
            (f"[{g['tipo']}] {g['descripcion']}"
             + (f"  · {g['proveedor_nombre']}" if g["proveedor_nombre"] else ""),
             _money(g["monto"]))
            for g in gasto_service.listar(desde.isoformat(), hasta.isoformat())])

    def _tarjetas(self, r: dict) -> None:
        cont = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cont.pack(fill="x", padx=2, pady=4)
        for i in range(3):
            cont.grid_columnconfigure(i, weight=1, uniform="cards")

        neta = r["ganancia_neta"]
        color_neta = theme.VERDE if neta >= 0 else theme.ROJO
        tarjetas = [
            ("Ventas", str(r["ventas_cantidad"]), theme.TXT),
            ("Total vendido", _money(r["total_vendido"]), theme.TXT),
            ("Costo total", _money(r["costo_total"]), theme.TXT),
            ("Ganancia bruta", _money(r["ganancia_bruta"]), theme.TXT),
            ("Gastos", _money(r["gastos_total"]), theme.TXT),
            ("Ganancia neta", _money(neta), color_neta),
        ]
        for idx, (titulo, valor, color) in enumerate(tarjetas):
            card = ctk.CTkFrame(cont, fg_color=theme.CARD_BG, corner_radius=12)
            card.grid(row=idx // 3, column=idx % 3, padx=6, pady=6, sticky="ew")
            ctk.CTkLabel(card, text=titulo, font=theme.fuente(13),
                         text_color=theme.TXT_MUTED, anchor="w").pack(
                anchor="w", padx=14, pady=(12, 0))
            ctk.CTkLabel(card, text=valor, font=theme.fuente(22, "bold"),
                         text_color=color, anchor="w").pack(
                anchor="w", padx=14, pady=(0, 12))

    def _card(self, titulo: str) -> ctk.CTkFrame:
        """Crea una tarjeta con título y la devuelve para meterle un gráfico."""
        card = ctk.CTkFrame(self.scroll, fg_color=theme.CARD_BG, corner_radius=12)
        card.pack(fill="x", padx=2, pady=6)
        ctk.CTkLabel(card, text=titulo, font=theme.fuente(15, "bold"),
                     text_color=theme.TXT).pack(anchor="w", padx=16, pady=(12, 6))
        return card

    def _dona(self, parent, columna: int, titulo: str, items) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD_BG, corner_radius=12)
        card.grid(row=0, column=columna, sticky="nsew",
                  padx=(0, 6) if columna == 0 else (6, 0))
        ctk.CTkLabel(card, text=titulo, font=theme.fuente(15, "bold"),
                     text_color=theme.TXT).pack(anchor="w", padx=16, pady=(12, 4))
        dona = DonutChart(card, alto=180)
        dona.pack(fill="x", padx=14, pady=(0, 12))
        dona.set_data(items)

    def _seccion(self, titulo: str, filas: list[tuple[str, str]]) -> None:
        card = ctk.CTkFrame(self.scroll, fg_color=theme.CARD_BG, corner_radius=12)
        card.pack(fill="x", padx=2, pady=6)
        ctk.CTkLabel(card, text=titulo, font=theme.fuente(15, "bold"),
                     text_color=theme.TXT).pack(anchor="w", padx=16, pady=(12, 6))
        if not filas:
            ctk.CTkLabel(card, text="Sin datos en el período",
                         font=theme.fuente(13), text_color=theme.TXT_MUTED).pack(
                anchor="w", padx=16, pady=(0, 12))
            return
        for etiqueta, valor in filas:
            f = ctk.CTkFrame(card, fg_color="transparent")
            f.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(f, text=etiqueta, anchor="w", font=theme.fuente(14),
                         text_color=theme.TXT).pack(side="left")
            ctk.CTkLabel(f, text=valor, anchor="e", font=theme.fuente(14),
                         text_color=theme.TXT).pack(side="right")
        ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

    # --- Acciones -----------------------------------------------------------

    def _registrar_gasto(self) -> None:
        datos = GastoDialog(self).mostrar()
        if datos is None:
            return
        try:
            gasto_service.crear_gasto(
                datos["tipo"], datos["descripcion"], datos["monto"],
                proveedor_id=datos["proveedor_id"])
        except gasto_service.GastoError as e:
            messagebox.showerror("No se pudo registrar", str(e))
            return
        self._render()
