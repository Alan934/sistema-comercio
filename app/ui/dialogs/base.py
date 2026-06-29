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
        # Se oculta hasta estar centrada (evita el parpadeo arriba a la izquierda).
        self.withdraw()
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

    def _activar_enter(self) -> None:
        """Permite confirmar el formulario con Enter (Esc ya cancela)."""
        if hasattr(self, "_confirmar"):
            self.bind("<Return>", lambda _e: self._confirmar())
            self.bind("<KP_Enter>", lambda _e: self._confirmar())

    def _pie_atajos(self, grid_row: int | None = None, bind_enter: bool = True):
        """Agrega la nota 'Enter para confirmar · Esc para cancelar' y, si
        bind_enter, activa el Enter. grid_row para layouts con grid; None usa pack."""
        if bind_enter:
            self._activar_enter()
        lbl = ctk.CTkLabel(self, text="Enter para confirmar  ·  Esc para cancelar",
                           text_color=("gray45", "gray60"))
        if grid_row is not None:
            lbl.grid(row=grid_row, column=0, columnspan=2, pady=(0, 12))
        else:
            lbl.pack(pady=(0, 12))
        return lbl

    def _centrar(self) -> None:
        """Posiciona la ventana en el centro de la pantalla según su tamaño."""
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = max(0, (self.winfo_screenwidth() - w) // 2)
        y = max(0, (self.winfo_screenheight() - h) // 2)
        self.geometry(f"+{x}+{y}")

    def mostrar(self):
        # Centra en pantalla, se muestra y toma el foco modal.
        self._centrar()
        self.deiconify()
        self.grab_set()
        self.wait_window()
        return self.resultado
