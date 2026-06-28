"""Pantalla principal del POS (caja), rediseñada.

Layout: a la izquierda el escaneo + el carrito (tarjeta con filas + badges de
cantidad); a la derecha el panel de cobro con el total destacado.

Flujo (sin cambios):
  - La 'pistolita' escribe en el campo de escaneo; al Enter busca y agrega.
  - Si el código no existe, busca por nombre y ofrece elegir.
  - Productos pesables abren el modal de peso.
  - Cobrar (o F12) abre el modal de cobro y registra la venta.
"""
from decimal import Decimal
from tkinter import messagebox

import customtkinter as ctk

from app.models.carrito import Carrito
from app.services import venta_service, cliente_service
from app.ui import theme
from app.ui.dialogs.peso_dialog import PesoDialog
from app.ui.dialogs.cobro_dialog import CobroDialog
from app.ui.dialogs.buscar_dialog import BuscarProductoDialog
from app.ui.dialogs.consulta_precio_dialog import ConsultaPrecioDialog


def _money(d: Decimal) -> str:
    return f"${Decimal(str(d)):,.2f}"


class VentasView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.carrito = Carrito()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=250)
        self.grid_rowconfigure(1, weight=1)

        # --- Encabezado ---
        ctk.CTkLabel(self, text="Caja", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(18, 10))

        # --- Columna izquierda: escaneo + carrito ---
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 18))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        scanbar = ctk.CTkFrame(main, fg_color="transparent")
        scanbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        scanbar.grid_columnconfigure(0, weight=1)
        self.entry_scan = ctk.CTkEntry(
            scanbar, placeholder_text="Escaneá un código o buscá un producto…",
            font=theme.fuente(16), height=48, corner_radius=10)
        self.entry_scan.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry_scan.bind("<Return>", self._on_scan)
        ctk.CTkButton(scanbar, text="Consultar precio (F2)", width=170,
                      height=48, corner_radius=10, font=theme.fuente(14),
                      fg_color="transparent", text_color=theme.ACCENT,
                      border_width=1, border_color=theme.GHOST,
                      hover_color=theme.GHOST,
                      command=self._consultar_precio).grid(row=0, column=1)

        self.tabla = ctk.CTkScrollableFrame(main, fg_color=theme.CARD_BG,
                                            corner_radius=12)
        self.tabla.grid(row=1, column=0, sticky="nsew")
        self.tabla.grid_columnconfigure(0, weight=1)

        # --- Columna derecha: panel de cobro ---
        panel = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=12)
        panel.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 18))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(panel, text="Total a cobrar", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 0))
        self.lbl_total = ctk.CTkLabel(panel, text="$0,00",
                                      font=theme.fuente(32, "bold"),
                                      text_color=theme.ACCENT)
        self.lbl_total.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 2))
        self.lbl_count = ctk.CTkLabel(panel, text="0 productos",
                                      font=theme.fuente(13),
                                      text_color=theme.TXT_MUTED)
        self.lbl_count.grid(row=2, column=0, sticky="w", padx=18)

        botonera = ctk.CTkFrame(panel, fg_color="transparent")
        botonera.grid(row=4, column=0, sticky="ew", padx=16, pady=16)
        botonera.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(botonera, text="Cobrar", height=50, corner_radius=10,
                      font=theme.fuente(18, "bold"), fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._cobrar).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(botonera, text="Cancelar venta", height=38,
                      corner_radius=10, font=theme.fuente(13),
                      fg_color="transparent", text_color=theme.TXT_MUTED,
                      hover_color=theme.GHOST,
                      command=self._cancelar_venta).grid(
            row=1, column=0, sticky="ew", pady=(8, 0))

        self.winfo_toplevel().bind("<F12>", lambda _e: self._cobrar())
        self.winfo_toplevel().bind("<F2>", lambda _e: self._consultar_precio())
        self._refrescar()
        self.after(120, self.entry_scan.focus_set)

    # --- Escaneo / agregado -------------------------------------------------

    def _on_scan(self, _event=None) -> None:
        texto = self.entry_scan.get().strip()
        self.entry_scan.delete(0, "end")
        if not texto:
            return
        prod = venta_service.buscar_por_codigo(texto)
        if prod is None:
            resultados = venta_service.buscar_por_nombre(texto)
            if not resultados:
                messagebox.showwarning("Sin resultados",
                                       f"No se encontró '{texto}'.")
                self.entry_scan.focus_set()
                return
            prod = BuscarProductoDialog(self, resultados).mostrar()
            if prod is None:
                self.entry_scan.focus_set()
                return
        self._agregar(prod)
        self.entry_scan.focus_set()

    def _consultar_precio(self) -> None:
        """Abre la consulta de precio. No toca el carrito."""
        ConsultaPrecioDialog(self).mostrar()
        self.entry_scan.focus_set()

    def _agregar(self, producto) -> None:
        if producto.es_pesable:
            kg = PesoDialog(self, producto).mostrar()
            if kg is None:
                return
            cantidad = kg
        else:
            cantidad = Decimal("1")
        self.carrito.agregar(producto, cantidad)
        self._refrescar()

    # --- Render del carrito -------------------------------------------------

    def _refrescar(self) -> None:
        for w in self.tabla.winfo_children():
            w.destroy()

        if self.carrito.esta_vacio():
            ctk.CTkLabel(self.tabla, text="El carrito está vacío.\nEscaneá un "
                         "producto para empezar.", font=theme.fuente(14),
                         text_color=theme.TXT_MUTED, justify="center").pack(
                pady=40)
        else:
            for i, item in enumerate(self.carrito.items):
                self._fila_item(i, item)

        total = self.carrito.total
        n = len(self.carrito.items)
        self.lbl_total.configure(text=_money(total))
        self.lbl_count.configure(text=f"{n} producto{'s' if n != 1 else ''}")

    def _fila_item(self, indice: int, item) -> None:
        fila = ctk.CTkFrame(self.tabla, fg_color="transparent")
        fila.pack(fill="x", padx=8, pady=4)

        if item.es_pesable:
            badge_txt, bg, fg = f"{item.cantidad}\nkg", theme.BADGE_KG_BG, theme.BADGE_KG_TXT
            unidad = f"{_money(item.precio_unitario)} / kg"
        else:
            badge_txt, bg, fg = f"{int(item.cantidad)}", theme.BADGE_BG, theme.BADGE_TXT
            unidad = f"{_money(item.precio_unitario)} c/u"

        ctk.CTkLabel(fila, text=badge_txt, width=38, height=38, corner_radius=8,
                     fg_color=bg, text_color=fg,
                     font=theme.fuente(13, "bold")).pack(side="left")

        medio = ctk.CTkFrame(fila, fg_color="transparent")
        medio.pack(side="left", fill="x", expand=True, padx=12)
        ctk.CTkLabel(medio, text=item.descripcion, anchor="w",
                     font=theme.fuente(15), text_color=theme.TXT).pack(
            anchor="w")
        ctk.CTkLabel(medio, text=unidad, anchor="w", font=theme.fuente(12),
                     text_color=theme.TXT_MUTED).pack(anchor="w")

        ctk.CTkButton(fila, text="✕", width=30, height=30, corner_radius=8,
                      fg_color="transparent", text_color=theme.TXT_MUTED,
                      hover_color=theme.ROJO,
                      command=lambda idx=indice: self._quitar(idx)).pack(
            side="right")
        ctk.CTkLabel(fila, text=_money(item.subtotal), width=90,
                     anchor="e", font=theme.fuente(15, "bold"),
                     text_color=theme.TXT).pack(side="right", padx=(0, 6))

    def _quitar(self, indice: int) -> None:
        self.carrito.quitar(indice)
        self._refrescar()
        self.entry_scan.focus_set()

    # --- Cobro --------------------------------------------------------------

    def _cobrar(self) -> None:
        if self.carrito.esta_vacio():
            messagebox.showinfo("Carrito vacío", "Agregá productos antes de cobrar.")
            return
        clientes = cliente_service.listar_activos()
        resultado = CobroDialog(self, self.carrito.total, clientes).mostrar()
        if resultado is None:
            self.entry_scan.focus_set()
            return
        pagos, cliente_id = resultado
        try:
            venta_service.registrar_venta(self.carrito, pagos, cliente_id)
        except venta_service.VentaError as e:
            messagebox.showerror("No se pudo cobrar", str(e))
            return
        messagebox.showinfo("Venta registrada",
                            f"Cobro exitoso por {_money(self.carrito.total)}.")
        self.carrito.vaciar()
        self._refrescar()
        self.entry_scan.focus_set()

    def _cancelar_venta(self) -> None:
        if self.carrito.esta_vacio():
            return
        if messagebox.askyesno("Cancelar venta", "¿Vaciar el carrito actual?"):
            self.carrito.vaciar()
            self._refrescar()
        self.entry_scan.focus_set()
