"""Vista de Carne: manejo de reses por despiece.

Dos pantallas apiladas:
  - Lista de reses (media reses) con su estado y ganancia.
  - Detalle de una res: sus piezas (Espalda/Pierna) y, para la pieza elegida, la
    tabla de cortes (como la planilla) con totales y ganancia en vivo. Al
    confirmar una pieza, sus cortes cargan stock a la sección Stock.
"""
from decimal import Decimal

import customtkinter as ctk

from app.core import formato

from app.models.res import ABIERTA, CUENTA_CORRIENTE
from app.services import despiece_service as ds
from app.ui import theme
from app.ui.toast import mostrar_toast
from app.ui.dialogs import notificar
from app.ui.dialogs.res_dialog import ResDialog
from app.ui.dialogs.pieza_dialog import PiezaDialog
from app.ui.dialogs.corte_dialog import CorteDialog


def _money(v) -> str:
    return formato.moneda(v)


def _kg(v) -> str:
    return formato.kg(v)


class CarneView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._pantalla = "lista"
        self._res_id = None
        self._pieza_id = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.pant_lista = ctk.CTkFrame(self, fg_color="transparent")
        self.pant_detalle = ctk.CTkFrame(self, fg_color="transparent")
        self.pant_lista.grid(row=0, column=0, sticky="nsew")
        self.pant_detalle.grid(row=0, column=0, sticky="nsew")

        self._build_lista()
        self._build_detalle()
        self.pant_lista.tkraise()

    def al_mostrar(self) -> None:
        if self._pantalla == "detalle" and self._res_id:
            self._recargar_detalle()
        else:
            self._ir_a_lista()

    # ======================================================================
    #  Pantalla: lista de reses
    # ======================================================================

    def _build_lista(self) -> None:
        p = self.pant_lista
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(p, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text="Carne", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="＋  Nueva res", height=38, width=170,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._nueva_res).grid(row=0, column=1)

        self.lista_reses = ctk.CTkScrollableFrame(p, fg_color="transparent")
        self.lista_reses.grid(row=1, column=0, sticky="nsew", padx=14, pady=(6, 16))
        self.lista_reses.grid_columnconfigure(0, weight=1)

    def _ir_a_lista(self) -> None:
        self._pantalla = "lista"
        self._render_lista()
        self.pant_lista.tkraise()

    def _render_lista(self) -> None:
        for w in self.lista_reses.winfo_children():
            w.destroy()
        reses = ds.listar_reses()
        if not reses:
            ctk.CTkLabel(
                self.lista_reses,
                text="Todavía no cargaste ninguna res.\n"
                     "Tocá «Nueva res» para empezar.",
                font=theme.fuente(15), text_color=theme.TXT_MUTED,
                justify="center").pack(pady=48)
            return
        for res in reses:
            self._tarjeta_res(res)

    def _tarjeta_res(self, res) -> None:
        resumen = ds.resumen_res(res.id)
        card = ctk.CTkFrame(self.lista_reses, fg_color=theme.CARD_BG, corner_radius=12)
        card.pack(fill="x", padx=6, pady=5)
        card.grid_columnconfigure(0, weight=1)

        izq = ctk.CTkFrame(card, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="w", padx=16, pady=12)
        cab = ctk.CTkFrame(izq, fg_color="transparent")
        cab.pack(anchor="w")
        ctk.CTkLabel(cab, text=res.descripcion, font=theme.fuente(16, "bold"),
                     text_color=theme.TXT).pack(side="left")
        self._badge_estado(cab, res.estado).pack(side="left", padx=10)
        ctk.CTkLabel(
            izq,
            text=f"{res.fecha[:10]}   ·   {_kg(res.peso_total)} × {_money(res.costo_por_kg)}"
                 f"   ·   costo {_money(res.costo_total)}",
            font=theme.fuente(13), text_color=theme.TXT_MUTED).pack(anchor="w",
                                                                    pady=(4, 0))

        med = ctk.CTkFrame(card, fg_color="transparent")
        med.grid(row=0, column=1, padx=10)
        ctk.CTkLabel(med, text="Valor venta", font=theme.fuente(11),
                     text_color=theme.TXT_MUTED).pack()
        ctk.CTkLabel(med, text=_money(resumen["venta_total"]),
                     font=theme.fuente(15, "bold"), text_color=theme.TXT).pack()

        gan = ctk.CTkFrame(card, fg_color="transparent")
        gan.grid(row=0, column=2, padx=10)
        ctk.CTkLabel(gan, text="Ganancia", font=theme.fuente(11),
                     text_color=theme.TXT_MUTED).pack()
        g = resumen["ganancia_piezas"]
        ctk.CTkLabel(gan, text=_money(g), font=theme.fuente(15, "bold"),
                     text_color=theme.VERDE if g >= 0 else theme.ROJO).pack()

        acc = ctk.CTkFrame(card, fg_color="transparent")
        acc.grid(row=0, column=3, padx=(6, 16))
        ctk.CTkButton(acc, text="Abrir  →", width=100, height=36, corner_radius=8,
                      font=theme.fuente(14), fg_color="transparent",
                      text_color=theme.ACCENT, border_width=1,
                      border_color=theme.GHOST, hover_color=theme.GHOST,
                      command=lambda rid=res.id: self._abrir_res(rid)).pack(
            side="left", padx=(0, 6))
        ctk.CTkButton(acc, text="🗑", width=40, height=36, corner_radius=8,
                      font=theme.fuente(15), fg_color="transparent",
                      text_color=theme.ROJO, border_width=1,
                      border_color=theme.GHOST, hover_color=theme.GHOST,
                      command=lambda r=res: self._eliminar_res(r)).pack(side="left")

    def _badge_estado(self, parent, estado):
        abierta = estado == ABIERTA
        return ctk.CTkLabel(
            parent, text=("Abierta" if abierta else "Cerrada"),
            font=theme.fuente(11, "bold"), corner_radius=8,
            fg_color=theme.VERDE_BG if abierta else theme.GHOST,
            text_color=theme.VERDE if abierta else theme.TXT_MUTED,
            width=64, height=22)

    # ======================================================================
    #  Pantalla: detalle de una res (piezas + cortes)
    # ======================================================================

    def _build_detalle(self) -> None:
        p = self.pant_detalle
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(4, weight=1)

        # Barra superior: volver + título + estado.
        top = ctk.CTkFrame(p, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(top, text="←  Volver", width=100, height=34, corner_radius=8,
                      font=theme.fuente(14), fg_color="transparent",
                      text_color=theme.ACCENT, border_width=1,
                      border_color=theme.GHOST, hover_color=theme.GHOST,
                      command=self._ir_a_lista).grid(row=0, column=0)
        self.lbl_res_titulo = ctk.CTkLabel(top, text="", font=theme.fuente(20, "bold"),
                                           text_color=theme.TXT)
        self.lbl_res_titulo.grid(row=0, column=1, sticky="w", padx=14)

        # Tarjeta con datos de la res + resumen + acciones.
        self.card_res = ctk.CTkFrame(p, fg_color=theme.CARD_BG, corner_radius=12)
        self.card_res.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 8))
        self.card_res.grid_columnconfigure(4, weight=1)
        self.lbl_res_datos = ctk.CTkLabel(self.card_res, text="", anchor="w",
                                          font=theme.fuente(13),
                                          text_color=theme.TXT_MUTED)
        self.lbl_res_datos.grid(row=0, column=0, columnspan=5, sticky="w",
                                padx=16, pady=(12, 4))
        self.lbl_res_resumen = ctk.CTkLabel(self.card_res, text="", anchor="w",
                                            font=theme.fuente(14),
                                            text_color=theme.TXT)
        self.lbl_res_resumen.grid(row=1, column=0, columnspan=4, sticky="w",
                                  padx=16, pady=(0, 12))
        self.btn_nueva_pieza = ctk.CTkButton(
            self.card_res, text="＋  Nueva pieza", width=150, height=34,
            corner_radius=8, font=theme.fuente(14), fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER, command=self._nueva_pieza)
        self.btn_nueva_pieza.grid(row=1, column=4, padx=8)
        self.btn_cerrar_res = ctk.CTkButton(
            self.card_res, text="Cerrar res", width=110, height=34, corner_radius=8,
            font=theme.fuente(14), fg_color="transparent", text_color=theme.ACCENT,
            border_width=1, border_color=theme.GHOST, hover_color=theme.GHOST,
            command=self._cerrar_res)
        self.btn_cerrar_res.grid(row=1, column=5, padx=(0, 14))

        # Fila de piezas (pills).
        self.fila_piezas = ctk.CTkFrame(p, fg_color="transparent")
        self.fila_piezas.grid(row=2, column=0, sticky="ew", padx=20, pady=(2, 6))

        # Encabezado de la tabla de cortes. Anchos FIJOS (sin weight) para que
        # coincidan exactamente con las filas al agrandar la ventana; el espacio
        # sobrante lo absorbe una columna final vacía.
        header = ctk.CTkFrame(p, fg_color="transparent")
        header.grid(row=3, column=0, sticky="ew", padx=28)
        header.grid_columnconfigure(6, weight=1)
        for col, (txt, w) in enumerate(
                [("Corte", 240), ("Kg", 90), ("Precio/kg", 110),
                 ("% del total", 90), ("Total", 120), ("", 200)]):
            ctk.CTkLabel(header, text=txt, width=w,
                         anchor="e" if txt in ("Kg", "Precio/kg", "% del total",
                                               "Total") else "w",
                         font=theme.fuente(12, "bold"),
                         text_color=theme.TXT_MUTED).grid(row=0, column=col, padx=4,
                                                          sticky="ew")

        # Tabla de cortes.
        self.tabla_cortes = ctk.CTkScrollableFrame(p, fg_color=theme.CARD_BG,
                                                   corner_radius=12)
        self.tabla_cortes.grid(row=4, column=0, sticky="nsew", padx=20, pady=(6, 6))
        self.tabla_cortes.grid_columnconfigure(0, weight=1)

        # Pie: totales de la pieza + acciones.
        pie = ctk.CTkFrame(p, fg_color=theme.CARD_BG, corner_radius=12)
        pie.grid(row=5, column=0, sticky="ew", padx=20, pady=(2, 16))
        pie.grid_columnconfigure(3, weight=1)
        self.lbl_pie_venta = ctk.CTkLabel(pie, text="Valor venta —",
                                          font=theme.fuente(14), text_color=theme.TXT)
        self.lbl_pie_venta.grid(row=0, column=0, padx=(16, 18), pady=12)
        self.lbl_pie_costo = ctk.CTkLabel(pie, text="Costo —", font=theme.fuente(14),
                                          text_color=theme.TXT_MUTED)
        self.lbl_pie_costo.grid(row=0, column=1, padx=18, pady=12)
        self.lbl_pie_gan = ctk.CTkLabel(pie, text="Ganancia —",
                                        font=theme.fuente(16, "bold"),
                                        text_color=theme.VERDE)
        self.lbl_pie_gan.grid(row=0, column=2, padx=18, pady=12)
        self.btn_agregar_corte = ctk.CTkButton(
            pie, text="＋  Agregar corte", width=160, height=36, corner_radius=8,
            font=theme.fuente(14), fg_color="transparent", text_color=theme.ACCENT,
            border_width=1, border_color=theme.GHOST, hover_color=theme.GHOST,
            command=self._agregar_corte)
        self.btn_agregar_corte.grid(row=0, column=4, padx=6)
        self.btn_confirmar = ctk.CTkButton(
            pie, text="Confirmar pieza", width=170, height=36, corner_radius=8,
            font=theme.fuente(14, "bold"), fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER, command=self._confirmar_pieza)
        self.btn_confirmar.grid(row=0, column=5, padx=(6, 16))

    # --- Navegación / carga -------------------------------------------------

    def _abrir_res(self, res_id: str) -> None:
        self._res_id = res_id
        self._pieza_id = None
        self._pantalla = "detalle"
        self._recargar_detalle()
        self.pant_detalle.tkraise()

    def _recargar_detalle(self) -> None:
        res = ds.obtener_res(self._res_id)
        if res is None:
            self._ir_a_lista()
            return
        abierta = res.estado == ABIERTA
        self.lbl_res_titulo.configure(text=res.descripcion)
        self.lbl_res_datos.configure(
            text=f"{res.fecha[:10]}   ·   {_kg(res.peso_total)} × {_money(res.costo_por_kg)}"
                 f"   ·   costo total {_money(res.costo_total)}   ·   "
                 f"{'Abierta' if abierta else 'Cerrada'}")
        rr = ds.resumen_res(self._res_id)
        self.lbl_res_resumen.configure(
            text=f"Valor venta {_money(rr['venta_total'])}   ·   "
                 f"Ganancia piezas {_money(rr['ganancia_piezas'])}   ·   "
                 f"Ganancia real {_money(rr['ganancia_real'])} "
                 f"(merma {_kg(rr['merma_kg'])})")
        # Acciones según estado.
        if abierta:
            self.btn_nueva_pieza.grid()
            self.btn_cerrar_res.grid()
        else:
            self.btn_nueva_pieza.grid_remove()
            self.btn_cerrar_res.grid_remove()

        piezas = ds.listar_piezas(self._res_id)
        # Mantener la pieza seleccionada si sigue existiendo; si no, la primera.
        ids = [p.id for p in piezas]
        if self._pieza_id not in ids:
            self._pieza_id = ids[0] if ids else None
        self._render_piezas(piezas)
        self._render_cortes()

    def _render_piezas(self, piezas) -> None:
        for w in self.fila_piezas.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.fila_piezas, text="Piezas:", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).pack(side="left", padx=(0, 8))
        if not piezas:
            ctk.CTkLabel(self.fila_piezas,
                         text="agregá la primera (Espalda / Pierna)",
                         font=theme.fuente(13), text_color=theme.TXT_MUTED).pack(
                side="left")
            return
        for p in piezas:
            activa = p.id == self._pieza_id
            cerrada = p.estado != ABIERTA
            txt = f"{p.nombre} · {_kg(p.peso)}" + ("  ✓" if cerrada else "")
            ctk.CTkButton(
                self.fila_piezas, text=txt, height=30, corner_radius=16,
                font=theme.fuente(13, "bold" if activa else "normal"),
                fg_color=theme.PRIMARY if activa else "transparent",
                text_color="#FFFFFF" if activa else theme.ACCENT,
                border_width=0 if activa else 1, border_color=theme.GHOST,
                hover_color=theme.PRIMARY_HOVER if activa else theme.GHOST,
                command=lambda pid=p.id: self._seleccionar_pieza(pid)).pack(
                side="left", padx=3)

    def _seleccionar_pieza(self, pieza_id: str) -> None:
        self._pieza_id = pieza_id
        self._render_cortes()
        # Re-render de las pills para mover el resaltado.
        self._render_piezas(ds.listar_piezas(self._res_id))

    def _render_cortes(self) -> None:
        for w in self.tabla_cortes.winfo_children():
            w.destroy()
        if self._pieza_id is None:
            self._pie_vacio()
            ctk.CTkLabel(self.tabla_cortes,
                         text="Elegí o creá una pieza para cargar sus cortes.",
                         font=theme.fuente(14), text_color=theme.TXT_MUTED).pack(
                pady=40)
            self.btn_agregar_corte.configure(state="disabled")
            self.btn_confirmar.configure(state="disabled")
            return

        resumen = ds.resumen_pieza(self._pieza_id)
        pieza = resumen["pieza"]
        abierta = pieza.estado == ABIERTA
        cortes = resumen["cortes"]

        if not cortes:
            ctk.CTkLabel(self.tabla_cortes,
                         text="Esta pieza no tiene cortes todavía.\n"
                              "Tocá «Agregar corte».",
                         font=theme.fuente(14), text_color=theme.TXT_MUTED,
                         justify="center").pack(pady=40)
        for i, c in enumerate(cortes):
            self._fila_corte(i, c, abierta, resumen["venta"])

        # Totales del pie.
        self.lbl_pie_venta.configure(text=f"Valor venta {_money(resumen['venta'])}")
        self.lbl_pie_costo.configure(
            text=f"Costo {_money(resumen['costo'])} ({_kg(resumen['peso'])})")
        g = resumen["ganancia"]
        self.lbl_pie_gan.configure(text=f"Ganancia {_money(g)}",
                                   text_color=theme.VERDE if g >= 0 else theme.ROJO)
        # Acciones según estado de la pieza.
        self.btn_agregar_corte.configure(state="normal" if abierta else "disabled")
        if abierta and cortes:
            self.btn_confirmar.configure(state="normal")
        else:
            self.btn_confirmar.configure(state="disabled")

    def _pie_vacio(self) -> None:
        self.lbl_pie_venta.configure(text="Valor venta —")
        self.lbl_pie_costo.configure(text="Costo —")
        self.lbl_pie_gan.configure(text="Ganancia —", text_color=theme.VERDE)

    def _fila_corte(self, i: int, c, editable: bool, total_venta) -> None:
        f = ctk.CTkFrame(self.tabla_cortes,
                         fg_color=theme.ROW_ALT if i % 2 else "transparent",
                         corner_radius=8)
        f.pack(fill="x", padx=6, pady=1)
        f.grid_columnconfigure(6, weight=1)   # el sobrante va a la derecha
        nombre = c.descripcion + ("   (desperdicio)" if c.es_desperdicio else "")
        ctk.CTkLabel(f, text=nombre, width=240, anchor="w", font=theme.fuente(14),
                     text_color=theme.TXT_MUTED if c.es_desperdicio else theme.TXT).grid(
            row=0, column=0, padx=4, sticky="w")
        ctk.CTkLabel(f, text=str(c.peso), width=90, anchor="e",
                     font=theme.fuente(14), text_color=theme.TXT).grid(row=0, column=1, padx=4)
        precio = "—" if c.es_desperdicio else _money(c.precio_venta_kg)
        ctk.CTkLabel(f, text=precio, width=110, anchor="e", font=theme.fuente(14),
                     text_color=theme.TXT_MUTED).grid(row=0, column=2, padx=4)
        # % que representa este corte sobre el valor total de venta de la pieza.
        if c.subtotal > 0 and total_venta > 0:
            share = (c.subtotal / total_venta * 100).quantize(Decimal("0.1"))
            pct = f"{share}%"
        else:
            pct = "—"
        ctk.CTkLabel(f, text=pct, width=90, anchor="e", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(row=0, column=3, padx=4)
        total = "—" if c.es_desperdicio else _money(c.subtotal)
        ctk.CTkLabel(f, text=total, width=120, anchor="e",
                     font=theme.fuente(14, "bold"), text_color=theme.TXT).grid(
            row=0, column=4, padx=4)
        acc = ctk.CTkFrame(f, fg_color="transparent")
        acc.grid(row=0, column=5, padx=2)
        if editable:
            ctk.CTkButton(acc, text="✏  Editar", width=92, height=30, corner_radius=8,
                          font=theme.fuente(13), fg_color="transparent",
                          text_color=theme.ACCENT, hover_color=theme.GHOST,
                          command=lambda cid=c.id: self._editar_corte(cid)).pack(side="left", padx=1)
            ctk.CTkButton(acc, text="🗑  Quitar", width=92, height=30, corner_radius=8,
                          font=theme.fuente(13), fg_color="transparent",
                          text_color=theme.ROJO, hover_color=theme.GHOST,
                          command=lambda cid=c.id: self._quitar_corte(cid)).pack(side="left", padx=1)
        else:
            ctk.CTkLabel(acc, text="✓  Cargado", width=100, anchor="w",
                         font=theme.fuente(13, "bold"),
                         text_color=theme.VERDE).pack()

    # --- Acciones -----------------------------------------------------------

    def _nueva_res(self) -> None:
        datos = ResDialog(self).mostrar()
        if datos is None:
            return
        try:
            res_id = ds.crear_res(
                descripcion=datos["descripcion"], peso_total=datos["peso_total"],
                costo_por_kg=datos["costo_por_kg"], proveedor_id=datos["proveedor_id"],
                margen_pct=datos["margen_pct"], condicion=datos["condicion"])
        except ds.DespieceError as e:
            notificar.error(self, "No se pudo crear la res", str(e))
            return
        mostrar_toast(self, "Res creada", tipo="ok")
        self._abrir_res(res_id)

    def _eliminar_res(self, res) -> None:
        cc = res.condicion == CUENTA_CORRIENTE
        extra = ("\nComo era a cuenta corriente, se le va a descontar la deuda "
                 "al proveedor." if cc else "")
        if not notificar.confirmar(
                self, "Eliminar res",
                f"¿Eliminar «{res.descripcion}» con todas sus piezas y cortes?"
                f"{extra}\nEsta acción no se puede deshacer."):
            return
        try:
            ds.eliminar_res(res.id)
        except ds.DespieceError as e:
            notificar.error(self, "No se pudo eliminar", str(e))
            return
        mostrar_toast(self, "Res eliminada", tipo="ok")
        self._ir_a_lista()

    def _cerrar_res(self) -> None:
        if not notificar.confirmar(
                self, "Cerrar res",
                "¿Cerrar esta res? No vas a poder agregarle más piezas ni cortes."):
            return
        try:
            ds.cerrar_res(self._res_id)
        except ds.DespieceError as e:
            notificar.error(self, "No se pudo cerrar", str(e))
            return
        mostrar_toast(self, "Res cerrada", tipo="ok")
        self._recargar_detalle()

    def _nueva_pieza(self) -> None:
        datos = PiezaDialog(self).mostrar()
        if datos is None:
            return
        try:
            pid = ds.agregar_pieza(self._res_id, datos["nombre"],
                                   margen_pct=datos["margen_pct"])
        except ds.DespieceError as e:
            notificar.error(self, "No se pudo agregar la pieza", str(e))
            return
        self._pieza_id = pid
        mostrar_toast(self, f"Pieza «{datos['nombre']}» agregada", tipo="ok")
        self._recargar_detalle()

    def _agregar_corte(self) -> None:
        res = ds.obtener_res(self._res_id)
        costo_kg = res.costo_por_kg if res else Decimal("0")
        datos = CorteDialog(self, costo_kg=costo_kg).mostrar()
        if datos is None:
            return
        try:
            ds.agregar_corte(
                self._pieza_id, datos["descripcion"], datos["peso"],
                precio_venta_kg=datos["precio_venta_kg"],
                margen_pct=datos["margen_pct"],
                es_desperdicio=datos["es_desperdicio"],
                producto_id=datos["producto_id"])
        except ds.DespieceError as e:
            notificar.error(self, "No se pudo agregar el corte", str(e))
            return
        self._recargar_detalle()

    def _editar_corte(self, corte_id: str) -> None:
        actual = next((c for c in ds.listar_cortes(self._pieza_id)
                       if c.id == corte_id), None)
        if actual is None:
            return
        res = ds.obtener_res(self._res_id)
        costo_kg = res.costo_por_kg if res else Decimal("0")
        datos = CorteDialog(self, costo_kg=costo_kg, corte=actual).mostrar()
        if datos is None:
            return
        try:
            ds.editar_corte(
                corte_id, datos["descripcion"], datos["peso"],
                precio_venta_kg=datos["precio_venta_kg"],
                margen_pct=datos["margen_pct"],
                es_desperdicio=datos["es_desperdicio"])
        except ds.DespieceError as e:
            notificar.error(self, "No se pudo guardar", str(e))
            return
        self._recargar_detalle()

    def _quitar_corte(self, corte_id: str) -> None:
        if not notificar.confirmar(self, "Quitar corte", "¿Quitar este corte?"):
            return
        try:
            ds.quitar_corte(corte_id)
        except ds.DespieceError as e:
            notificar.error(self, "No se pudo quitar", str(e))
            return
        self._recargar_detalle()

    def _confirmar_pieza(self) -> None:
        resumen = ds.resumen_pieza(self._pieza_id)
        if not notificar.confirmar(
                self, "Confirmar pieza",
                f"Se va a cargar el stock de {len(resumen['cortes'])} cortes "
                f"({_kg(resumen['peso'])}) a la sección Stock. "
                "Después la pieza no se podrá editar. ¿Confirmar?",
                confirmar_txt="Confirmar y cargar stock", cancelar_txt="Todavía no"):
            return
        try:
            res = ds.confirmar_pieza(self._pieza_id)
        except ds.DespieceError as e:
            notificar.error(self, "No se pudo confirmar", str(e))
            return
        mostrar_toast(self, f"Pieza confirmada · {res['cortes_confirmados']} cortes "
                            "cargados al stock", tipo="ok")
        self._recargar_detalle()
