"""Gestor de vencimientos (lotes) de un producto.

Un perecedero puede tener varias fechas conviviendo (p. ej. stock que vence el
07/07 y stock nuevo que vence el 11/07). Acá se ven todas, se agregan y se
quitan. La alerta de Stock usa siempre la más próxima.
"""
from decimal import Decimal

import customtkinter as ctk

from app.core import formato
from app.services import stock_service
from app.ui import theme
from app.ui.dialogs import notificar
from app.ui.dialogs.base import ModalBase


class _QuitarLoteDialog(ModalBase):
    """Al quitar un lote con existencias, pregunta si además hay que descontar
    esa cantidad del stock (mercadería vencida que se retira). Devuelve
    'descontar', 'solo_fecha' o None (cancelar)."""

    def __init__(self, master, resumen: str):
        super().__init__(master, "Quitar vencimiento")
        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(padx=28, pady=(26, 8), fill="x")
        ctk.CTkLabel(cont, text="?", width=48, height=48, corner_radius=24,
                     fg_color=theme.ACCENT, text_color="#FFFFFF",
                     font=theme.fuente(24, "bold")).grid(
            row=0, column=0, rowspan=2, padx=(0, 16))
        ctk.CTkLabel(cont, text="Quitar vencimiento", anchor="w",
                     font=theme.fuente(18, "bold"), text_color=theme.TXT).grid(
            row=0, column=1, sticky="w")
        ctk.CTkLabel(
            cont, text=f"¿También querés descontar {resumen} del stock?",
            anchor="w", justify="left", wraplength=380, font=theme.fuente(14),
            text_color=theme.TXT_MUTED).grid(row=1, column=1, sticky="w",
                                             pady=(2, 0))

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=(12, 22))
        ctk.CTkButton(botones, text="Cancelar", width=110, height=40,
                      corner_radius=10, fg_color="transparent",
                      text_color=theme.TXT_MUTED, border_width=1,
                      border_color=theme.GHOST, hover_color=theme.GHOST,
                      command=self._cancelar).pack(side="left", padx=6)
        ctk.CTkButton(botones, text="No, solo la fecha", width=150, height=40,
                      corner_radius=10, fg_color="gray",
                      command=lambda: self._aceptar("solo_fecha")).pack(
            side="left", padx=6)
        ctk.CTkButton(botones, text="Sí, descontar", width=150, height=40,
                      corner_radius=10, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=lambda: self._aceptar("descontar")).pack(
            side="left", padx=6)
        self._activar_enter()

    def _confirmar(self):  # Enter = la acción principal (descontar)
        self._aceptar("descontar")


def _fecha_es(iso: str | None) -> str:
    """ISO (YYYY-MM-DD) -> dd/mm/aaaa; si es None o no parsea, texto neutro."""
    if not iso:
        return "sin fecha"
    try:
        a, m, d = iso.split("-")
        return f"{d}/{m}/{a}"
    except ValueError:
        return iso


