"""Autocompletado de productos: mientras se escribe muestra los resultados en
un desplegable debajo del campo, navegables con ↑/↓ y seleccionables con Enter
(o clic). También soporta Enter "directo" (ej. código de barra exacto).

Se engancha a un CTkEntry existente. `contenedor` es el frame sobre el que se
dibuja el desplegable (debe abarcar el área debajo del campo, para que no quede
recortado).
"""
import customtkinter as ctk

from app.services import venta_service
from app.ui import theme

_TECLAS_NAV = {"Up", "Down", "Return", "KP_Enter", "Escape", "Left", "Right",
               "Shift_L", "Shift_R", "Control_L", "Control_R", "Tab"}


class AutocompleteBuscador:
    def __init__(self, entry, contenedor, on_seleccionar,
                 on_enter_directo=None, limite: int = 8):
        self.entry = entry
        self.on_seleccionar = on_seleccionar
        self.on_enter_directo = on_enter_directo
        self.limite = limite
        self._resultados = []
        self._filas = []
        self._sel = -1
        self._visible = False

        self.drop = ctk.CTkFrame(contenedor, fg_color=theme.CARD_BG,
                                 corner_radius=8, border_width=1,
                                 border_color=theme.GHOST)

        entry.bind("<KeyRelease>", self._on_key)
        entry.bind("<Down>", self._nav_down)
        entry.bind("<Up>", self._nav_up)
        entry.bind("<Return>", self._on_enter)
        entry.bind("<Escape>", lambda _e: self._ocultar())
        entry.bind("<FocusOut>", lambda _e: self.entry.after(150, self._ocultar))

    # --- Búsqueda en vivo ---------------------------------------------------

    def _on_key(self, event) -> None:
        if event.keysym in _TECLAS_NAV:
            return
        texto = self.entry.get().strip()
        if not texto:
            self._ocultar()
            return
        # Parece un código de barra (lo escanea la pistolita): no sugerir por
        # nombre, así el Enter final hace la búsqueda por código exacta.
        if texto.isdigit() and len(texto) >= 6:
            self._ocultar()
            return
        self._resultados = venta_service.buscar_por_nombre(texto)[:self.limite]
        self._render()

    def _render(self) -> None:
        for w in self.drop.winfo_children():
            w.destroy()
        self._filas = []
        if not self._resultados:
            self._ocultar()
            return
        self._sel = 0
        for i, p in enumerate(self._resultados):
            unidad = " /kg" if p.es_pesable else ""
            texto = f"{p.nombre}"
            precio = f"${p.precio_venta:,.2f}{unidad}"
            fila = ctk.CTkButton(
                self.drop, text=f"{texto}", anchor="w", height=34,
                corner_radius=6, fg_color="transparent", text_color=theme.TXT,
                hover_color=theme.GHOST, font=theme.fuente(14),
                command=lambda idx=i: self._elegir(idx))
            fila.pack(fill="x", padx=4, pady=1)
            # Precio a la derecha, sobre el mismo botón.
            ctk.CTkLabel(fila, text=precio, font=theme.fuente(13),
                         text_color=theme.TXT_MUTED, fg_color="transparent").place(
                relx=1.0, rely=0.5, x=-10, anchor="e")
            self._filas.append(fila)
        self._resaltar()
        self._mostrar()

    def _resaltar(self) -> None:
        for i, f in enumerate(self._filas):
            activo = (i == self._sel)
            f.configure(fg_color=theme.NAV_ACTIVE_BG if activo else "transparent",
                        text_color="#FFFFFF" if activo else theme.TXT)

    def _mostrar(self) -> None:
        self.drop.place(in_=self.entry, relx=0, rely=1.0, y=2, relwidth=1.0,
                        anchor="nw")
        self.drop.lift()
        self._visible = True

    def _ocultar(self) -> None:
        if self._visible:
            self.drop.place_forget()
            self._visible = False
        self._sel = -1

    # --- Navegación ---------------------------------------------------------

    def _nav_down(self, _e):
        if not self._visible or not self._resultados:
            return None
        self._sel = (self._sel + 1) % len(self._resultados)
        self._resaltar()
        return "break"

    def _nav_up(self, _e):
        if not self._visible or not self._resultados:
            return None
        self._sel = (self._sel - 1) % len(self._resultados)
        self._resaltar()
        return "break"

    def _on_enter(self, _e):
        if self._visible and 0 <= self._sel < len(self._resultados):
            self._elegir(self._sel)
            return "break"
        self._ocultar()
        if self.on_enter_directo:
            self.on_enter_directo()
        return "break"

    def enter(self) -> None:
        """Dispara la misma acción que apretar Enter (para un botón 'Buscar')."""
        self._on_enter(None)

    def _elegir(self, idx: int) -> None:
        prod = self._resultados[idx]
        self._ocultar()
        self.on_seleccionar(prod)
