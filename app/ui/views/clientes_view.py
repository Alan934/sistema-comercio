"""Vista de Clientes: listado con su deuda (cuenta corriente / fiado),
alta de cliente y registro de pagos cuando saldan su cuenta."""
from decimal import Decimal

import customtkinter as ctk

from app.services import cliente_service
from app.ui import theme
from app.ui.toast import mostrar_toast
from app.ui.dialogs import notificar
from app.ui.dialogs.cliente_dialog import ClienteDialog
from app.ui.dialogs.proveedor_dialog import PagoDialog
from app.ui.dialogs.ajuste_saldo_dialog import AjusteSaldoDialog


def _money(v) -> str:
    return f"${Decimal(str(v)):,.2f}"


def _texto_saldo(saldo):
    """Positivo = nos debe; negativo = tiene saldo a favor."""
    if saldo > 0:
        return f"Te debe {_money(saldo)}", theme.ROJO
    if saldo < 0:
        return f"{_money(abs(saldo))} a favor", theme.VERDE
    return "Al día", theme.TXT_MUTED


class ClientesView(ctk.CTkFrame):
    def __init__(self, master, usuario=None):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Clientes", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Nuevo cliente", width=150, height=40,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._nuevo).grid(row=0, column=2)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=28)
        for col, (txt, w) in enumerate(
                [("Cliente", 240), ("Teléfono", 150), ("Nos debe", 190), ("", 200)]):
            ctk.CTkLabel(header, text=txt, width=w, anchor="w",
                         font=theme.fuente(12, "bold"),
                         text_color=theme.TXT_MUTED).grid(row=0, column=col, padx=4)

        self.tabla = ctk.CTkScrollableFrame(self, fg_color=theme.CARD_BG,
                                            corner_radius=12)
        self.tabla.grid(row=2, column=0, sticky="nsew", padx=20, pady=(6, 18))
        self.tabla.grid_columnconfigure(0, weight=1)

    def al_mostrar(self) -> None:
        self._recargar()

    def _recargar(self) -> None:
        clientes = cliente_service.listar_activos()
        for w in self.tabla.winfo_children():
            w.destroy()
        if not clientes:
            ctk.CTkLabel(self.tabla, text="Todavía no hay clientes.\n"
                         "Creá el primero con “Nuevo cliente”.",
                         font=theme.fuente(14), text_color=theme.TXT_MUTED,
                         justify="center").pack(pady=36)
            return
        for i, c in enumerate(clientes):
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
