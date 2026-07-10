"""Modales para recibir un remito (compra).

ItemRemitoDialog: carga un renglón (cantidad, costo, vencimiento opcional).
RemitoDialog: arma el remito completo escaneando productos y elige condición.

RemitoDialog devuelve un dict listo para compra_service.registrar_compra:
    {"proveedor_id", "items": [ItemCompra...], "nro_remito", "condicion"}
o None si se cancela.
"""
import tkinter as tk
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import customtkinter as ctk

from app.core import formato

from app.models.compra import ItemCompra, CONTADO, CUENTA_CORRIENTE
from app.services import venta_service, proveedor_service, stock_service
from app.ui import theme
from app.ui.autocomplete import AutocompleteBuscador, AutocompleteSimple
from app.ui.dialogs.base import ModalBase
from app.ui.dialogs.buscar_dialog import BuscarProductoDialog

CENTAVOS = Decimal("0.01")
POR_UNIDAD = "Por unidad"
POR_TOTAL = "Por el total"


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
    """Carga un renglón del remito. El costo se puede ingresar por unidad o
    por el total pagado por la cantidad; el sistema calcula el otro."""

    def __init__(self, master, producto):
        super().__init__(master, "Agregar al remito")
        self.producto = producto

        ctk.CTkLabel(self, text=producto.nombre, font=theme.fuente(16, "bold")
                     ).grid(row=0, column=0, columnspan=2, padx=20, pady=(18, 10))

        ctk.CTkLabel(self, text="Cantidad recibida", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_cant = ctk.CTkEntry(self, width=200)
        self.ent_cant.insert(0, "1")
        self.ent_cant.grid(row=1, column=1, padx=(8, 20), pady=6)
        self.ent_cant.bind("<KeyRelease>", self._recalcular)

        ctk.CTkLabel(self, text="Cargar el costo", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=6)
        self.seg_modo = ctk.CTkSegmentedButton(
            self, values=[POR_UNIDAD, POR_TOTAL],
            selected_color=theme.PRIMARY, selected_hover_color=theme.PRIMARY_HOVER,
            command=lambda _v: self._cambiar_modo())
        self.seg_modo.set(POR_UNIDAD)
        self.seg_modo.grid(row=2, column=1, padx=(8, 20), pady=6, sticky="w")

        self.lbl_costo = ctk.CTkLabel(self, text="Costo por unidad", anchor="w")
        self.lbl_costo.grid(row=3, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_costo = ctk.CTkEntry(self, width=200)
        self.ent_costo.insert(0, str(producto.costo_compra))
        self.ent_costo.grid(row=3, column=1, padx=(8, 20), pady=6)
        self.ent_costo.bind("<KeyRelease>", self._recalcular)

        self.lbl_calculo = ctk.CTkLabel(self, text="", anchor="w",
                                        font=theme.fuente(13),
                                        text_color=theme.ACCENT)
        self.lbl_calculo.grid(row=4, column=0, columnspan=2, sticky="w", padx=20)

        ctk.CTkLabel(self, text="Vencimiento (opcional)", anchor="w").grid(
            row=5, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_venc = ctk.CTkEntry(self, width=200, placeholder_text="dd/mm/aaaa")
        self.ent_venc.grid(row=5, column=1, padx=(8, 20), pady=6)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.grid(row=6, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=7, column=0, columnspan=2, pady=(8, 20))
        ctk.CTkButton(cont, text="Cancelar", width=110, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Agregar", width=130, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.after(50, self.ent_cant.focus_set)
        self._recalcular()

    def _por_total(self) -> bool:
        return self.seg_modo.get() == POR_TOTAL

    def _costo_unitario(self) -> Decimal | None:
        """Resuelve el costo unitario según el modo elegido."""
        cant = _num(self.ent_cant.get(), permite_cero=False)
        costo = _num(self.ent_costo.get())
        if cant is None or costo is None:
            return None
        if self._por_total():
            return (costo / cant).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        return costo

    def _cambiar_modo(self) -> None:
        self.lbl_costo.configure(
            text="Costo total pagado" if self._por_total() else "Costo por unidad")
        self._recalcular()

    def _recalcular(self, _event=None) -> None:
        unitario = self._costo_unitario()
        if unitario is None:
            self.lbl_calculo.configure(text="")
            return
        cant = _num(self.ent_cant.get(), permite_cero=False)
        if self._por_total():
            self.lbl_calculo.configure(text=f"→ Cada uno: {formato.moneda(unitario)}")
        else:
            total = (unitario * cant).quantize(CENTAVOS)
            self.lbl_calculo.configure(text=f"→ Total: {formato.moneda(total)}")

    def _confirmar(self) -> None:
        cant = _num(self.ent_cant.get(), permite_cero=False)
        if cant is None:
            self.lbl_error.configure(text="⚠ Cantidad inválida (> 0)")
            return
        unitario = self._costo_unitario()
        if unitario is None:
            self.lbl_error.configure(text="⚠ Costo inválido")
            return
        # Normaliza la fecha al mismo formato ISO que usa "nuevo producto", así
        # los lotes de remito y de alta conviven sin romper la lista de vencim.
        venc_txt = self.ent_venc.get().strip()
        venc = None
        if venc_txt:
            venc = stock_service.parse_fecha(venc_txt)
            if venc is None:
                self.lbl_error.configure(
                    text="⚠ Fecha de vencimiento inválida (dd/mm/aaaa)")
                return
        self._aceptar(ItemCompra(
            producto_id=self.producto.id, cantidad=cant,
            costo_unitario=unitario, fecha_vencimiento=venc))


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
        nombres = list(self._mapa_prov.keys())
        # Campo con autocompletado: filtra proveedores mientras se escribe.
        self.ent_prov = ctk.CTkEntry(
            cab, width=220,
            placeholder_text="Buscá un proveedor…" if nombres else "(sin proveedores)")
        if nombres:
            self.ent_prov.insert(0, nombres[0])
        self.ent_prov.grid(row=0, column=1, padx=8, pady=8)
        self._auto_prov = AutocompleteSimple(self.ent_prov, self, nombres)
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
        ctk.CTkButton(barra, text="Agregar", width=110, height=40,
                      command=lambda: self._auto_prod.enter()).grid(row=0, column=1)
        # Autocompletado de productos: sugiere por nombre mientras se escribe;
        # el Enter "directo" busca por código exacto (pistolita).
        self._auto_prod = AutocompleteBuscador(
            self.ent_scan, self,
            on_seleccionar=self._agregar_producto,
            on_enter_directo=self._on_scan,
            buscar_codigo_fn=venta_service.buscar_por_codigo)

        # Encabezado de columnas. La columna "Producto" (1) se estira; el resto
        # queda a ancho fijo, así la columna del ✕ siempre está pegada a la derecha.
        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 0))
        cabecera.grid_columnconfigure(1, weight=1)
        for col, (txt, w) in enumerate(
                [("Cant.", 60), ("Producto", 180), ("Costo unit.", 110),
                 ("Subtotal", 100), ("", 40)]):
            ctk.CTkLabel(cabecera, text=txt, width=w, anchor="w",
                         font=theme.fuente(12, "bold"),
                         text_color=theme.TXT_MUTED).grid(
                row=0, column=col, padx=4, sticky="ew")

        # Lista de renglones.
        self.lista = ctk.CTkScrollableFrame(self, width=600, height=220,
                                            fg_color=theme.CARD_BG, corner_radius=12)
        self.lista.grid(row=3, column=0, sticky="nsew", padx=16, pady=6)
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Pie: total + acciones.
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=4, column=0, sticky="ew", padx=16, pady=(6, 16))
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
        """Enter 'directo': busca por código exacto o, si no, por nombre."""
        texto = self.ent_scan.get().strip()
        if not texto:
            return
        prod = venta_service.buscar_por_codigo(texto)
        if prod is None:
            resultados = venta_service.buscar_por_nombre(texto)
            if not resultados:
                self.ent_scan.delete(0, "end")
                self.lbl_total.configure(text=f"Sin resultados para '{texto}'")
                return
            prod = BuscarProductoDialog(self, resultados).mostrar()
            if prod is None:
                self.ent_scan.focus_set()
                return
        self._agregar_producto(prod)

    def _agregar_producto(self, prod) -> None:
        """Abre el modal de renglón para el producto elegido y lo agrega."""
        self.ent_scan.delete(0, "end")
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
            venc = f"  · vence {item.fecha_vencimiento}" if item.fecha_vencimiento else ""
            fila = ctk.CTkFrame(self.lista, fg_color="transparent")
            fila.pack(fill="x", padx=8, pady=2)
            fila.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(fila, text=formato.numero(item.cantidad), width=60,
                         anchor="w").grid(row=0, column=0, padx=4)
            ctk.CTkLabel(fila, text=f"{nombre}{venc}", width=180,
                         anchor="w").grid(row=0, column=1, padx=4, sticky="ew")
            ctk.CTkLabel(fila, text=f"{formato.moneda(item.costo_unitario)}", width=110,
                         anchor="w").grid(row=0, column=2, padx=4)
            ctk.CTkLabel(fila, text=f"{formato.moneda(item.subtotal)}", width=100,
                         anchor="w").grid(row=0, column=3, padx=4)
            ctk.CTkButton(fila, text="✕", width=36, fg_color="#b33",
                          hover_color="#922",
                          command=lambda idx=i: self._quitar(idx)).grid(
                row=0, column=4, padx=4)
        self.lbl_total.configure(text=f"TOTAL: {formato.moneda(total)}")

    # --- Confirmación -------------------------------------------------------

    def _confirmar(self) -> None:
        if not self._mapa_prov:
            self.lbl_total.configure(text="⚠ Primero creá un proveedor")
            return
        proveedor_id = self._mapa_prov.get(self.ent_prov.get().strip())
        if proveedor_id is None:
            self.lbl_total.configure(text="⚠ Elegí un proveedor válido de la lista")
            return
        if not self._items:
            self.lbl_total.configure(text="⚠ El remito no tiene productos")
            return
        condicion = (CUENTA_CORRIENTE if self.seg_cond.get() == "Cuenta corriente"
                     else CONTADO)
        self._aceptar({
            "proveedor_id": proveedor_id,
            "items": [it for it, _ in self._items],
            "nro_remito": self.ent_remito.get().strip() or None,
            "condicion": condicion,
        })
