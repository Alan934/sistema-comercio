"""Vista de Clientes: listado con su deuda (cuenta corriente / fiado),
alta de cliente y registro de pagos cuando saldan su cuenta."""
from decimal import Decimal
from math import ceil

import customtkinter as ctk

from app.core import formato

from app.services import cliente_service
from app.ui import theme
from app.ui.tablas import PintorEnTandas
from app.ui.toast import mostrar_toast
from app.ui.dialogs import notificar
from app.ui.dialogs.cliente_dialog import ClienteDialog
from app.ui.dialogs.proveedor_dialog import PagoDialog
from app.ui.dialogs.ajuste_saldo_dialog import AjusteSaldoDialog


def _money(v) -> str:
    return formato.moneda(v)


def _texto_saldo(saldo):
    """Positivo = nos debe; negativo = tiene saldo a favor."""
    if saldo > 0:
        return f"Te debe {_money(saldo)}", theme.ROJO
    if saldo < 0:
        return f"{_money(abs(saldo))} a favor", theme.VERDE
    return "Al día", theme.TXT_MUTED


PAGE_SIZE = 50
DEBOUNCE_MS = 250
# Filtro por estado de cuenta (los textos son también las claves).
CUENTA_TODAS = "Todas las cuentas"
CUENTA_DEBE = "Nos deben"
CUENTA_FAVOR = "Tienen saldo a favor"
CUENTA_ALDIA = "Al día"
CUENTAS = [CUENTA_TODAS, CUENTA_DEBE, CUENTA_FAVOR, CUENTA_ALDIA]
ORD_NOMBRE = "Nombre (A→Z)"
ORD_DEUDA = "Mayor deuda primero"
ORD_DEUDA_MENOR = "Menor deuda primero"
ORDENES = [ORD_NOMBRE, ORD_DEUDA, ORD_DEUDA_MENOR]


