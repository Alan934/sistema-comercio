"""Auto-actualización del programa vía GitHub Releases (acceso anónimo).

Flujo:
  buscar_actualizacion() -> averigua la última release en GitHub y compara
                            versión con la actual (settings.APP_VERSION).
  aplicar_actualizacion() -> descarga el .exe nuevo al lado del actual, escribe
                             un .bat que espera el cierre de la app, reemplaza
                             el .exe y reabre. (Solo en la versión compilada.)

Windows no deja sobreescribir un .exe en uso: por eso el reemplazo lo hace el
.bat una vez que la app cerró.

IMPORTANTE — por qué NO se usa api.github.com:
  La API REST de GitHub limita a 60 consultas/hora POR IP para accesos anónimos.
  Detrás del CGNAT de muchos ISP, esa IP se comparte con cientos de usuarios, así
  que el cupo se agota con tráfico ajeno y el updater fallaba con "límite de
  consultas alcanzado". En cambio, las URL públicas de github.com que usamos acá
  (el redirect de /releases/latest y la descarga /releases/latest/download/...)
  NO están sujetas a ese límite. Así la actualización funciona siempre.

Usa solo la librería estándar (urllib), sin dependencias extra.
"""
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from config import settings

REPO = "Alan934/sistema-comercio"
# El redirect de esta URL apunta a .../releases/tag/vX.Y.Z (de ahí sale la
# versión). La descarga siempre baja el asset de la última release publicada.
LATEST_URL = f"https://github.com/{REPO}/releases/latest"
ASSET_URL = f"https://github.com/{REPO}/releases/latest/download/Kiosko.exe"
_HEADERS = {"User-Agent": "Kiosko-Updater"}
CREATE_NEW_CONSOLE = 0x00000010


class UpdaterError(Exception):
    pass


class _SinRedireccion(urllib.request.HTTPRedirectHandler):
    """No sigue el 302 de /releases/latest: así podemos leer el tag desde el
    header Location sin una request extra (y sin tocar api.github.com)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def esta_compilado() -> bool:
    """True si corre como .exe de PyInstaller (no en desarrollo)."""
    return getattr(sys, "frozen", False)


def _a_tupla(version: str) -> tuple:
    """'v0.2.0' / '0.2.0' -> (0, 2, 0) para comparar numéricamente."""
    numeros = re.findall(r"\d+", version or "")
    return tuple(int(n) for n in numeros) if numeros else (0,)


def _tag_de_location(location: str) -> str:
    """De 'https://github.com/.../releases/tag/v0.8.1' saca 'v0.8.1'."""
    return location.rstrip("/").rsplit("/", 1)[-1] if location else ""


def buscar_actualizacion() -> dict:
    """Averigua la última release leyendo el redirect de /releases/latest (sin
    api.github.com, así no hay límite de consultas). Nunca lanza: devuelve un
    dict con el resultado.
      {ok:True, hay:True, version, url}
      {ok:True, hay:False, motivo}
      {ok:False, motivo}
    """
    try:
        req = urllib.request.Request(LATEST_URL, headers=_HEADERS)
        opener = urllib.request.build_opener(_SinRedireccion)
        try:
            # Sin releases, GitHub responde 200 con una página; el 302 con el tag
            # solo aparece cuando hay una publicada.
            resp = opener.open(req, timeout=8)
            location = resp.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"ok": True, "hay": False,
                        "motivo": "Todavía no hay versiones publicadas."}
            if 300 <= e.code < 400:
                location = e.headers.get("Location", "")
            else:
                return {"ok": False, "motivo": f"GitHub respondió {e.code}."}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"ok": False, "motivo": "Sin conexión a internet."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "motivo": f"Error inesperado: {e}"}

    tag = _tag_de_location(location)
    if not tag:
        return {"ok": True, "hay": False,
                "motivo": "Todavía no hay versiones publicadas."}

    nueva = _a_tupla(tag)
    actual = _a_tupla(settings.APP_VERSION)
    if nueva <= actual:
        return {"ok": True, "hay": False,
                "motivo": f"Ya tenés la última versión (v{settings.APP_VERSION})."}
    return {"ok": True, "hay": True, "version": tag.lstrip("vV"), "url": ASSET_URL}


def _descargar(url: str, destino: Path) -> None:
    """Descarga el .exe y verifica la integridad contra el Content-Length que
    informa el servidor (no hace falta la API para saber el tamaño)."""
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        esperado = int(resp.headers.get("Content-Length") or 0)
        datos = resp.read()
    destino.write_bytes(datos)
    if esperado and destino.stat().st_size != esperado:
        destino.unlink(missing_ok=True)
        raise UpdaterError("La descarga quedó incompleta (tamaño no coincide).")


def _lanzar_swap(actual: Path, nuevo: Path) -> None:
    """Escribe y lanza el .bat que reemplaza el .exe tras cerrar la app."""
    nombre = actual.name
    bat = actual.with_name("_actualizar.bat")
    contenido = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        f"echo Actualizando {nombre}... no cierres esta ventana.\r\n"
        ":esperar\r\n"
        f'tasklist /FI "IMAGENAME eq {nombre}" 2>nul | find /I "{nombre}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto esperar\r\n"
        ")\r\n"
        f'move /Y "{nuevo}" "{actual}" >nul\r\n'
        f'start "" "{actual}"\r\n'
        'del "%~f0"\r\n'
    )
    bat.write_text(contenido, encoding="utf-8")
    subprocess.Popen(["cmd", "/c", str(bat)],
                     creationflags=CREATE_NEW_CONSOLE,
                     cwd=str(actual.parent), close_fds=True)


def aplicar_actualizacion(info: dict) -> None:
    """Descarga el .exe nuevo y deja lanzado el reemplazo. El llamador debe
    cerrar la app inmediatamente después para liberar el archivo."""
    if not esta_compilado():
        raise UpdaterError("La actualización automática solo funciona en el "
                           ".exe compilado.")
    actual = Path(sys.executable).resolve()
    nuevo = actual.with_name(f"{actual.stem}_nuevo{actual.suffix}")
    _descargar(info["url"], nuevo)
    _lanzar_swap(actual, nuevo)
