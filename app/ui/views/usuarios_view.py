"""Vista de Usuarios (solo admin): listar, crear empleados y desactivar."""
from tkinter import messagebox

import customtkinter as ctk

from app.services import usuario_service
from app.ui import theme
from app.ui.dialogs.usuario_dialog import UsuarioDialog


class UsuariosView(ctk.CTkFrame):
    def __init__(self, master, usuario_actual):
        super().__init__(master, fg_color="transparent")
        self.usuario_actual = usuario_actual
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Usuarios", font=theme.fuente(24, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Nuevo empleado", width=160, height=40,
                      corner_radius=10, font=theme.fuente(14),
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._nuevo).grid(row=0, column=2)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=28)
        for col, (txt, w) in enumerate(
                [("Usuario", 260), ("Rol", 180), ("", 140)]):
            ctk.CTkLabel(header, text=txt, width=w, anchor="w",
                         font=theme.fuente(12, "bold"),
                         text_color=theme.TXT_MUTED).grid(row=0, column=col, padx=4)

        self.tabla = ctk.CTkScrollableFrame(self, fg_color=theme.CARD_BG,
                                            corner_radius=12)
        self.tabla.grid(row=2, column=0, sticky="nsew", padx=20, pady=(6, 18))
        self.tabla.grid_columnconfigure(0, weight=1)

    def al_mostrar(self) -> None:
        self._recargar()

    def _recargar(self) -> None:
        for w in self.tabla.winfo_children():
            w.destroy()
        for u in usuario_service.listar():
            f = ctk.CTkFrame(self.tabla, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=2)
            rol = "Administrador" if u.es_admin else "Empleado"
            ctk.CTkLabel(f, text=u.username, width=260, anchor="w",
                         font=theme.fuente(15), text_color=theme.TXT).grid(
                row=0, column=0, padx=4)
            ctk.CTkLabel(f, text=rol, width=180, anchor="w",
                         font=theme.fuente(13), text_color=theme.TXT_MUTED).grid(
                row=0, column=1, padx=4)
            if u.id != self.usuario_actual.id:
                ctk.CTkButton(f, text="Desactivar", width=110, height=30,
                              corner_radius=8, font=theme.fuente(13),
                              fg_color="transparent", text_color=theme.ROJO,
                              hover_color=theme.GHOST,
                              command=lambda uid=u.id, n=u.username:
                              self._desactivar(uid, n)).grid(row=0, column=2, padx=4)
            else:
                ctk.CTkLabel(f, text="(vos)", width=110, anchor="center",
                             text_color=theme.TXT_MUTED).grid(row=0, column=2, padx=4)

    def _nuevo(self) -> None:
        datos = UsuarioDialog(self).mostrar()
        if datos is None:
            return
        try:
            usuario_service.crear_empleado(datos["username"], datos["password"])
        except usuario_service.UsuarioError as e:
            messagebox.showerror("No se pudo crear", str(e))
            return
        self._recargar()

    def _desactivar(self, usuario_id: str, nombre: str) -> None:
        if not messagebox.askyesno(
                "Desactivar usuario",
                f"¿Desactivar a “{nombre}”? No podrá volver a iniciar sesión."):
            return
        usuario_service.desactivar(usuario_id)
        self._recargar()