class ClientesView(ctk.CTkFrame):
    def __init__(self, master, usuario=None):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario
        self._clientes = []
        self._visibles = []
        self._pagina = 0
        self._debounce_id = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Clientes", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        self.ent_buscar = ctk.CTkEntry(
            top, placeholder_text="Buscar por nombre o teléfono…", width=260,
            height=40, corner_radius=10, font=theme.fuente(14))
        self.ent_buscar.grid(row=0, column=1, sticky="e", padx=8)
        self.ent_buscar.bind("<KeyRelease>", lambda _e: self._render_debounced())
        ctk.CTkButton(top, text="Nuevo cliente", width=150, height=40,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._nuevo).grid(row=0, column=2)

        # --- Barra de filtros ---
        barra = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=10)
        barra.grid(row=1, column=0, sticky="ew", padx=20, pady=(2, 4))
        barra.grid_columnconfigure(3, weight=1)

        def _menu(col, values, ancho):
            m = ctk.CTkOptionMenu(
                barra, values=values, width=ancho, height=32,
                font=theme.fuente(13), dropdown_font=theme.fuente(13),
                fg_color=theme.GHOST_BTN_BG, button_color=theme.GHOST_BTN_BG,
                button_hover_color=theme.GHOST_BTN_HOVER, text_color=theme.TXT,
                command=lambda _v: self._filtro_inmediato())
            m.grid(row=0, column=col, padx=(8, 4), pady=8)
            return m

        self._f_cuenta = _menu(0, CUENTAS, 210)
        self._f_orden = _menu(1, ORDENES, 190)
        ctk.CTkButton(barra, text="Limpiar filtros", width=120, height=32,
                      corner_radius=8, font=theme.fuente(13),
                      fg_color="transparent", text_color=theme.ACCENT,
                      hover_color=theme.GHOST,
                      command=self._limpiar_filtros).grid(
            row=0, column=4, padx=(4, 8), pady=8)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=2, column=0, sticky="ew", padx=28)
        for col, (txt, w) in enumerate(
                [("Cliente", 240), ("Teléfono", 150), ("Nos debe", 190), ("", 200)]):
            ctk.CTkLabel(header, text=txt, width=w, anchor="w",
                         font=theme.fuente(12, "bold"),
                         text_color=theme.TXT_MUTED).grid(row=0, column=col, padx=4)

        self.tabla = ctk.CTkScrollableFrame(self, fg_color=theme.CARD_BG,
                                            corner_radius=12)
        self.tabla.grid(row=3, column=0, sticky="nsew", padx=20, pady=(6, 6))
        self.tabla.grid_columnconfigure(0, weight=1)
        self._pintor = PintorEnTandas(self.tabla)

        # --- Paginador ---
        pag = ctk.CTkFrame(self, fg_color="transparent")
        pag.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 14))
        pag.grid_columnconfigure(1, weight=1)
        self.btn_prev = ctk.CTkButton(
            pag, text="‹ Anterior", width=110, height=32, corner_radius=8,
            font=theme.fuente(13), fg_color=theme.GHOST_BTN_BG,
            text_color=theme.ACCENT, border_width=1,
            border_color=theme.GHOST_BTN_BORDER, hover_color=theme.GHOST_BTN_HOVER,
            command=self._pagina_prev)
        self.btn_prev.grid(row=0, column=0, sticky="w")
        self.lbl_pagina = ctk.CTkLabel(pag, text="", font=theme.fuente(13),
                                       text_color=theme.TXT_MUTED)
        self.lbl_pagina.grid(row=0, column=1)
        self.btn_next = ctk.CTkButton(
            pag, text="Siguiente ›", width=110, height=32, corner_radius=8,
            font=theme.fuente(13), fg_color=theme.GHOST_BTN_BG,
            text_color=theme.ACCENT, border_width=1,
            border_color=theme.GHOST_BTN_BORDER, hover_color=theme.GHOST_BTN_HOVER,
            command=self._pagina_next)
        self.btn_next.grid(row=0, column=2, sticky="e")

    def al_mostrar(self) -> None:
        self._recargar()

    def _recargar(self) -> None:
        self._clientes = cliente_service.listar_activos()
        self._pagina = 0
        self._render_tabla()

    # --- Filtros + paginación ----------------------------------------------

    def _filtrar(self) -> list:
        texto = self.ent_buscar.get().strip().lower()
        cuenta = self._f_cuenta.get()
        res = []
        for c in self._clientes:
            if texto and texto not in c.nombre.lower() \
                    and texto not in (c.telefono or "").lower():
                continue
            s = c.saldo_cuenta
            if cuenta == CUENTA_DEBE and not s > 0:
                continue
            if cuenta == CUENTA_FAVOR and not s < 0:
                continue
            if cuenta == CUENTA_ALDIA and s != 0:
                continue
            res.append(c)
        orden = self._f_orden.get()
        if orden == ORD_DEUDA:
            res.sort(key=lambda c: c.saldo_cuenta, reverse=True)
        elif orden == ORD_DEUDA_MENOR:
            res.sort(key=lambda c: c.saldo_cuenta)
        else:
            res.sort(key=lambda c: c.nombre.lower())
        return res

    def _filtro_inmediato(self) -> None:
        self._pagina = 0
        self._render_tabla()

    def _limpiar_filtros(self) -> None:
        self.ent_buscar.delete(0, "end")
        self._f_cuenta.set(CUENTA_TODAS)
        self._f_orden.set(ORD_NOMBRE)
        self._pagina = 0
        self._render_tabla()

    def _render_debounced(self) -> None:
        self._pagina = 0
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(DEBOUNCE_MS, self._render_tabla)

    def _render_tabla(self) -> None:
        self._debounce_id = None
        self._pintor.cancelar()
        for w in self.tabla.winfo_children():
            w.destroy()
        self._visibles = self._filtrar()
        total = len(self._visibles)
        paginas = max(1, ceil(total / PAGE_SIZE))
        self._pagina = max(0, min(self._pagina, paginas - 1))
        self._actualizar_paginador(total, paginas)
        if total == 0:
            hay_filtro = bool(self.ent_buscar.get().strip()
                              or self._f_cuenta.get() != CUENTA_TODAS)
            txt = ("Ningún cliente coincide con los filtros." if hay_filtro
                   else "Todavía no hay clientes.\n"
                        "Creá el primero con “Nuevo cliente”.")
            ctk.CTkLabel(self.tabla, text=txt, font=theme.fuente(14),
                         text_color=theme.TXT_MUTED, justify="center").pack(pady=36)
            return
        ini = self._pagina * PAGE_SIZE
        self._pintor.pintar(self._visibles[ini:ini + PAGE_SIZE], self._fila)

    def _actualizar_paginador(self, total: int, paginas: int) -> None:
        if total == 0:
            self.lbl_pagina.configure(text="Sin clientes")
        else:
            desde = self._pagina * PAGE_SIZE + 1
            hasta = min((self._pagina + 1) * PAGE_SIZE, total)
            self.lbl_pagina.configure(
                text=f"{desde}–{hasta} de {total}   ·   "
                     f"Página {self._pagina + 1} de {paginas}")
        self.btn_prev.configure(
            state="normal" if self._pagina > 0 else "disabled")
        self.btn_next.configure(
            state="normal" if self._pagina < paginas - 1 else "disabled")

    def _pagina_prev(self) -> None:
        if self._pagina > 0:
            self._pagina -= 1
            self._render_tabla()

    def _pagina_next(self) -> None:
        if (self._pagina + 1) * PAGE_SIZE < len(self._visibles):
            self._pagina += 1
            self._render_tabla()

    def _fila(self, c, i: int) -> None:
        f = ctk.CTkFrame(self.tabla,
                         fg_color=theme.ROW_ALT if i % 2 else "transparent",
                         corner_radius=8)
        f.pack(fill="x", padx=6, pady=1)
        ctk.CTkLabel(f, text=c.nombre, width=240, anchor="w",
                     font=theme.fuente(15), text_color=theme.TXT).grid(
            row=0, column=0, padx=4, pady=6)
        ctk.CTkLabel(f, text=(c.telefono or "—"), width=150, anchor="w",
                     font=theme.fuente(13), text_color=theme.TXT_MUTED).grid(
            row=0, column=1, padx=4)
        txt, color = _texto_saldo(c.saldo_cuenta)
        ctk.CTkLabel(f, text=txt, width=190, anchor="w",
                     font=theme.fuente(15, "bold"), text_color=color).grid(
            row=0, column=2, padx=4)
        acciones = ctk.CTkFrame(f, fg_color="transparent")
        acciones.grid(row=0, column=3, padx=4)
        ctk.CTkButton(
            acciones, text="💵  Registrar pago", width=160, height=34,
            corner_radius=8, font=theme.fuente(13), fg_color="transparent",
            text_color=theme.ACCENT, hover_color=theme.GHOST,
            command=lambda cid=c.id, n=c.nombre, s=c.saldo_cuenta:
            self._pagar(cid, n, s)).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            acciones, text="⚖  Ajustar", width=110, height=34,
            corner_radius=8, font=theme.fuente(13), fg_color="transparent",
            text_color=theme.TXT_MUTED, hover_color=theme.GHOST,
            command=lambda cid=c.id, n=c.nombre, s=c.saldo_cuenta:
            self._ajustar(cid, n, s)).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            acciones, text="✏  Editar", width=100, height=34,
            corner_radius=8, font=theme.fuente(13), fg_color="transparent",
            text_color=theme.TXT_MUTED, hover_color=theme.GHOST,
            command=lambda cli=c: self._editar(cli)).pack(
            side="left", padx=(0, 4))
        # Eliminar clientes es solo para el administrador.
        if self.usuario is not None and self.usuario.es_admin:
            ctk.CTkButton(
                acciones, text="🗑  Eliminar", width=110, height=34,
                corner_radius=8, font=theme.fuente(13), fg_color="transparent",
                text_color=theme.ROJO, hover_color=theme.GHOST,
                command=lambda cid=c.id, n=c.nombre:
                self._eliminar(cid, n)).pack(side="left")

    def _nuevo(self) -> None:
        datos = ClienteDialog(self).mostrar()
        if datos is None:
            return
        try:
            cliente_service.crear(datos["nombre"], datos["telefono"],
                                  datos["limite_credito"])
        except cliente_service.ClienteError as e:
            notificar.error(self, "No se pudo crear", str(e))
            return
        self._recargar()
        mostrar_toast(self, "Cliente creado", tipo="ok")

    def _editar(self, cliente) -> None:
        datos = ClienteDialog(self, cliente).mostrar()
        if datos is None:
            return
        try:
            cliente_service.editar(cliente.id, datos["nombre"],
                                   datos["telefono"], datos["limite_credito"])
        except cliente_service.ClienteError as e:
            notificar.error(self, "No se pudo editar", str(e))
            return
        self._recargar()
        mostrar_toast(self, "Cambios guardados", tipo="ok")

    def _eliminar(self, cliente_id: str, nombre: str) -> None:
        if not notificar.confirmar(
                self, "Eliminar cliente",
                f"¿Seguro que querés eliminar a «{nombre}»? Dejará de aparecer "
                "en la lista de clientes.",
                confirmar_txt="Sí, eliminar", cancelar_txt="No"):
            return
        try:
            cliente_service.eliminar(cliente_id)
        except cliente_service.ClienteError as e:
            notificar.error(self, "No se pudo eliminar", str(e))
            return
        self._recargar()
        mostrar_toast(self, f"«{nombre}» eliminado", tipo="ok")

    def _pagar(self, cliente_id: str, nombre: str, saldo) -> None:
        datos = PagoDialog(self, "Registrar pago",
                           f"Pago de {nombre}:").mostrar()
        if datos is None:
            return
        monto, metodo = datos["monto"], datos["metodo"]
        if monto > saldo:
            if saldo > 0:
                msg = (f"{nombre} te debe {_money(saldo)} y vas a registrar un "
                       f"pago de {_money(monto)}.\nLe quedarán "
                       f"{_money(monto - saldo)} a favor. ¿Continuar?")
            else:
                msg = (f"{nombre} no tiene deuda. El pago de {_money(monto)} le "
                       "quedará a favor. ¿Continuar?")
            if not notificar.confirmar(self, "Pago mayor a la deuda", msg):
                return
        try:
            cliente_service.registrar_pago(cliente_id, monto, metodo)
        except cliente_service.ClienteError as e:
            notificar.error(self, "No se pudo registrar", str(e))
            return
        self._recargar()
        mostrar_toast(self, f"Pago de {_money(monto)} registrado", tipo="ok")

    def _ajustar(self, cliente_id: str, nombre: str, saldo) -> None:
        texto, _ = _texto_saldo(saldo)
        nuevo = AjusteSaldoDialog(self, nombre, "¿Cuánto te debe en total?",
                                  texto, saldo).mostrar()
        if nuevo is None:
            return
        try:
            cliente_service.ajustar_saldo(cliente_id, nuevo)
        except cliente_service.ClienteError as e:
            notificar.error(self, "No se pudo ajustar", str(e))
            return
        self._recargar()
        mostrar_toast(self, "Saldo ajustado", tipo="ok")
