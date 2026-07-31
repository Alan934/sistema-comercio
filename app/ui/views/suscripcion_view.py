"""Vista de la Suscripción del software.

Dos lecturas de la misma pantalla:
  - El dueño del comercio (ADMIN) la ve de SOLO LECTURA: en qué estado está,
    cuántos días le quedan, cuántos meses lleva pagados, su historial y a dónde
    tiene que pagar.
  - El super administrador ve además los botones para configurar el contrato,
    registrar cobros y anular un pago mal cargado.
"""
from datetime import date, datetime

import customtkinter as ctk

from app.core import formato, suscripcion
from app.services import suscripcion_service
from app.ui import theme
from app.ui.toast import mostrar_toast
from app.ui.dialogs import notificar
from app.ui.dialogs.suscripcion_dialog import (ConfigSuscripcionDialog,
                                               PagoSuscripcionDialog)

_MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun",
                 "jul", "ago", "sep", "oct", "nov", "dic")


def colores(estado: str):
    """(color del texto, color de fondo, ícono) según el estado."""
    if estado == suscripcion.AL_DIA:
        return theme.VERDE, theme.VERDE_BG, "✓"
    if estado == suscripcion.POR_VENCER:
        return theme.BADGE_KG_TXT, theme.BADGE_KG_BG, "⏳"
    if estado in (suscripcion.VENCIDA, suscripcion.SUSPENDIDA):
        return theme.ROJO, theme.ROJO_BG, "⚠"
    return theme.TXT_MUTED, theme.GHOST, "•"


def mensaje_estado(est) -> tuple[str, str]:
    """(título, detalle) para mostrar en la vista, el banner y el aviso."""
    hasta = _fecha(est.cubierto_hasta)
    if est.estado == suscripcion.SIN_CONFIGURAR:
        return ("Suscripción sin configurar",
                "Todavía no se cargaron la fecha de inicio ni la cuota.")
    if est.estado == suscripcion.AL_DIA:
        detalle = f"Cubierta hasta el {hasta}."
        if not est.manual:
            detalle += f" Faltan {est.dias_restantes} días."
        return "Suscripción al día", detalle
    if est.estado == suscripcion.POR_VENCER:
        cuando = ("Vence hoy" if est.dias_restantes == 0
                  else f"Vence en {est.dias_restantes} día"
                       f"{'s' if est.dias_restantes != 1 else ''}")
        return f"{cuando} ({hasta})", (
            "Conviene abonar antes de esa fecha para no quedar en deuda.")
    if est.estado == suscripcion.VENCIDA:
        dias = est.dias_de_atraso
        return (f"Pago vencido hace {dias} día{'s' if dias != 1 else ''}",
                f"La cobertura venció el {hasta}. Si no se abona antes del "
                f"{_fecha(est.fecha_suspension)}, la cuenta queda suspendida "
                f"({est.dias_para_suspension} días).")
    return ("Cuenta suspendida",
            f"La cobertura venció el {hasta} y ya pasaron los "
            f"{est.gracia_dias} días de plazo. Se puede seguir vendiendo y "
            "atendiendo clientes; el resto del sistema queda bloqueado hasta "
            "regularizar el pago.")


def _fecha(f) -> str:
    if isinstance(f, date):
        return f.strftime("%d/%m/%Y")
    return "—"


def _fecha_hora(ts) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromisoformat(ts).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return str(ts)[:16]


