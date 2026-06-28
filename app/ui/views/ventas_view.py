"""Pantalla principal del POS (caja).

Flujo:
  - La 'pistolita' escribe en el campo de escaneo; al recibir Enter se busca
    el producto y se agrega al carrito automáticamente.
  - Si el código no existe, se busca por nombre y se ofrece elegir.
  - Productos pesables abren el modal de peso.
  - El botón Cobrar (o F12) abre el modal de cobro y registra la venta.
"""
from decimal import Decimal
from tkinter import messagebox

import customtkinter as ctk

from app.models.carrito import Carrito
from app.services import venta_service, cliente_service
from app.ui.dialogs.peso_dialog import PesoDialog
from app.ui.dialogs.cobro_dialog import CobroDialog
from app.ui.dialogs.buscar_dialog import BuscarProductoDialog


def _money(d: Decimal) -> str:
    return f"${d:,.2f}"


class VentasView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.carrito = Carrito()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- Barra de escaneo ---
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        top.grid_columnconfigure(0, weight=1)
        self.entry_scan = ctk.CTkEntry(
            top, placeholder_text="Escaneá un código o escribí para buscar...",
            font=("", 18), height=44)
        self.entry_scan.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=8)
        self.entry_scan.bind("<Return>", self._on_scan)
        ctk.CTkButton(top, text="Agregar", width=110, height=44,
                      command=self._on_scan).grid(row=0, column=1, pady=8)

        # --- Encabezado de la tabla ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=12)
        for col, (txt, w) in enumerate(
                [("Producto", 320), ("Cant.", 90), ("Precio", 120),
                 ("Subtotal", 120), ("", 50)]):
            header.grid_columnconfigure(col, weight=1 if col == 0 else 0)
            ctk.CTkLabel(header, text=txt, width=w, anchor="w",
                         font=("", 13, "bold")).grid(row=0, column=col, padx=4)

        # --- Lista de ítems ---
        self.tabla = ctk.CTkScrollableFrame(self)
        self.tabla.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        self.tabla.grid_columnconfigure(0, weight=1)

        # --- Pie: total + acciones ---
        pie = ctk.CTkFrame(self)
        pie.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 12))
        pie.grid_columnconfigure(0, weight=1)

        self.lbl_total = ctk.CTkLabel(pie, text="TOTAL: $0.00",
                                      font=("", 28, "bold"))
        self.lbl_total.grid(row=0, column=0, sticky="w", padx=12, pady=12)

        ctk.CTkButton(pie, text="Cancelar venta", width=140, height=48,
                      fg_color="gray", command=self._cancelar_venta).grid(
            row=0, column=1, padx=6, pady=12)
        ctk.CTkButton(pie, text="COBRAR (F12)", width=200, height=48,
                      font=("", 18, "bold"), command=self._cobrar).grid(
            row=0, column=2, padx=6, pady=12)

        # Atajos
        self.winfo_toplevel().bind("<F12>", lambda _e: self._cobrar())

        self._refrescar()
        self.after(100, self.entry_scan.focus_set)

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

        for i, item in enumerate(self.carrito.items):
            fila = ctk.CTkFrame(self.tabla, fg_color="transparent")
            fila.grid(row=i, column=0, sticky="ew", pady=2)
            fila.grid_columnconfigure(0, weight=1)

            cant = (f"{item.cantidad} kg" if item.es_pesable
                    else f"{int(item.cantidad)}")
            ctk.CTkLabel(fila, text=item.descripcion, anchor="w",
                         width=320).grid(row=0, column=0, padx=4, sticky="w")
            ctk.CTkLabel(fila, text=cant, width=90).grid(row=0, column=1, padx=4)
            ctk.CTkLabel(fila, text=_money(item.precio_unitario),
                         width=120).grid(row=0, column=2, padx=4)
            ctk.CTkLabel(fila, text=_money(item.subtotal),
                         width=120).grid(row=0, column=3, padx=4)
            ctk.CTkButton(fila, text="✕", width=40, fg_color="#b33",
                          hover_color="#922",
                          command=lambda idx=i: self._quitar(idx)).grid(
                row=0, column=4, padx=4)

        self.lbl_total.configure(text=f"TOTAL: {_money(self.carrito.total)}")

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
