"""Modales para recibir un remito (compra).

ItemRemitoDialog: carga un renglón (cantidad, costo, vencimiento opcional).
RemitoDialog: arma el remito completo escaneando productos y elige condición.

RemitoDialog devuelve un dict listo para compra_service.registrar_compra:
    {"proveedor_id", "items": [ItemCompra...], "nro_remito", "condicion"}
o None si se cancela.
"""
import tkinter as tk
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.models.compra import ItemCompra, CONTADO, CUENTA_CORRIENTE
from app.services import venta_service, proveedor_service
from app.ui.dialogs.base import ModalBase
from app.ui.dialogs.buscar_dialog import BuscarProductoDialog


def _num(texto: str, permite_cero: bool = True) -> Decimal | None:
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return Decimal("0") if permite_cero else None
    try:
        v = Decimal(texto)
    except InvalidOperation:
        return None
    if v < 0 or (v == 0 and not permite_cero):
        return None
    return v


class ItemRemitoDialog(ModalBase):
    """Carga un renglón del remito para un producto ya identificado."""

    def __init__(self, master, producto):
        super().__init__(master, "Agregar al remito")
        self.producto = producto

        ctk.CTkLabel(self, text=producto.nombre, font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(18, 10))

        ctk.CTkLabel(self, text="Cantidad recibida", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_cant = ctk.CTkEntry(self, width=180)
        self.ent_cant.insert(0, "1")
        self.ent_cant.grid(row=1, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="Costo unitario", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_costo = ctk.CTkEntry(self, width=180)
        self.ent_costo.insert(0, str(producto.costo_compra))
        self.ent_costo.grid(row=2, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="Vencimiento (opcional)", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_venc = ctk.CTkEntry(self, width=180, placeholder_text="AAAA-MM-DD")
        self.ent_venc.grid(row=3, column=1, padx=(8, 20), pady=6)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
        self.lbl_error.grid(row=4, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=5, column=0, columnspan=2, pady=(8, 20))
        ctk.CTkButton(cont, text="Cancelar", width=110, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Agregar", width=130,
                      command=self._confirmar).pack(side="left", padx=8)

        self.after(50, self.ent_cant.focus_set)

    def _confirmar(self) -> None:
        cant = _num(self.ent_cant.get(), permite_cero=False)
        if cant is None:
            self.lbl_error.configure(text="⚠ Cantidad inválida (> 0)")
            return
        costo = _num(self.ent_costo.get())
        if costo is None:
            self.lbl_error.configure(text="⚠ Costo inválido")
            return
        venc = self.ent_venc.get().strip() or None
        self._aceptar(ItemCompra(
            producto_id=self.producto.id, cantidad=cant,
            costo_unitario=costo, fecha_vencimiento=venc))


class RemitoDialog(ModalBase):
    def __init__(self, master):
        super().__init__(master, "Recibir remito")
        self._items: list[tuple[ItemCompra, str]] = []
        self._proveedores = proveedor_service.listar_activos()
        self._mapa_prov = {p.nombre: p.id for p in self._proveedores}

        # Encabezado: proveedor, nro remito, condición.
        cab = ctk.CTkFrame(self)
        cab.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        ctk.CTkLabel(cab, text="Proveedor").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        nombres = list(self._mapa_prov.keys()) or ["(sin proveedores)"]
        self.opt_prov = ctk.CTkOptionMenu(cab, values=nombres, width=220)
        self.opt_prov.set(nombres[0])
        self.opt_prov.grid(row=0, column=1, padx=8, pady=8)
        ctk.CTkLabel(cab, text="N° remito").grid(row=0, column=2, padx=8, pady=8)
        self.ent_remito = ctk.CTkEntry(cab, width=140)
        self.ent_remito.grid(row=0, column=3, padx=8, pady=8)
        self.seg_cond = ctk.CTkSegmentedButton(
            cab, values=["Contado", "Cuenta corriente"])
        self.seg_cond.set("Contado")
        self.seg_cond.grid(row=1, column=0, columnspan=4, padx=8, pady=(0, 8))

        # Escaneo para agregar productos.
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        barra.grid_columnconfigure(0, weight=1)
        self.ent_scan = ctk.CTkEntry(
            barra, placeholder_text="Escaneá o buscá un producto y Enter...",
            height=40)
        self.ent_scan.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.ent_scan.bind("<Return>", self._on_scan)
        ctk.CTkButton(barra, text="Agregar", width=110, height=40,
                      command=self._on_scan).grid(row=0, column=1)

        # Lista de renglones.
        self.lista = ctk.CTkScrollableFrame(self, width=560, height=240)
        self.lista.grid(row=2, column=0, sticky="nsew", padx=16, pady=6)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Pie: total + acciones.
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 16))
        pie.grid_columnconfigure(0, weight=1)
        self.lbl_total = ctk.CTkLabel(pie, text="TOTAL: $0.00",
                                      font=("", 20, "bold"))
        self.lbl_total.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(pie, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).grid(row=0, column=1, padx=6)
        ctk.CTkButton(pie, text="Confirmar remito", width=170,
                      command=self._confirmar).grid(row=0, column=2, padx=6)

        self.after(80, self.ent_scan.focus_set)
        self._refrescar()

    # --- Agregado de ítems --------------------------------------------------

    def _on_scan(self, _event=None) -> None:
        texto = self.ent_scan.get().strip()
        self.ent_scan.delete(0, "end")
        if not texto:
            return
        prod = venta_service.buscar_por_codigo(texto)
        if prod is None:
            resultados = venta_service.buscar_por_nombre(texto)
            if not resultados:
                self.lbl_total.configure(text=f"Sin resultados para '{texto}'")
                return
            prod = BuscarProductoDialog(self, resultados).mostrar()
            if prod is None:
                self.ent_scan.focus_set()
                return
        item = ItemRemitoDialog(self, prod).mostrar()
        if item is not None:
            self._items.append((item, prod.nombre))
            self._refrescar()
        self.ent_scan.focus_set()

    def _quitar(self, indice: int) -> None:
        del self._items[indice]
        self._refrescar()

    def _refrescar(self) -> None:
        for w in self.lista.winfo_children():
            w.destroy()
        total = Decimal("0.00")
        for i, (item, nombre) in enumerate(self._items):
            total += item.subtotal
            fila = ctk.CTkFrame(self.lista, fg_color="transparent")
            fila.grid(row=i, column=0, sticky="ew", pady=2)
            fila.grid_columnconfigure(0, weight=1)
            venc = f"  · vence {item.fecha_vencimiento}" if item.fecha_vencimiento else ""
            ctk.CTkLabel(
                fila, anchor="w",
                text=f"{item.cantidad} x {nombre} @ ${item.costo_unitario}{venc}"
            ).grid(row=0, column=0, sticky="w", padx=4)
            ctk.CTkLabel(fila, text=f"${item.subtotal}", width=110).grid(
                row=0, column=1, padx=4)
            ctk.CTkButton(fila, text="✕", width=36, fg_color="#b33",
                          hover_color="#922",
                          command=lambda idx=i: self._quitar(idx)).grid(
                row=0, column=2, padx=4)
        self.lbl_total.configure(text=f"TOTAL: ${total:,.2f}")

    # --- Confirmación -------------------------------------------------------

    def _confirmar(self) -> None:
        if not self._mapa_prov:
            self.lbl_total.configure(text="⚠ Primero creá un proveedor")
            return
        if not self._items:
            self.lbl_total.configure(text="⚠ El remito no tiene productos")
            return
        condicion = (CUENTA_CORRIENTE if self.seg_cond.get() == "Cuenta corriente"
                     else CONTADO)
        self._aceptar({
            "proveedor_id": self._mapa_prov.get(self.opt_prov.get()),
            "items": [it for it, _ in self._items],
            "nro_remito": self.ent_remito.get().strip() or None,
            "condicion": condicion,
        })
