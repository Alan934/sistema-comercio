"""Gestión de categorías: crear/editar categorías y su margen de ganancia.

CategoriaForm: formulario de una categoría (nombre + margen).
CategoriasManager: lista de categorías con su margen y acceso a crear/editar.
"""
from decimal import Decimal, InvalidOperation
from tkinter import messagebox

import customtkinter as ctk

from app.services import categoria_service
from app.ui import theme
from app.ui.dialogs.base import ModalBase


class CategoriaForm(ModalBase):
    """Alta/edición de una categoría. Devuelve {nombre, margen_pct} o None."""

    def __init__(self, master, categoria=None):
        super().__init__(master, "Editar categoría" if categoria
                         else "Nueva categoría")
        ctk.CTkLabel(self, text="Nombre", anchor="w").grid(
            row=0, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_nombre = ctk.CTkEntry(self, width=240)
        if categoria:
            self.ent_nombre.insert(0, categoria.nombre)
        self.ent_nombre.grid(row=0, column=1, padx=(8, 20), pady=6)

        ctk.CTkLabel(self, text="Margen % (opcional)", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_margen = ctk.CTkEntry(self, width=240)
        if categoria and categoria.margen_pct is not None:
            self.ent_margen.insert(0, str(categoria.margen_pct))
        self.ent_margen.grid(row=1, column=1, padx=(8, 20), pady=6)
        ctk.CTkLabel(self, text="Vacío = sin margen por defecto.",
                     text_color=theme.TXT_MUTED, font=theme.fuente(12)).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=20)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="orange")
        self.lbl_error.grid(row=3, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=4, column=0, columnspan=2, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Guardar", width=140, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)
        self.after(50, self.ent_nombre.focus_set)

    def _confirmar(self) -> None:
        nombre = self.ent_nombre.get().strip()
        if not nombre:
            self.lbl_error.configure(text="⚠ El nombre es obligatorio")
            return
        mtxt = self.ent_margen.get().strip().replace(",", ".")
        margen = None
        if mtxt:
            try:
                margen = Decimal(mtxt)
                if margen < 0:
                    raise InvalidOperation
            except InvalidOperation:
                self.lbl_error.configure(text="⚠ Margen inválido")
                return
        self._aceptar({"nombre": nombre, "margen_pct": margen})


class CategoriasManager(ModalBase):
    """Lista de categorías con su margen; crear y editar."""

    def __init__(self, master):
        super().__init__(master, "Categorías")
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", padx=16, pady=(16, 6))
        cab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cab, text="Categorías y su margen de ganancia",
                     font=theme.fuente(15, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(cab, text="Nueva categoría", width=150,
                      fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                      command=self._nueva).grid(row=0, column=1)

        self.lista = ctk.CTkScrollableFrame(self, width=440, height=320,
                                            fg_color=theme.CARD_BG, corner_radius=12)
        self.lista.pack(padx=16, pady=(0, 8), fill="both", expand=True)
        self.lista.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(self, text="Cerrar", width=120, fg_color="gray",
                      command=self._cancelar).pack(pady=(0, 16))

        self.after(60, self._recargar)

    def _recargar(self) -> None:
        for w in self.lista.winfo_children():
            w.destroy()
        categorias = categoria_service.listar_activas()
        if not categorias:
            ctk.CTkLabel(self.lista, text="Todavía no hay categorías.",
                         text_color=theme.TXT_MUTED).pack(pady=30)
            return
        for cat in categorias:
            f = ctk.CTkFrame(self.lista, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=3)
            f.grid_columnconfigure(0, weight=1)
            margen = f"{cat.margen_pct}%" if cat.margen_pct is not None else "sin margen"
            ctk.CTkLabel(f, text=cat.nombre, anchor="w",
                         font=theme.fuente(15)).grid(row=0, column=0, sticky="w", padx=4)
            ctk.CTkLabel(f, text=margen, width=110, anchor="e",
                         text_color=theme.TXT_MUTED).grid(row=0, column=1, padx=4)
            ctk.CTkButton(f, text="Editar", width=70, height=30,
                          fg_color="transparent", text_color=theme.ACCENT,
                          hover_color=theme.GHOST,
                          command=lambda c=cat: self._editar(c)).grid(
                row=0, column=2, padx=4)

    def _nueva(self) -> None:
        datos = CategoriaForm(self).mostrar()
        if datos is None:
            return
        try:
            categoria_service.crear(datos["nombre"], datos["margen_pct"])
        except categoria_service.CategoriaError as e:
            messagebox.showerror("No se pudo crear", str(e))
            return
        self._recargar()

    def _editar(self, categoria) -> None:
        datos = CategoriaForm(self, categoria=categoria).mostrar()
        if datos is None:
            return
        try:
            categoria_service.actualizar(categoria.id, datos["nombre"],
                                         datos["margen_pct"])
        except categoria_service.CategoriaError as e:
            messagebox.showerror("No se pudo guardar", str(e))
            return
        self._recargar()
