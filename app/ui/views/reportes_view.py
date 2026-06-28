"""Vista de Reportes + Gastos: período seleccionable, tarjetas de resumen
(con la ganancia neta destacada), desgloses y alta de gastos."""
from datetime import date, timedelta
from decimal import Decimal
from tkinter import messagebox

import customtkinter as ctk

from app.services import reporte_service, gasto_service
from app.ui.dialogs.gasto_dialog import GastoDialog


def _money(v) -> str:
    return f"${Decimal(str(v)):,.2f}"


class ReportesView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Encabezado ---
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Reportes", font=("", 24, "bold")).grid(
            row=0, column=0, sticky="w")
        self.seg_periodo = ctk.CTkSegmentedButton(
            top, values=["Hoy", "Semana", "Mes", "Año"],
            command=lambda _v: self._render())
        self.seg_periodo.set("Mes")
        self.seg_periodo.grid(row=0, column=1, padx=8)
        ctk.CTkButton(top, text="Registrar gasto", width=150,
                      command=self._registrar_gasto).grid(row=0, column=2, padx=4)

        # --- Contenido desplazable ---
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=(6, 16))
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
        return hoy.replace(day=1), hoy  # Mes (por defecto)

    # --- Render -------------------------------------------------------------

    def _render(self) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()
        desde, hasta = self._periodo()

        ctk.CTkLabel(self.scroll, text=f"Del {desde} al {hasta}",
                     text_color="gray").pack(anchor="w", padx=4, pady=(2, 6))

        r = reporte_service.resumen(desde, hasta)
        self._tarjetas(r)

        self._seccion("Gastos por tipo", [
            (g["tipo"], _money(g["total"]))
            for g in reporte_service.gastos_por_tipo(desde, hasta)])
        self._seccion("Ventas por método de pago", [
            (m["metodo"], _money(m["total"]))
            for m in reporte_service.ventas_por_metodo(desde, hasta)])
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
            cont.grid_columnconfigure(i, weight=1)

        neta = r["ganancia_neta"]
        color_neta = "#1e8e3e" if neta >= 0 else "#c0392b"
        tarjetas = [
            ("Ventas", str(r["ventas_cantidad"]), None),
            ("Total vendido", _money(r["total_vendido"]), None),
            ("Costo total", _money(r["costo_total"]), None),
            ("Ganancia bruta", _money(r["ganancia_bruta"]), None),
            ("Gastos", _money(r["gastos_total"]), None),
            ("GANANCIA NETA", _money(neta), color_neta),
        ]
        for idx, (titulo, valor, color) in enumerate(tarjetas):
            card = ctk.CTkFrame(cont)
            card.grid(row=idx // 3, column=idx % 3, padx=6, pady=6, sticky="ew")
            ctk.CTkLabel(card, text=titulo, text_color="gray",
                         anchor="w").pack(anchor="w", padx=12, pady=(10, 0))
            lbl = ctk.CTkLabel(card, text=valor, font=("", 20, "bold"), anchor="w")
            if color:
                lbl.configure(text_color=color)
            lbl.pack(anchor="w", padx=12, pady=(0, 10))

    def _seccion(self, titulo: str, filas: list[tuple[str, str]]) -> None:
        cont = ctk.CTkFrame(self.scroll)
        cont.pack(fill="x", padx=2, pady=6)
        ctk.CTkLabel(cont, text=titulo, font=("", 15, "bold")).pack(
            anchor="w", padx=12, pady=(8, 4))
        if not filas:
            ctk.CTkLabel(cont, text="(sin datos en el período)",
                         text_color="gray").pack(anchor="w", padx=12, pady=(0, 8))
            return
        for etiqueta, valor in filas:
            f = ctk.CTkFrame(cont, fg_color="transparent")
            f.pack(fill="x", padx=12, pady=1)
            ctk.CTkLabel(f, text=etiqueta, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=valor, anchor="e").pack(side="right")
        ctk.CTkLabel(cont, text="").pack(pady=2)  # respiro inferior

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
