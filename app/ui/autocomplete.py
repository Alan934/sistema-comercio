"""Autocompletado con desplegable debajo de un CTkEntry: mientras se escribe
muestra los resultados que contienen los caracteres ingresados, navegables con
↑/↓ y seleccionables con Enter (o clic).

Se engancha a un CTkEntry existente. `contenedor` es el frame sobre el que se
dibuja el desplegable: debe abarcar el área debajo del campo para que no quede
recortado (normalmente el diálogo o la vista completa).

Hay dos variantes:
    AutocompleteBuscador  → busca productos por nombre (usado en la caja y al
                            recibir un remito). Soporta Enter "directo" para
                            códigos de barra exactos.
    AutocompleteSimple    → filtra una lista fija de textos (categorías,
                            ubicaciones, proveedores).
"""
import customtkinter as ctk

from app.core import formato

from app.services import venta_service
from app.ui import theme

_TECLAS_NAV = {"Up", "Down", "Return", "KP_Enter", "Escape", "Left", "Right",
               "Shift_L", "Shift_R", "Control_L", "Control_R", "Tab"}


class _AutocompleteBase:
    """Mecánica común del desplegable (render, navegación, mostrar/ocultar).

    Las subclases definen qué se busca (`_buscar`), cómo se muestra cada fila
    (`_texto_fila` / `_decorar_fila`), qué pasa al elegir (`_al_elegir`) y qué
    hace Enter cuando no hay nada seleccionado (`_enter_sin_seleccion`).
    """

    # Alto aproximado de cada fila (botón 34 + pady) y cuántas se ven a la vez
    # antes de que el desplegable empiece a scrollear con la rueda del mouse.
    ALTO_FILA = 37
    FILAS_VISIBLES = 8

    def __init__(self, entry, contenedor, limite: int = 8):
        self.entry = entry
        self.limite = limite
        self._resultados = []
        self._filas = []
        self._sel = -1
        self._visible = False

        # Contenedor scrollable: si hay más opciones que FILAS_VISIBLES, se
        # scrollea con la rueda del mouse en vez de recortar las de abajo.
        self.drop = ctk.CTkScrollableFrame(
            contenedor, fg_color=theme.CARD_BG, corner_radius=8,
            border_width=1, border_color=theme.GHOST)

        entry.bind("<KeyRelease>", self._on_key)
        entry.bind("<Down>", self._nav_down)
        entry.bind("<Up>", self._nav_up)
        entry.bind("<Return>", self._on_enter)
        entry.bind("<Escape>", self._on_escape)
        entry.bind("<FocusOut>", lambda _e: self.entry.after(150, self._ocultar))

    # --- Hooks de la subclase ----------------------------------------------

    def _buscar(self, texto: str) -> list:
        raise NotImplementedError

    def _mostrar_vacio(self) -> list:
        """Resultados a mostrar cuando el campo está vacío (por defecto nada)."""
        return []

    def _texto_fila(self, item) -> str:
        raise NotImplementedError

    def _decorar_fila(self, fila, item) -> None:
        pass

    def _al_elegir(self, item) -> None:
        raise NotImplementedError

    def _enter_sin_seleccion(self):
        return None

    # --- Búsqueda en vivo ---------------------------------------------------

    def _on_key(self, event) -> None:
        if event.keysym in _TECLAS_NAV:
            return
        self._actualizar()

    def _actualizar(self) -> None:
        texto = self.entry.get().strip()
        if not texto:
            self._resultados = self._mostrar_vacio()[:self.limite]
        else:
            self._resultados = self._buscar(texto)[:self.limite]
        self._render()

    def _render(self, auto_sel: bool = True) -> None:
        # Destruir solo las filas propias: el CTkScrollableFrame tiene hijos
        # internos (canvas + barra) que no hay que tocar.
        for w in self._filas:
            w.destroy()
        self._filas = []
        if not self._resultados:
            self._ocultar()
            return
        # Al escribir, se resalta la primera coincidencia (Enter la elige). Al
        # solo enfocar (auto_sel=False) no se resalta nada, así Enter no pisa el
        # valor que ya tenía el campo.
        self._sel = 0 if auto_sel else -1
        for i, item in enumerate(self._resultados):
            fila = ctk.CTkButton(
                self.drop, text=self._texto_fila(item), anchor="w", height=34,
                corner_radius=6, fg_color="transparent", text_color=theme.TXT,
                hover_color=theme.GHOST, font=theme.fuente(14),
                command=lambda idx=i: self._elegir(idx))
            fila.pack(fill="x", padx=4, pady=1)
            self._decorar_fila(fila, item)
            self._filas.append(fila)
        self._resaltar()
        self._mostrar()

    def _resaltar(self) -> None:
        for i, f in enumerate(self._filas):
            activo = (i == self._sel)
            f.configure(fg_color=theme.NAV_ACTIVE_BG if activo else "transparent",
                        text_color="#FFFFFF" if activo else theme.TXT)
        self._scroll_a_seleccion()

    def _scroll_a_seleccion(self) -> None:
        """Si se navega con las flechas más allá de lo visible, mueve el scroll
        para que la fila resaltada quede a la vista."""
        n = len(self._filas)
        if self._sel < 0 or n <= self.FILAS_VISIBLES:
            return
        try:
            self.drop._parent_canvas.yview_moveto(self._sel / n)
        except Exception:
            pass

    def _ajustar_altura(self) -> None:
        """Alto del desplegable = las filas que entren hasta el tope; el resto
        queda accesible con el scroll."""
        visibles = min(len(self._filas), self.FILAS_VISIBLES)
        self.drop.configure(height=max(1, visibles) * self.ALTO_FILA)

    def _mostrar(self) -> None:
        self._ajustar_altura()
        self.drop.place(in_=self.entry, relx=0, rely=1.0, y=2, relwidth=1.0,
                        anchor="nw")
        self.drop.lift()
        self._visible = True

    def _ocultar(self) -> None:
        if self._visible:
            self.drop.place_forget()
            self._visible = False
        self._sel = -1

    def _on_escape(self, _e):
        # Si el desplegable está abierto, Esc solo lo cierra (no propaga, para
        # no cancelar el diálogo que también escucha Esc). Si no, deja propagar.
        if self._visible:
            self._ocultar()
            return "break"
        return None

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
        return self._enter_sin_seleccion()

    def enter(self):
        """Dispara la misma acción que apretar Enter (para un botón 'Buscar')."""
        return self._on_enter(None)

    def _elegir(self, idx: int) -> None:
        item = self._resultados[idx]
        self._ocultar()
        self._al_elegir(item)


