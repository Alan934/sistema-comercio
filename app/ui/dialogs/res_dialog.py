"""Modal para dar de alta una res (entera o media) a despiezar.

El costo se puede cargar por kg o por el total pagado por todos los kilos; el
sistema calcula el otro. Devuelve un dict listo para despiece_service.crear_res
(siempre con costo_por_kg ya resuelto), o None si se cancela:
    {"descripcion", "proveedor_id", "peso_total", "costo_por_kg",
     "margen_pct", "condicion"}
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import customtkinter as ctk

from app.models.res import CONTADO, CUENTA_CORRIENTE
from app.services import proveedor_service
from app.ui import theme
from app.ui.autocomplete import AutocompleteSimple
from app.ui.dialogs.base import ModalBase

CENTAVOS = Decimal("0.01")
POR_KG = "Costo por kg"
POR_TOTAL = "Costo total"


def _num(texto):
    """Texto (acepta coma) -> Decimal >= 0, o None si es inválido/vacío."""
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        v = Decimal(texto)
    except InvalidOperation:
        return None
    return v if v >= 0 else None


class ResDialog(ModalBase):
    def __init__(self, master):
        super().__init__(master, "Nueva res")
        self._mapa_prov = {p.nombre: p.id for p in proveedor_service.listar_activos()}
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Nueva res", font=theme.fuente(18, "bold"),
                     text_color=theme.TXT).grid(row=0, column=0, columnspan=2,
                                                padx=20, pady=(18, 12))

        ctk.CTkLabel(self, text="Descripción", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_desc = ctk.CTkEntry(
            self, width=260, placeholder_text="Ej: Media res novillo, res entera…")
        self.ent_desc.grid(row=1, column=1, padx=(8, 20), pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Proveedor", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_prov = ctk.CTkEntry(self, width=260, placeholder_text="Opcional…")
        self.ent_prov.grid(row=2, column=1, padx=(8, 20), pady=6, sticky="ew")
        self._auto_prov = AutocompleteSimple(
            self.ent_prov, self, list(self._mapa_prov.keys()))

        ctk.CTkLabel(self, text="Peso total (kg)", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_peso = ctk.CTkEntry(self, width=260)
        self.ent_peso.grid(row=3, column=1, padx=(8, 20), pady=6, sticky="ew")
        self.ent_peso.bind("<KeyRelease>", self._recalcular)

        # Cómo se carga el costo: por kg o por el total de todos los kilos.
        ctk.CTkLabel(self, text="Cargar el costo", anchor="w").grid(
            row=4, column=0, sticky="w", padx=(20, 8), pady=6)
        self.seg_modo = ctk.CTkSegmentedButton(
            self, values=[POR_KG, POR_TOTAL],
            selected_color=theme.PRIMARY, selected_hover_color=theme.PRIMARY_HOVER,
            command=lambda _v: self._cambiar_modo())
        self.seg_modo.set(POR_KG)
        self.seg_modo.grid(row=4, column=1, padx=(8, 20), pady=6, sticky="w")

        self.lbl_costo = ctk.CTkLabel(self, text=POR_KG, anchor="w")
        self.lbl_costo.grid(row=5, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_costo = ctk.CTkEntry(self, width=260)
        self.ent_costo.grid(row=5, column=1, padx=(8, 20), pady=6, sticky="ew")
        self.ent_costo.bind("<KeyRelease>", self._recalcular)

        ctk.CTkLabel(self, text="Margen % (opcional)", anchor="w").grid(
            row=6, column=0, sticky="w", padx=(20, 8), pady=6)
        self.ent_margen = ctk.CTkEntry(
            self, width=260, placeholder_text="También se puede poner por pieza o corte")
        self.ent_margen.grid(row=6, column=1, padx=(8, 20), pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Condición", anchor="w").grid(
            row=7, column=0, sticky="w", padx=(20, 8), pady=6)
        self.seg_cond = ctk.CTkSegmentedButton(
            self, values=["Contado", "Cuenta corriente"],
            selected_color=theme.PRIMARY, selected_hover_color=theme.PRIMARY_HOVER)
        self.seg_cond.set("Contado")
        self.seg_cond.grid(row=7, column=1, padx=(8, 20), pady=6, sticky="w")

        self.lbl_calc = ctk.CTkLabel(self, text="", font=theme.fuente(14, "bold"),
                                     text_color=theme.ACCENT)
        self.lbl_calc.grid(row=8, column=0, columnspan=2, padx=20, pady=(6, 0))
        self.lbl_error = ctk.CTkLabel(self, text="", text_color=theme.ROJO)
        self.lbl_error.grid(row=9, column=0, columnspan=2, padx=20)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.grid(row=10, column=0, columnspan=2, pady=(8, 18))
        ctk.CTkButton(cont, text="Cancelar", width=120, fg_color="gray",
                      command=self._cancelar).pack(side="left", padx=8)
        ctk.CTkButton(cont, text="Crear res", width=150, fg_color=theme.PRIMARY,
                      hover_color=theme.PRIMARY_HOVER,
                      command=self._confirmar).pack(side="left", padx=8)

        self._pie_atajos(grid_row=99)
        self.after(60, self.ent_peso.focus_set)

    def _por_total(self) -> bool:
        return self.seg_modo.get() == POR_TOTAL

    def _costo_por_kg(self):
        """Resuelve el costo por kg según el modo elegido (o None si falta dato)."""
        peso, costo = _num(self.ent_peso.get()), _num(self.ent_costo.get())
        if peso is None or costo is None or peso <= 0:
            return None
        if self._por_total():
            return (costo / peso).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        return costo

    def _cambiar_modo(self):
        self.lbl_costo.configure(
            text="Costo total (por todos los kg)" if self._por_total() else POR_KG)
        self._recalcular()

    def _recalcular(self, _e=None):
        if self.lbl_error.cget("text"):
            self.lbl_error.configure(text="")   # corregir un campo borra el error
        peso, costo = _num(self.ent_peso.get()), _num(self.ent_costo.get())
        if peso is None or costo is None or peso <= 0:
            self.lbl_calc.configure(text="")
            return
        if self._por_total():
            pk = (costo / peso).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
            self.lbl_calc.configure(text=f"→ Costo por kg: ${pk:,.2f}")
        else:
            total = (peso * costo).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
            self.lbl_calc.configure(text=f"→ Costo total de la res: ${total:,.2f}")

    def _confirmar(self):
        peso = _num(self.ent_peso.get())
        if peso is None or peso <= 0:
            self.lbl_error.configure(text="⚠ Peso inválido (tiene que ser > 0)")
            return
        pk = self._costo_por_kg()
        if pk is None:
            self.lbl_error.configure(text="⚠ Costo inválido")
            return
        cond = (CUENTA_CORRIENTE if self.seg_cond.get() == "Cuenta corriente"
                else CONTADO)
        prov_txt = self.ent_prov.get().strip()
        prov_id = self._mapa_prov.get(prov_txt)
        if prov_txt and prov_id is None:
            self.lbl_error.configure(
                text="⚠ Elegí un proveedor de la lista o dejalo vacío")
            return
        if cond == CUENTA_CORRIENTE and prov_id is None:
            self.lbl_error.configure(text="⚠ Para cuenta corriente elegí un proveedor")
            return
        self._aceptar({
            "descripcion": self.ent_desc.get().strip() or "Res",
            "proveedor_id": prov_id,
            "peso_total": self.ent_peso.get().strip(),
            "costo_por_kg": str(pk),
            "margen_pct": self.ent_margen.get().strip() or None,
            "condicion": cond,
        })
