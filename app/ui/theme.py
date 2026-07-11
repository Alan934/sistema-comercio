"""Sistema de diseño central: paleta, tipografía, espaciados y preferencias.

Acento: verde azulado (teal). Los colores que van sobre superficies que cambian
con el modo claro/oscuro se definen como tuplas (claro, oscuro) — CustomTkinter
elige el que corresponde. El sidebar es siempre teal oscuro con texto claro.
"""
import json

import customtkinter as ctk

from config import settings

# --- Marca / sidebar (siempre teal oscuro, texto claro) --------------------
SIDEBAR_BG = "#0F6E56"
NAV_TXT = "#E1F5EE"
NAV_TXT_INACT = "#9FE1CB"
NAV_ACTIVE_BG = "#0B5A47"
NAV_HOVER = "#15805F"
BRAND_MARK_BG = "#E1F5EE"
BRAND_MARK_FG = "#0F6E56"

# --- Acento / botón primario -----------------------------------------------
PRIMARY = "#0F6E56"
PRIMARY_HOVER = "#1D9E75"
ACCENT = "#1D9E75"

# --- Superficies (claro, oscuro) -------------------------------------------
APP_BG = ("#F4F6F5", "#1A1A1A")
CARD_BG = ("#FFFFFF", "#2B2B2B")
GHOST = ("#E6E8E7", "#3A3A3A")
# Fila alterna en tablas (rayado zebra sutil sobre CARD_BG)
ROW_ALT = ("#F5F7F6", "#333333")

# Botón secundario "ghost" (contorno con texto de acento). En modo claro lleva
# un tinte teal suave y un borde marcado para despegarse del fondo del mismo
# color; en oscuro se mantiene transparente con borde sutil como antes.
GHOST_BTN_BG = ("#E6F4EE", "#233530")
GHOST_BTN_BORDER = ("#8FD0BA", "#3A5049")
GHOST_BTN_HOVER = ("#D3EBE1", "#2C4038")

# --- Texto -----------------------------------------------------------------
TXT = ("#1A1A1A", "#F0F0F0")
TXT_MUTED = ("#6B7280", "#9AA0A6")

# --- Semánticos / badges ----------------------------------------------------
VERDE = ("#1B8A3D", "#4CC76A")
ROJO = ("#C0392B", "#F1707A")
# Fondos suaves para banners/estados (tinte claro, tinte oscuro)
VERDE_BG = ("#E4F5E9", "#173D24")
ROJO_BG = ("#FCEAE8", "#3D1A17")
BADGE_BG = ("#E6F1FB", "#143A5A")
BADGE_TXT = ("#185FA5", "#85B7EB")
BADGE_KG_BG = ("#FAEEDA", "#4A3208")
BADGE_KG_TXT = ("#854F0B", "#EF9F27")

# --- Espaciado --------------------------------------------------------------
PAD = 16
GAP = 8

# --- Paleta para gráficos (tonos medios, legibles en claro y oscuro) --------
CHART_PALETTE = ["#1D9E75", "#378ADD", "#EF9F27", "#7F77DD", "#D85A30", "#639922"]


_FUENTE_CACHE: dict = {}


def fuente(tam: int = 14, peso: str = "normal") -> ctk.CTkFont:
    """Devuelve una CTkFont reutilizable (cacheada). Llamar siempre después de
    que exista la ventana raíz.

    Antes se creaba una CTkFont NUEVA en cada llamada; como cada fila de una
    tabla la pide varias veces, dibujar cientos de filas creaba miles de fuentes
    y congelaba la app. Un CTkFont se puede compartir entre muchos widgets, así
    que lo cacheamos por (tamaño, peso). La cache se indexa además por la ventana
    raíz actual: el flujo login->app recrea la raíz (CTk nuevo) y una fuente
    atada a la raíz vieja no debe reutilizarse."""
    import tkinter
    clave = (id(tkinter._default_root), tam, peso)
    f = _FUENTE_CACHE.get(clave)
    if f is None:
        f = ctk.CTkFont(size=tam, weight=peso)
        _FUENTE_CACHE[clave] = f
    return f


# --- Preferencia de apariencia (persistida) --------------------------------
_PREF = settings.DATA_DIR / "preferencias.json"


def cargar_apariencia() -> str:
    try:
        return json.loads(_PREF.read_text(encoding="utf-8")).get("apariencia", "light")
    except Exception:
        return "light"


def guardar_apariencia(modo: str) -> None:
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _PREF.write_text(json.dumps({"apariencia": modo}), encoding="utf-8")
    except Exception:
        pass