class SuscripcionView(ctk.CTkFrame):
    def __init__(self, master, usuario):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario
        self.admin = suscripcion_service.puede_administrar(usuario)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Suscripción", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        if self.admin:
            acciones = ctk.CTkFrame(top, fg_color="transparent")
            acciones.grid(row=0, column=2, sticky="e")
            ctk.CTkButton(acciones, text="⚙  Configurar", width=140, height=40,
                          corner_radius=10, font=theme.fuente(14),
                          fg_color=theme.GHOST_BTN_BG, text_color=theme.ACCENT,
                          border_width=1, border_color=theme.GHOST_BTN_BORDER,
                          hover_color=theme.GHOST_BTN_HOVER,
                          command=self._configurar).pack(side="left", padx=(0, 8))
            ctk.CTkButton(acciones, text="＋  Registrar pago", width=180, height=40,
                          corner_radius=10, font=theme.fuente(14),
                          fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                          command=self._registrar_pago).pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.scroll.grid_columnconfigure(0, weight=1)

    # --- Carga ---
    def al_mostrar(self) -> None:
        self._recargar()

    def _recargar(self) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()
        datos = suscripcion_service.resumen()
        est = datos["estado"]
        fila = 0

        if datos["config_alterada"]:
            fila = self._aviso_alteracion(fila)
        self._hero(fila, est)
        fila += 1
        self._tarjetas(fila, est)
        fila += 1
        if est.configurada:
            self._calendario(fila, est)
            fila += 1
        if datos["datos_pago"]:
            self._datos_pago(fila, datos["datos_pago"], datos["comercio"])
            fila += 1
        self._historial(fila, datos["pagos"], est)

    # --- Bloques ---
    def _hero(self, fila: int, est) -> None:
        color, fondo, icono = colores(est.estado)
        titulo, detalle = mensaje_estado(est)
        card = ctk.CTkFrame(self.scroll, fg_color=fondo, corner_radius=14)
        card.grid(row=fila, column=0, sticky="ew", padx=8, pady=(6, 8))
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text=icono, width=56, height=56, corner_radius=28,
                     fg_color=color, text_color="#FFFFFF",
                     font=theme.fuente(26, "bold")).grid(
            row=0, column=0, rowspan=2, padx=(20, 16), pady=20)
        ctk.CTkLabel(card, text=titulo, anchor="w", font=theme.fuente(22, "bold"),
                     text_color=color).grid(row=0, column=1, sticky="w",
                                            pady=(20, 0))
        ctk.CTkLabel(card, text=detalle, anchor="w", justify="left",
                     wraplength=680, font=theme.fuente(14),
                     text_color=theme.TXT).grid(row=1, column=1, sticky="w",
                                                pady=(2, 20))
        if est.manual:
            ctk.CTkLabel(card, text="estado fijado a mano", font=theme.fuente(11),
                         text_color=theme.TXT_MUTED).grid(
                row=0, column=2, sticky="ne", padx=16, pady=(20, 0))

    def _tarjetas(self, fila: int, est) -> None:
        cont = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cont.grid(row=fila, column=0, sticky="ew", padx=8, pady=(0, 8))
        for i in range(3):
            cont.grid_columnconfigure(i, weight=1, uniform="tarjetas")

        restantes = est.dias_restantes
        if est.estado == suscripcion.SIN_CONFIGURAR:
            dias_txt, dias_col = "—", theme.TXT_MUTED
        elif restantes >= 0:
            dias_txt = f"{restantes}"
            dias_col = theme.VERDE if restantes > suscripcion.DIAS_AVISO_PREVIO \
                else theme.BADGE_KG_TXT
        else:
            dias_txt, dias_col = f"−{est.dias_de_atraso}", theme.ROJO

        self._tarjeta(cont, 0, "Días restantes", dias_txt, dias_col,
                      "de atraso" if restantes < 0 else "hasta el vencimiento")
        self._tarjeta(cont, 1, "Meses pagados", str(est.meses_pagados), theme.TXT,
                      f"cubre hasta el {_fecha(est.cubierto_hasta)}")
        self._tarjeta(cont, 2, "Cuota mensual",
                      formato.moneda(est.monto_mensual), theme.TXT,
                      f"{est.gracia_dias} días de gracia")

    def _tarjeta(self, cont, col: int, titulo: str, valor: str, color, pie: str):
        card = ctk.CTkFrame(cont, fg_color=theme.CARD_BG, corner_radius=12)
        card.grid(row=0, column=col, sticky="nsew", padx=4)
        ctk.CTkLabel(card, text=titulo, font=theme.fuente(12),
                     text_color=theme.TXT_MUTED).pack(anchor="w", padx=16,
                                                      pady=(14, 0))
        ctk.CTkLabel(card, text=valor, font=theme.fuente(28, "bold"),
                     text_color=color).pack(anchor="w", padx=16, pady=(0, 0))
        ctk.CTkLabel(card, text=pie, font=theme.fuente(11),
                     text_color=theme.TXT_MUTED).pack(anchor="w", padx=16,
                                                      pady=(0, 14))

    def _calendario(self, fila: int, est) -> None:
        """Doce meses a partir del actual: en verde los que están cubiertos."""
        card = ctk.CTkFrame(self.scroll, fg_color=theme.CARD_BG, corner_radius=12)
        card.grid(row=fila, column=0, sticky="ew", padx=8, pady=(0, 8))
        ctk.CTkLabel(card, text="Meses cubiertos", font=theme.fuente(13, "bold"),
                     text_color=theme.TXT_MUTED).pack(anchor="w", padx=16,
                                                      pady=(14, 6))
        tira = ctk.CTkFrame(card, fg_color="transparent")
        tira.pack(fill="x", padx=12, pady=(0, 14))
        hoy = date.today()
        primero = date(hoy.year, hoy.month, 1)
        for i in range(12):
            mes = suscripcion.sumar_meses(primero, i)
            cubierto = est.cubierto_hasta is not None and mes < est.cubierto_hasta
            chip = ctk.CTkFrame(
                tira, corner_radius=8, height=52,
                fg_color=theme.VERDE_BG if cubierto else theme.GHOST,
                border_width=2 if i == 0 else 0, border_color=theme.ACCENT)
            chip.grid(row=0, column=i, sticky="ew", padx=3)
            tira.grid_columnconfigure(i, weight=1, uniform="meses")
            ctk.CTkLabel(chip, text=_MESES_CORTOS[mes.month - 1],
                         font=theme.fuente(12, "bold"),
                         text_color=theme.VERDE if cubierto else theme.TXT_MUTED
                         ).pack(pady=(8, 0))
            ctk.CTkLabel(chip, text=str(mes.year)[2:], font=theme.fuente(10),
                         text_color=theme.TXT_MUTED).pack(pady=(0, 8))

    def _datos_pago(self, fila: int, datos: str, comercio: str) -> None:
        card = ctk.CTkFrame(self.scroll, fg_color=theme.CARD_BG, corner_radius=12)
        card.grid(row=fila, column=0, sticky="ew", padx=8, pady=(0, 8))
        titulo = "Dónde pagar" + (f"  ·  {comercio}" if comercio else "")
        ctk.CTkLabel(card, text=titulo, font=theme.fuente(13, "bold"),
                     text_color=theme.TXT_MUTED).pack(anchor="w", padx=16,
                                                      pady=(14, 2))
        ctk.CTkLabel(card, text=datos, anchor="w", justify="left", wraplength=680,
                     font=theme.fuente(16), text_color=theme.TXT).pack(
            anchor="w", padx=16, pady=(0, 14))

    def _aviso_alteracion(self, fila: int) -> int:
        card = ctk.CTkFrame(self.scroll, fg_color=theme.ROJO_BG, corner_radius=12)
        card.grid(row=fila, column=0, sticky="ew", padx=8, pady=(6, 4))
        ctk.CTkLabel(
            card, text="⚠  La configuración de la suscripción fue modificada "
                       "fuera del sistema. Se va a corregir sola en la próxima "
                       "sincronización con la nube.",
            anchor="w", justify="left", wraplength=680, font=theme.fuente(13),
            text_color=theme.ROJO).pack(anchor="w", padx=16, pady=12)
        return fila + 1

    def _historial(self, fila: int, pagos: list, est) -> None:
        cont = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cont.grid(row=fila, column=0, sticky="ew", padx=8, pady=(4, 8))
        cont.grid_columnconfigure(0, weight=1)
        titulo = "Historial de pagos"
        if est.pagos_invalidos:
            titulo += f"   ⚠ {est.pagos_invalidos} registro(s) sin validar"
        ctk.CTkLabel(cont, text=titulo, font=theme.fuente(13, "bold"),
                     text_color=theme.TXT_MUTED).grid(row=0, column=0, sticky="w",
                                                      padx=8, pady=(4, 4))

        tabla = ctk.CTkFrame(cont, fg_color=theme.CARD_BG, corner_radius=12)
        tabla.grid(row=1, column=0, sticky="ew")
        tabla.grid_columnconfigure(0, weight=1)

        if not pagos:
            ctk.CTkLabel(tabla, text="Todavía no se registró ningún pago.",
                         text_color=theme.TXT_MUTED).pack(pady=30)
            return

        cab = ctk.CTkFrame(tabla, fg_color="transparent")
        cab.pack(fill="x", padx=10, pady=(10, 2))
        for texto, ancho in (("Fecha", 140), ("Meses", 80), ("Monto", 130),
                             ("Cómo pagó", 130), ("Cargó", 100)):
            ctk.CTkLabel(cab, text=texto, width=ancho, anchor="w",
                         font=theme.fuente(12, "bold"),
                         text_color=theme.TXT_MUTED).pack(side="left", padx=4)

        for i, p in enumerate(pagos):
            self._fila_pago(tabla, p, i)

    def _fila_pago(self, tabla, p: dict, i: int) -> None:
        f = ctk.CTkFrame(tabla, fg_color=theme.ROW_ALT if i % 2 else "transparent",
                         corner_radius=8)
        f.pack(fill="x", padx=10, pady=1)
        anulado = p["anulado"]
        invalido = not p["valido"]
        gris = anulado or invalido
        col_txt = theme.TXT_MUTED if gris else theme.TXT

        ctk.CTkLabel(f, text=_fecha_hora(p["fecha"]), width=140, anchor="w",
                     font=theme.fuente(13), text_color=col_txt).pack(side="left",
                                                                    padx=4, pady=2)
        ctk.CTkLabel(f, text=f"{p['meses']} mes{'es' if p['meses'] != 1 else ''}",
                     width=80, anchor="w", font=theme.fuente(13, "bold"),
                     text_color=col_txt).pack(side="left", padx=4)
        ctk.CTkLabel(f, text=formato.moneda(p["monto"]), width=130, anchor="w",
                     font=theme.fuente(13), text_color=col_txt).pack(side="left",
                                                                    padx=4)
        ctk.CTkLabel(f, text=(p["metodo"] or "").capitalize(), width=130,
                     anchor="w", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).pack(side="left", padx=4)
        ctk.CTkLabel(f, text=p["registrado_por"] or "—", width=100, anchor="w",
                     font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).pack(side="left", padx=4)

        if anulado:
            self._badge(f, "anulado", theme.ROJO, theme.ROJO_BG)
        if invalido:
            self._badge(f, "⚠ sin validar", theme.ROJO, theme.ROJO_BG)
        if p["nota"]:
            ctk.CTkLabel(f, text=p["nota"], anchor="w", font=theme.fuente(12),
                         text_color=theme.TXT_MUTED).pack(side="left", padx=8)

        if self.admin and not anulado:
            ctk.CTkButton(f, text="🗑  Anular", width=90, height=28,
                          corner_radius=8, font=theme.fuente(12),
                          fg_color="transparent", text_color=theme.ROJO,
                          hover_color=theme.GHOST,
                          command=lambda pid=p["id"]: self._anular(pid)).pack(
                side="right", padx=6, pady=2)

    def _badge(self, padre, texto: str, color, fondo) -> None:
        # El aire interno se logra con espacios: CTkLabel no acepta padding.
        ctk.CTkLabel(padre, text=f"  {texto}  ", corner_radius=6, fg_color=fondo,
                     text_color=color, font=theme.fuente(11)).pack(side="left",
                                                                   padx=6)

    # --- Acciones (solo super admin) ---
    def _configurar(self) -> None:
        datos = suscripcion_service.resumen()
        res = ConfigSuscripcionDialog(self, datos).mostrar()
        if res is None:
            return
        try:
            suscripcion_service.configurar(
                self.usuario.rol, res["fecha_inicio"], res["monto_mensual"],
                gracia_dias=res["gracia_dias"], datos_pago=res["datos_pago"],
                comercio=res["comercio"], estado_manual=res["estado_manual"])
        except suscripcion_service.SuscripcionError as e:
            notificar.error(self, "Suscripción", str(e))
            return
        mostrar_toast(self, "Suscripción configurada")
        self._recargar()

    def _registrar_pago(self) -> None:
        est = suscripcion_service.estado_actual()
        if not est.configurada:
            notificar.informar(
                self, "Suscripción",
                "Primero configurá la fecha de inicio y la cuota mensual.",
                tipo="alerta")
            return
        res = PagoSuscripcionDialog(self, est.monto_mensual,
                                    est.cubierto_hasta).mostrar()
        if res is None:
            return
        try:
            suscripcion_service.registrar_pago(
                self.usuario.rol, res["meses"], res["monto"],
                metodo=res["metodo"], nota=res["nota"],
                registrado_por=self.usuario.username)
        except suscripcion_service.SuscripcionError as e:
            notificar.error(self, "Suscripción", str(e))
            return
        nuevo = suscripcion_service.estado_actual()
        mostrar_toast(self, f"Pago registrado · cubierto hasta el "
                            f"{_fecha(nuevo.cubierto_hasta)}")
        self._recargar()

    def _anular(self, pago_id: str) -> None:
        if not notificar.confirmar(
                self, "Anular pago",
                "El pago deja de contar y la cobertura se acorta. Queda en el "
                "historial marcado como anulado. ¿Anularlo?",
                confirmar_txt="Anular", cancelar_txt="No"):
            return
        try:
            suscripcion_service.anular_pago(self.usuario.rol, pago_id)
        except suscripcion_service.SuscripcionError as e:
            notificar.error(self, "Suscripción", str(e))
            return
        mostrar_toast(self, "Pago anulado", tipo="info")
        self._recargar()
