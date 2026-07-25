"""Modal con la lista de PLU y precios que hay que dejar cargados en la balanza.

La balanza etiquetadora NO se sincroniza con el sistema (solo lo hace con el
software propietario de Systel), así que el precio vive en los dos lados y hay
que emparejarlos a mano. Este modal es la lista para ir a hacerlo.

Se abre en dos momentos:
  - Justo después de confirmar una pieza, con lo que cambió en ese despiece
    (`ListaBalanzaDialog(master, items, sin_plu=..., tras_despiece=True)`).
  - Desde Stock, con TODO lo que está cargado en la balanza, para repasar.

Cada item es un dict: {"nombre", "plu", "precio"} y, si viene de un despiece,
además {"precio_anterior", "es_nuevo", "cambio"}.
"""
import customtkinter as ctk

from app.core import formato

from app.ui import theme
from app.ui.dialogs.base import ModalBase


class ListaBalanzaDialog(ModalBase):
    def __init__(self, master, items: list[dict], sin_plu: list[str] | None = None,
                 tras_despiece: bool = False):
        super().__init__(master, "Precios para la balanza")
        sin_plu = sin_plu or []
        # Tras un despiece interesan primero los que cambiaron de precio: son
        # los que hay que ir a tocar sí o sí.
        cambiaron = [i for i in items if i.get("cambio") or i.get("es_nuevo")]
        resto = [i for i in items if i not in cambiaron]

        ctk.CTkLabel(self, text="Precios para la balanza",
                     font=theme.fuente(20, "bold"), text_color=theme.TXT).pack(
            padx=26, pady=(22, 4), anchor="w")

        if tras_despiece and cambiaron:
            bajada = (f"{len(cambiaron)} corte(s) quedaron con otro precio. "
                      "Cargalos igual en la balanza para que las etiquetas "
                      "coincidan con el sistema.")
        elif tras_despiece:
            bajada = ("Ningún precio cambió: la balanza ya debería estar bien.")
        else:
            bajada = ("Así tiene que estar cargada la balanza. Si algún precio "
                      "no coincide, el stock se va a ir desviando.")
        ctk.CTkLabel(self, text=bajada, font=theme.fuente(13), justify="left",
                     wraplength=460, text_color=theme.TXT_MUTED).pack(
            padx=26, anchor="w")

        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                        width=470, height=340)
        cuerpo.pack(padx=20, pady=14, fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=1)

        if not items and not sin_plu:
            ctk.CTkLabel(cuerpo,
                         text="Todavía no hay ningún corte con PLU de balanza.\n"
                              "Asignáselos desde Stock o al cargar el despiece.",
                         font=theme.fuente(14), text_color=theme.TXT_MUTED,
                         justify="center").pack(pady=60)

        if cambiaron:
            self._seccion(cuerpo, "PONER ESTE PRECIO EN LA BALANZA",
                          theme.BADGE_KG_TXT)
            for i in cambiaron:
                self._fila(cuerpo, i, theme.BADGE_KG_TXT)
        if resto:
            self._seccion(cuerpo,
                          "SIN CAMBIOS" if tras_despiece else "CARGADOS EN LA BALANZA",
                          theme.VERDE)
            for i in resto:
                self._fila(cuerpo, i, theme.VERDE)

        if sin_plu:
            self._seccion(cuerpo, "SIN PLU · NO SE PUEDEN ESCANEAR", theme.ROJO)
            for nombre in sin_plu:
                f = ctk.CTkFrame(cuerpo, fg_color=theme.CARD_BG, corner_radius=10)
                f.pack(fill="x", pady=3)
                f.grid_columnconfigure(1, weight=1)
                ctk.CTkFrame(f, width=5, height=42, corner_radius=3,
                             fg_color=theme.ROJO).grid(row=0, column=0, rowspan=2,
                                                       padx=(8, 12), pady=8)
                ctk.CTkLabel(f, text=nombre, anchor="w",
                             font=theme.fuente(15, "bold"),
                             text_color=theme.TXT).grid(row=0, column=1,
                                                        sticky="w", pady=(8, 0))
                ctk.CTkLabel(f, text="Asignale un PLU desde Stock para poder "
                                     "escanear su etiqueta",
                             anchor="w", font=theme.fuente(13),
                             text_color=theme.TXT_MUTED).grid(
                    row=1, column=1, sticky="w", pady=(0, 8))

        ctk.CTkButton(self, text="Entendido", width=160, height=42,
                      corner_radius=10, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._cancelar).pack(pady=(0, 22))

    def _seccion(self, parent, texto, color) -> None:
        ctk.CTkLabel(parent, text=texto, anchor="w",
                     font=theme.fuente(12, "bold"), text_color=color).pack(
            fill="x", pady=(12, 4))

    def _fila(self, parent, item: dict, color) -> None:
        f = ctk.CTkFrame(parent, fg_color=theme.CARD_BG, corner_radius=10)
        f.pack(fill="x", pady=3)
        f.grid_columnconfigure(2, weight=1)
        ctk.CTkFrame(f, width=5, height=46, corner_radius=3, fg_color=color).grid(
            row=0, column=0, rowspan=2, padx=(8, 10), pady=8)
        # El PLU es lo que se tipea en la balanza: va grande y primero.
        ctk.CTkLabel(f, text=f"PLU {item['plu']}", width=76, anchor="w",
                     font=theme.fuente(15, "bold"), text_color=color).grid(
            row=0, column=1, rowspan=2, padx=(0, 10))
        ctk.CTkLabel(f, text=item["nombre"], anchor="w",
                     font=theme.fuente(15, "bold"), text_color=theme.TXT).grid(
            row=0, column=2, sticky="w", pady=(8, 0))

        precio = formato.moneda(item["precio"])
        anterior = item.get("precio_anterior")
        if item.get("es_nuevo"):
            detalle = f"{precio} por kg   ·   corte nuevo"
        elif item.get("cambio") and anterior is not None:
            detalle = (f"{formato.moneda(anterior)}  →  {precio} por kg")
        else:
            detalle = f"{precio} por kg"
        ctk.CTkLabel(f, text=detalle, anchor="w", font=theme.fuente(13),
                     text_color=theme.TXT_MUTED).grid(row=1, column=2, sticky="w",
                                                      pady=(0, 8))