class AutocompleteBuscador(_AutocompleteBase):
    """Sugiere productos por nombre mientras se escribe.

    Por defecto busca en todo el catálogo (caja, remito). Con `buscar_fn` se
    puede acotar el universo (ej. solo cortes de carne)."""

    def __init__(self, entry, contenedor, on_seleccionar,
                 on_enter_directo=None, limite: int = 8, buscar_fn=None,
                 buscar_codigo_fn=None):
        super().__init__(entry, contenedor, limite)
        self.on_seleccionar = on_seleccionar
        self.on_enter_directo = on_enter_directo
        self._buscar_fn = buscar_fn
        self._buscar_codigo_fn = buscar_codigo_fn

    def _buscar(self, texto: str) -> list:
        # Parece un código de barra (lo escanea la pistolita): no sugerir por
        # nombre, así el Enter final hace la búsqueda por código exacta.
        if texto.isdigit() and len(texto) >= 6:
            return []
        if self._buscar_fn is not None:
            return self._buscar_fn(texto)
        return venta_service.buscar_por_nombre(texto)

    def _texto_fila(self, p) -> str:
        return p.nombre

    def _decorar_fila(self, fila, p) -> None:
        unidad = " /kg" if p.es_pesable else ""
        precio = f"{formato.moneda(p.precio_venta)}{unidad}"
        ctk.CTkLabel(fila, text=precio, font=theme.fuente(13),
                     text_color=theme.TXT_MUTED, fg_color="transparent").place(
            relx=1.0, rely=0.5, x=-10, anchor="e")

    def _al_elegir(self, p) -> None:
        self.on_seleccionar(p)

    def _on_enter(self, _e):
        # Prioridad absoluta al código de barra exacto (la pistolita). Así el
        # escaneo agrega SIEMPRE el producto correcto, sin depender de la
        # longitud del código ni de que el desplegable de nombres esté abierto
        # con una sugerencia resaltada (que si no, pisaría el escaneo).
        texto = self.entry.get().strip()
        if texto and self._buscar_codigo_fn is not None:
            prod = self._buscar_codigo_fn(texto)
            if prod is not None:
                self._ocultar()
                self.on_seleccionar(prod)
                return "break"
        # Sin código exacto: es una búsqueda por nombre normal.
        return super()._on_enter(_e)

    def _enter_sin_seleccion(self):
        if self.on_enter_directo:
            self.on_enter_directo()
        return "break"


class AutocompleteSimple(_AutocompleteBase):
    """Filtra una lista fija de textos por substring (sin distinguir mayúsculas).

    Al elegir una opción escribe su texto en el campo y llama on_seleccionar(texto)
    si se pasó. Con `sugerir_al_focus`, al enfocar el campo vacío muestra todas
    las opciones (útil cuando reemplaza a un desplegable).
    """

    def __init__(self, entry, contenedor, opciones, on_seleccionar=None,
                 limite: int = 100, sugerir_al_focus: bool = True):
        super().__init__(entry, contenedor, limite)
        self._opciones = [str(o) for o in opciones]
        self.on_seleccionar = on_seleccionar
        self._sugerir_al_focus = sugerir_al_focus
        if sugerir_al_focus:
            entry.bind("<FocusIn>", self._on_focus_in)

    def set_opciones(self, opciones) -> None:
        self._opciones = [str(o) for o in opciones]

    def _on_focus_in(self, _e) -> None:
        # Al enfocar, se muestran todas las opciones y se selecciona el texto
        # actual: así se puede elegir otra sin borrar a mano lo que ya había
        # (el primer carácter que se escriba reemplaza la selección).
        self.entry.select_range(0, "end")
        self._resultados = self._opciones[:self.limite]
        self._render(auto_sel=False)

    def _buscar(self, texto: str) -> list:
        t = texto.lower()
        return [o for o in self._opciones if t in o.lower()]

    def _mostrar_vacio(self) -> list:
        return self._opciones if self._sugerir_al_focus else []

    def _texto_fila(self, item) -> str:
        return item

    def _al_elegir(self, item) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, item)
        if self.on_seleccionar:
            self.on_seleccionar(item)