class VencimientosDialog(ModalBase):
    def __init__(self, master, producto_id: str, nombre: str,
                 es_pesable: bool = False):
        super().__init__(master, "Vencimientos")
        self.producto_id = producto_id
        self._unidad = " kg" if es_pesable else ""

        ctk.CTkLabel(self, text="Vencimientos", font=theme.fuente(20, "bold"),
                     text_color=theme.TXT).pack(padx=26, pady=(22, 0), anchor="w")
        ctk.CTkLabel(self, text=nombre, font=theme.fuente(14),
                     text_color=theme.TXT_MUTED).pack(padx=26, anchor="w")

        self.lista = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                            width=420, height=260)
        self.lista.pack(padx=20, pady=(12, 6), fill="both", expand=True)
        self.lista.grid_columnconfigure(0, weight=1)

        # --- Alta de un lote nuevo ---
        alta = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=10)
        alta.pack(padx=20, pady=(0, 8), fill="x")
        ctk.CTkLabel(alta, text="Agregar fecha", font=theme.fuente(13, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, columnspan=3,
                                                sticky="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(alta, text="Vence", font=theme.fuente(12),
                     text_color=theme.TXT_MUTED).grid(row=1, column=0, padx=(12, 4),
                                                      pady=(0, 12), sticky="w")
        self.ent_fecha = ctk.CTkEntry(alta, width=120, placeholder_text="dd/mm/aaaa")
        self.ent_fecha.grid(row=1, column=1, padx=4, pady=(0, 12))
        ctk.CTkLabel(alta, text="Cant.", font=theme.fuente(12),
                     text_color=theme.TXT_MUTED).grid(row=1, column=2, padx=(12, 4),
                                                      pady=(0, 12), sticky="w")
        self.ent_cant = ctk.CTkEntry(alta, width=80, placeholder_text="0")
        self.ent_cant.grid(row=1, column=3, padx=4, pady=(0, 12))
        ctk.CTkButton(alta, text="Agregar", width=100, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._agregar).grid(row=1, column=4, padx=12,
                                                  pady=(0, 12))
        self.ent_fecha.bind("<Return>", lambda _e: self._agregar())
        self.ent_cant.bind("<Return>", lambda _e: self._agregar())

        ctk.CTkButton(self, text="Cerrar", width=160, height=42, corner_radius=10,
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._cancelar).pack(pady=(0, 20))

        self.after(60, self.ent_fecha.focus_set)
        self._refrescar()

    # --- Datos --------------------------------------------------------------

    def _refrescar(self) -> None:
        for w in self.lista.winfo_children():
            w.destroy()
        lotes = stock_service.listar_lotes(self.producto_id)
        if not lotes:
            ctk.CTkLabel(self.lista, text="Sin fechas de vencimiento cargadas.",
                         font=theme.fuente(14), text_color=theme.TXT_MUTED).pack(
                pady=30)
            return
        for lote in lotes:
            self._fila(lote)

    def _fila(self, lote: dict) -> None:
        dias = lote["dias_restantes"]
        if dias is None:
            detalle, color = "", theme.TXT_MUTED
        elif dias < 0:
            detalle = f"vencido hace {-dias} día{'s' if dias != -1 else ''}"
            color = theme.ROJO
        elif dias == 0:
            detalle, color = "vence hoy", theme.ROJO
        else:
            detalle = f"en {dias} día{'s' if dias != 1 else ''}"
            color = theme.BADGE_KG_TXT if dias <= 7 else theme.VERDE

        f = ctk.CTkFrame(self.lista, fg_color=theme.ROW_ALT, corner_radius=10)
        f.pack(fill="x", pady=3)
        f.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(f, width=5, height=40, corner_radius=3, fg_color=color).grid(
            row=0, column=0, rowspan=2, padx=(8, 12), pady=8)
        ctk.CTkLabel(f, text=_fecha_es(lote["fecha_vencimiento"]), anchor="w",
                     font=theme.fuente(15, "bold"), text_color=theme.TXT).grid(
            row=0, column=1, sticky="w", pady=(8, 0))
        sub = f"Cantidad {formato.numero(lote['cantidad'])}{self._unidad}"
        if detalle:
            sub += f"  ·  {detalle}"
        ctk.CTkLabel(f, text=sub, anchor="w", font=theme.fuente(12),
                     text_color=theme.TXT_MUTED).grid(row=1, column=1, sticky="w",
                                                      pady=(0, 8))
        ctk.CTkButton(f, text="🗑  Quitar", width=90, height=30, corner_radius=8,
                      font=theme.fuente(12), fg_color="transparent",
                      text_color=theme.ROJO, hover_color=theme.GHOST,
                      command=lambda lid=lote["id"], c=lote["cantidad"]:
                          self._quitar(lid, c)).grid(
            row=0, column=2, rowspan=2, padx=10)

    # --- Acciones -----------------------------------------------------------

    def _agregar(self) -> None:
        try:
            stock_service.agregar_lote(self.producto_id, self.ent_fecha.get(),
                                       self.ent_cant.get())
        except stock_service.StockError as e:
            notificar.error(self, "No se pudo agregar", str(e))
            return
        self.ent_fecha.delete(0, "end")
        self.ent_cant.delete(0, "end")
        self._refrescar()
        self.ent_fecha.focus_set()

    def _quitar(self, lote_id: str, cantidad) -> None:
        # Si el lote tiene existencias, ofrecemos descontarlas del stock (la
        # mercadería vencida se retira); si no, se quita la fecha sin más.
        descontar = False
        if Decimal(str(cantidad)) > 0:
            resumen = f"{formato.numero(cantidad)}{self._unidad}"
            opcion = _QuitarLoteDialog(self, resumen).mostrar()
            if opcion is None:
                return  # canceló: no se toca nada
            descontar = opcion == "descontar"
        stock_service.eliminar_lote(lote_id, descontar_stock=descontar)
        self._refrescar()
