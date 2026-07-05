"""Modal para corregir el saldo de cuenta corriente a un valor concreto.

Devuelve el nuevo saldo (Decimal >= 0) o None si se cancela.
"""
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from app.ui import theme
from app.ui.dialogs.base import ModalBase


class AjusteSaldoDialog(ModalBase):
    def __init__(self, master, nombre: str, prompt: str, saldo_texto: str,
                 saldo_actual: Decimal):
        super().__init__(master, "Ajustar saldo")

        ctk.CTkLabel(self, text=nombre, font=theme.fuente(16, "bold")).pack(
            padx=24, pady=(18, 2))
        ctk.CTkLabel(self, text=f"Saldo actual: {saldo_texto}",
                     font=theme.fuente(13), text_color=theme.TXT_MUTED).pack(padx=24)

        ctk.CTkLabel(self, text=prompt, font=theme.fuente(13)).pack(
            padx=24, pady=(12, 2))
        self.ent = ctk.CTkEntry(self, width=180, justify="center",
                                font=theme.fuente(18))
        inicial = saldo_actual if saldo_actual > 0 else Decimal("0")
        self.ent.insert(0, f"{inicial:.2f}")
        self.ent.pack(padx=24, pady=8)
        self.ent.bind("<Return>", lambda _e: self._confirmar())
        ctk.CTkLabel(self, text="Poné 0 si está al día.", font=theme.fuente(12),
                     text_color=theme.TXT_MUTED).pack()

        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.pack()

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(padx=24, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=110, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar", width=130, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)
        self._pie_atajos(bind_enter=False)
        self.after(60, self.ent.focus_set)

    def _confirmar(self) -> None:
        texto = self.ent.get().strip().replace(",", ".")
        try:
            valor = Decimal(texto)
        except InvalidOperation:
            self.lbl_error.configure(text="⚠ Valor inválido")
            return
        if valor < 0:
            self.lbl_error.configure(text="⚠ No puede ser negativo")
            return
        self._aceptar(valor)
