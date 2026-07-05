"""Toast: aviso breve y NO bloqueante, integrado al tema.

Reemplaza a los `messagebox.showinfo` de confirmación (p. ej. "Venta
registrada"): en vez de un cuadro gris del sistema que corta el flujo y hay
que cerrar con OK, aparece una tarjeta teal sobre la ventana y se desvanece
sola. Se coloca con `.place()` sobre la ventana raíz (no crea otra ventana →
liviano, clave por la restricción de RAM).
"""
import customtkinter as ctk

from app.ui import theme

# tipo -> (color de acento, ícono)
_ESTILOS = {
    "ok": (theme.VERDE, "✓"),
    "error": (theme.ROJO, "✕"),
    "info": (theme.ACCENT, "ℹ"),
}


def mostrar_toast(widget, mensaje: str, tipo: str = "ok",
                  duracion: int = 2600) -> None:
    """Muestra un toast sobre la ventana que contiene `widget`.

    tipo: "ok" | "error" | "info". `duracion` en milisegundos.
    """
    root = widget.winfo_toplevel()
    color, icono = _ESTILOS.get(tipo, _ESTILOS["info"])

    tarjeta = ctk.CTkFrame(root, corner_radius=14, fg_color=theme.CARD_BG,
                           border_width=2, border_color=color)
    # Franja de color a la izquierda + ícono en círculo.
    chip = ctk.CTkLabel(tarjeta, text=icono, width=34, height=34,
                        corner_radius=17, fg_color=color, text_color="#FFFFFF",
                        font=theme.fuente(16, "bold"))
    chip.grid(row=0, column=0, padx=(14, 10), pady=14)
    ctk.CTkLabel(tarjeta, text=mensaje, anchor="w", justify="left",
                 font=theme.fuente(15, "bold"), text_color=theme.TXT).grid(
        row=0, column=1, padx=(0, 20), pady=14, sticky="w")

    # Aparece sobre el borde inferior, centrado horizontalmente.
    tarjeta.place(relx=0.5, rely=0.97, anchor="s")
    tarjeta.after(duracion, tarjeta.destroy)
