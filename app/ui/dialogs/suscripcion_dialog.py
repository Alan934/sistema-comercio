"""Diálogos de la suscripción del software (solo los usa el super administrador).

  - `PagoSuscripcionDialog`: registrar un cobro (1 a 12 meses).
  - `ConfigSuscripcionDialog`: fecha de inicio, cuota, gracia y datos de pago.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.core import formato, suscripcion
from app.ui import theme
from app.ui.dialogs.base import ModalBase

_ATAJOS_MESES = ("1", "2", "3", "6", "12")


def _dec(texto) -> Decimal:
    """Importe escrito a mano -> Decimal. Si hay coma, es el separador decimal y
    los puntos son de miles (15.000,50); si no la hay, el punto es el decimal
    (15000.50), que es como lo escribe la propia app al sugerir el monto."""
    texto = (texto or "").strip()
    if not texto:
        return Decimal("0")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return Decimal("0")


def _fecha_larga(f: date | None) -> str:
    return f.strftime("%d/%m/%Y") if f else "—"


class PagoSuscripcionDialog(ModalBase):
    """Devuelve {meses, monto, metodo, nota} o None."""

    def __init__(self, master, monto_mensual: Decimal, cubierto_hasta: date | None):
        super().__init__(master, "Registrar pago de suscripción")
        self.monto_mensual = Decimal(str(monto_mensual or 0))
        self.cubierto_hasta = cubierto_hasta
        self._monto_tocado = False
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Registrar pago", font=theme.fuente(20, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, columnspan=2,
                                                padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text=f"Cuota mensual: {formato.moneda(self.monto_mensual)}",
                     font=theme.fuente(12), text_color=theme.TXT_MUTED).grid(
            row=1, column=0, columnspan=2, padx=24, pady=(0, 14))

        ctk.CTkLabel(self, text="Meses que paga", anchor="w",
                     font=theme.fuente(13)).grid(row=2, column=0, sticky="w",
                                                 padx=(24, 8), pady=(4, 2))
        self.seg_meses = ctk.CTkSegmentedButton(
            self, values=list(_ATAJOS_MESES), command=self._elegir_meses,
            selected_color=theme.PRIMARY, selected_hover_color=theme.PRIMARY_HOVER)
        self.seg_meses.grid(row=3, column=0, columnspan=2, sticky="ew",
                            padx=24, pady=(0, 6))

        ctk.CTkLabel(self, text="O escribí la cantidad", anchor="w",
                     font=theme.fuente(12), text_color=theme.TXT_MUTED).grid(
            row=4, column=0, sticky="w", padx=(24, 8), pady=4)
        self.ent_meses = ctk.CTkEntry(self, width=160, justify="right")
        self.ent_meses.grid(row=4, column=1, sticky="e", padx=(8, 24), pady=4)
        self.ent_meses.bind("<KeyRelease>", self._recalcular)

        ctk.CTkLabel(self, text="Monto cobrado", anchor="w",
                     font=theme.fuente(13)).grid(row=5, column=0, sticky="w",
                                                 padx=(24, 8), pady=4)
        self.ent_monto = ctk.CTkEntry(self, width=160, justify="right")
        self.ent_monto.grid(row=5, column=1, sticky="e", padx=(8, 24), pady=4)
        self.ent_monto.bind("<KeyRelease>", self._monto_editado)

        ctk.CTkLabel(self, text="Cómo pagó", anchor="w",
                     font=theme.fuente(13)).grid(row=6, column=0, sticky="w",
                                                 padx=(24, 8), pady=(10, 2))
        self.seg_metodo = ctk.CTkSegmentedButton(
            self, values=["Efectivo", "Transferencia"],
            selected_color=theme.PRIMARY, selected_hover_color=theme.PRIMARY_HOVER)
        self.seg_metodo.set("Efectivo")
        self.seg_metodo.grid(row=7, column=0, columnspan=2, sticky="ew",
                             padx=24, pady=(0, 6))

        ctk.CTkLabel(self, text="Nota (opcional)", anchor="w",
                     font=theme.fuente(13)).grid(row=8, column=0, sticky="w",
                                                 padx=(24, 8), pady=4)
        self.ent_nota = ctk.CTkEntry(self, width=240,
                                     placeholder_text="ej. transferencia del 5/8")
        self.ent_nota.grid(row=8, column=1, sticky="e", padx=(8, 24), pady=4)

        # Resultado en vivo: hasta cuándo queda cubierto con lo que se está por
        # cobrar. Es la información que de verdad importa al cargar el pago.
        self.card = ctk.CTkFrame(self, fg_color=theme.VERDE_BG, corner_radius=10)
        self.card.grid(row=9, column=0, columnspan=2, sticky="ew",
                       padx=24, pady=(14, 4))
        ctk.CTkLabel(self.card, text="Queda cubierto hasta",
                     font=theme.fuente(12), text_color=theme.TXT_MUTED).pack(
            anchor="w", padx=14, pady=(10, 0))
        self.lbl_hasta = ctk.CTkLabel(self.card, text="—",
                                      font=theme.fuente(22, "bold"),
                                      text_color=theme.VERDE)
        self.lbl_hasta.pack(anchor="w", padx=14, pady=(0, 10))

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO,
                                      font=theme.fuente(12))
        self.lbl_error.grid(row=10, column=0, columnspan=2, padx=24)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=11, column=0, columnspan=2, pady=(8, 12))
        ctk.CTkButton(cont, text="Cancelar", width=120, height=40,
                      corner_radius=10, fg_color="transparent",
                      text_color=theme.TXT_MUTED, border_width=1,
                      border_color=theme.GHOST, hover_color=theme.GHOST,
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Registrar pago", width=170, height=40,
                      corner_radius=10, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.seg_meses.set("1")
        self._elegir_meses("1")
        self.after(50, self.ent_monto.focus_set)

    # --- Interacción ---
    def _elegir_meses(self, valor: str) -> None:
        self.ent_meses.delete(0, "end")
        self.ent_meses.insert(0, valor)
        self._recalcular()

    def _monto_editado(self, _e=None) -> None:
        self._monto_tocado = True

    def _meses(self) -> int:
        try:
            return int((self.ent_meses.get() or "").strip())
        except ValueError:
            return 0

    def _recalcular(self, _e=None) -> None:
        n = self._meses()
        # El botón de atajo acompaña a lo que se escribió a mano (o se apaga).
        self.seg_meses.set(str(n) if str(n) in _ATAJOS_MESES else "")
        if not self._monto_tocado:
            self.ent_monto.delete(0, "end")
            if 1 <= n <= suscripcion.MESES_MAXIMO:
                self.ent_monto.insert(0, str(self.monto_mensual * n))
        if self.cubierto_hasta and 1 <= n <= suscripcion.MESES_MAXIMO:
            self.lbl_hasta.configure(
                text=_fecha_larga(suscripcion.sumar_meses(self.cubierto_hasta, n)))
        else:
            self.lbl_hasta.configure(text="—")

    def _confirmar(self) -> None:
        n = self._meses()
        if n < 1 or n > suscripcion.MESES_MAXIMO:
            self.lbl_error.configure(
                text=f"Los meses van de 1 a {suscripcion.MESES_MAXIMO}.")
            return
        self._aceptar({
            "meses": n,
            "monto": _dec(self.ent_monto.get()),
            "metodo": ("TRANSFERENCIA" if self.seg_metodo.get() == "Transferencia"
                       else "EFECTIVO"),
            "nota": self.ent_nota.get().strip(),
        })


class ConfigSuscripcionDialog(ModalBase):
    """Devuelve {comercio, fecha_inicio, monto_mensual, gracia_dias, datos_pago,
    estado_manual} o None."""

    _ESTADOS = {
        "Automático": "",
        "Forzar activa": suscripcion.MANUAL_ACTIVA,
        "Forzar suspendida": suscripcion.MANUAL_SUSPENDIDA,
    }

    def __init__(self, master, actual: dict):
        super().__init__(master, "Configurar suscripción")
        self.grid_columnconfigure(1, weight=1)
        est = actual.get("estado")

        ctk.CTkLabel(self, text="Configurar suscripción",
                     font=theme.fuente(20, "bold"), text_color=theme.TXT).grid(
            row=0, column=0, columnspan=2, padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text="Estos datos los ve el comercio en su pantalla.",
                     font=theme.fuente(12), text_color=theme.TXT_MUTED).grid(
            row=1, column=0, columnspan=2, padx=24, pady=(0, 14))

        self.ent_comercio = self._campo(2, "Nombre del comercio",
                                        actual.get("comercio", ""))
        self.ent_inicio = self._campo(
            3, "Primer día cobrado",
            est.fecha_inicio.strftime("%d/%m/%Y") if est and est.fecha_inicio else "",
            placeholder="dd/mm/aaaa",
            ayuda="El cobro cae ese mismo día de cada mes (si el mes no lo "
                  "tiene, el último: 31 → 28/29 de febrero).")
        self.ent_monto = self._campo(
            5, "Cuota mensual",
            str(est.monto_mensual) if est and est.monto_mensual else "")
        self.ent_gracia = self._campo(
            6, "Días de gracia antes de suspender",
            str(actual.get("gracia_dias", suscripcion.GRACIA_DIAS_DEFECTO)),
            ayuda="Cuánto se tolera el atraso ANTES de bloquear. No es cada "
                  "cuánto se cobra: eso siempre es mensual.")
        self.ent_datos = self._campo(
            8, "Datos para pagarte", actual.get("datos_pago", ""),
            placeholder="Alias / CBU / teléfono")

        ctk.CTkLabel(self, text="Estado", anchor="w",
                     font=theme.fuente(13)).grid(row=9, column=0, sticky="w",
                                                 padx=(24, 8), pady=(12, 2))
        self.seg_estado = ctk.CTkSegmentedButton(
            self, values=list(self._ESTADOS),
            selected_color=theme.PRIMARY, selected_hover_color=theme.PRIMARY_HOVER)
        actual_manual = actual.get("estado_manual", "")
        self.seg_estado.set(next((k for k, v in self._ESTADOS.items()
                                  if v == actual_manual), "Automático"))
        self.seg_estado.grid(row=10, column=0, columnspan=2, sticky="ew",
                             padx=24, pady=(0, 4))
        ctk.CTkLabel(self, text="«Forzar activa» perdona el atraso sin registrar "
                                "un pago; «forzar suspendida» corta al instante.",
                     font=theme.fuente(11), text_color=theme.TXT_MUTED,
                     wraplength=420, justify="left").grid(
            row=11, column=0, columnspan=2, sticky="w", padx=24, pady=(0, 6))

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO,
                                      font=theme.fuente(12))
        self.lbl_error.grid(row=12, column=0, columnspan=2, padx=24)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=13, column=0, columnspan=2, pady=(8, 12))
        ctk.CTkButton(cont, text="Cancelar", width=120, height=40,
                      corner_radius=10, fg_color="transparent",
                      text_color=theme.TXT_MUTED, border_width=1,
                      border_color=theme.GHOST, hover_color=theme.GHOST,
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar", width=170, height=40,
                      corner_radius=10, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.after(50, self.ent_inicio.focus_set)

    def _campo(self, fila: int, etiqueta: str, valor: str, placeholder: str = "",
               ayuda: str = ""):
        ctk.CTkLabel(self, text=etiqueta, anchor="w",
                     font=theme.fuente(13)).grid(row=fila, column=0, sticky="w",
                                                 padx=(24, 8), pady=4)
        ent = ctk.CTkEntry(self, width=240, placeholder_text=placeholder)
        if valor:
            ent.insert(0, valor)
        ent.grid(row=fila, column=1, sticky="e", padx=(8, 24), pady=4)
        if ayuda:
            ctk.CTkLabel(self, text=ayuda, anchor="w", justify="left",
                         wraplength=420, font=theme.fuente(11),
                         text_color=theme.TXT_MUTED).grid(
                row=fila + 1, column=0, columnspan=2, sticky="w",
                padx=(24, 24), pady=(0, 4))
        return ent

    def _confirmar(self) -> None:
        if not self.ent_inicio.get().strip():
            self.lbl_error.configure(text="Falta el primer día cobrado.")
            return
        self._aceptar({
            "comercio": self.ent_comercio.get().strip(),
            "fecha_inicio": self.ent_inicio.get().strip(),
            "monto_mensual": _dec(self.ent_monto.get()),
            "gracia_dias": (self.ent_gracia.get().strip()
                            or suscripcion.GRACIA_DIAS_DEFECTO),
            "datos_pago": self.ent_datos.get().strip(),
            "estado_manual": self._ESTADOS.get(self.seg_estado.get(), ""),
        })
