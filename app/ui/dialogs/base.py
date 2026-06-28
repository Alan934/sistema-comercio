"""Base para diálogos modales con CustomTkinter.

Patrón de uso:
    resultado = MiDialogo(parent, ...).mostrar()
`mostrar()` bloquea hasta que el usuario acepta o cancela, y devuelve el
resultado (o None si canceló).
"""
import customtkinter as ctk


class ModalBase(ctk.CTkToplevel):
    def __init__(self, master, titulo: str):
        super().__init__(master)
        self.resultado = None
        self.title(titulo)
        self.resizable(False, False)
        # Se asocia a la ventana principal y bloquea el cierre por la X.
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        # Esc cancela en cualquier diálogo.
        self.bind("<Escape>", lambda _e: self._cancelar())

    def _aceptar(self, resultado) -> None:
        self.resultado = resultado
        self.grab_release()
        self.destroy()

    def _cancelar(self) -> None:
        self.resultado = None
        self.grab_release()
        self.destroy()

    def mostrar(self):
        # Centra sobre la ventana padre y toma el foco modal.
        self.update_idletasks()
        self.grab_set()
        self.wait_window()
        return self.resultado
