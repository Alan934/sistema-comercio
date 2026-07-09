"""Captura global del lector de código de barra ("pistolita").

El lector funciona como un teclado: teclea el código muy rápido y termina con
Enter. Este catcher escucha las teclas a nivel de la ventana principal para que
el escaneo funcione aunque el foco NO esté en el campo de escaneo: distingue la
ráfaga del lector (teclas muy seguidas) de la escritura humana por el tiempo
entre teclas y, al Enter, enruta el código a la vista activa.

No interfiere con los diálogos modales: son ventanas Toplevel aparte con
grab_set(), así que sus teclas nunca llegan a este bind (que está solo en la
ventana principal). Tampoco pisa el campo de escaneo dedicado: cuando ese campo
tiene el foco, su propio handler consume el Enter (return "break") y este catcher
ni se entera.
"""
import time


class ScanCatcher:
    # Máximo de segundos entre teclas para considerarlas parte de una misma
    # ráfaga del lector. La escritura humana deja huecos bastante mayores.
    INTERVALO = 0.06
    # El Enter del lector llega pegado a la última tecla; margen algo más amplio.
    INTERVALO_ENTER = 0.15
    # Mínimo de caracteres para tratar la ráfaga como un código (evita confundir
    # un par de teclas humanas rápidas con un escaneo).
    MIN_CHARS = 3

    def __init__(self, root, dispatch):
        """root: la ventana principal. dispatch(codigo): se llama con el código
        cuando se detecta un escaneo."""
        self._root = root
        self._dispatch = dispatch
        self._buffer = ""
        self._ult = 0.0
        root.bind("<KeyPress>", self._on_key, add="+")
        root.bind("<Return>", self._on_enter, add="+")
        root.bind("<KP_Enter>", self._on_enter, add="+")

    def _on_key(self, event):
        ch = event.char
        # Solo caracteres imprimibles de una sola tecla (dígitos/letras del
        # código). Ignora Enter, Tab, flechas, F2/F12, modificadores, etc.
        if len(ch) != 1 or not ch.isprintable():
            return
        ahora = time.monotonic()
        if ahora - self._ult > self.INTERVALO:
            self._buffer = ""          # hueco grande: arranca secuencia nueva
        self._buffer += ch
        self._ult = ahora

    def _on_enter(self, _event=None):
        codigo = self._buffer.strip()
        es_rafaga = (len(codigo) >= self.MIN_CHARS
                     and time.monotonic() - self._ult <= self.INTERVALO_ENTER)
        self._buffer = ""
        if not es_rafaga:
            return None
        # Limpia lo que se haya colado en el campo con foco (ej. el buscador),
        # así el código escaneado no queda escrito ni filtra la tabla.
        try:
            w = self._root.focus_get()
            if w is not None and hasattr(w, "delete"):
                w.delete(0, "end")
        except Exception:  # noqa: BLE001  (foco/widget en transición)
            pass
        self._dispatch(codigo)
        return "break"
