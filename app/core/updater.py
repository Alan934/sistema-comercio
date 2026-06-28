"""Auto-actualización del programa vía GitHub Releases (acceso anónimo).

Flujo:
  buscar_actualizacion() -> consulta la última release en GitHub y compara
                            versión con la actual (settings.APP_VERSION).
  aplicar_actualizacion() -> descarga el .exe nuevo al lado del actual, escribe
                             un .bat que espera el cierre de la app, reemplaza
                             el .exe y reabre. (Solo en la versión compilada.)

Windows no deja sobreescribir un .exe en uso: por eso el reemplazo lo hace el
.bat una vez que la app cerró.

Usa solo la librería estándar (urllib/json), sin dependencias extra.
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from config import settings

REPO = "Alan934/sistema-comercio"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Kiosko-Updater",
}
CREATE_NEW_CONSOLE = 0x00000010


class UpdaterError(Exception):
    pass


def esta_compilado() -> bool:
    """True si corre como .exe de PyInstaller (no en desarrollo)."""
    return getattr(sys, "frozen", False)


def _a_tupla(version: str) -> tuple:
    """'v0.2.0' / '0.2.0' -> (0, 2, 0) para comparar numéricamente."""
    numeros = re.findall(r"\d+", version or "")
    return tuple(int(n) for n in numeros) if numeros else (0,)


def buscar_actualizacion() -> dict:
    """Consulta GitHub. Nunca lanza: devuelve un dict con el resultado.
      {ok:True, hay:bool, version, url, tam, notas[, motivo]}
      {ok:False, motivo}
    """
    try:
        req = urllib.request.Request(API_URL, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": True, "hay": False,
                    "motivo": "Todavía no hay versiones publicadas."}
        if e.code == 403 and e.headers.get("X-RateLimit-Remaining") == "0":
            return {"ok": False,
                    "motivo": "Se alcanzó el límite de consultas a GitHub. "
                              "Probá de nuevo en un rato."}
        return {"ok": False, "motivo": f"GitHub respondió {e.code}."}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"ok": False, "motivo": "Sin conexión a internet."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "motivo": f"Error inesperado: {e}"}

    tag = data.get("tag_name", "")
    nueva = _a_tupla(tag)
    actual = _a_tupla(settings.APP_VERSION)
    asset = next((a for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith(".exe")), None)

    if nueva <= actual:
        return {"ok": True, "hay": False,
                "motivo": f"Ya tenés la última versión (v{settings.APP_VERSION})."}
    if asset is None:
        return {"ok": True, "hay": False,
                "motivo": f"Hay una versión nueva ({tag}) pero el release no "
                          "incluye el .exe."}
    return {
        "ok": True, "hay": True,
        "version": tag.lstrip("vV"),
        "url": asset["browser_download_url"],
        "tam": asset.get("size", 0),
        "notas": data.get("body", "") or "",
    }


def _descargar(url: str, destino: Path, tam_esperado: int = 0) -> None:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        destino.write_bytes(resp.read())
    if tam_esperado and destino.stat().st_size != tam_esperado:
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
    _descargar(info["url"], nuevo, info.get("tam", 0))
    _lanzar_swap(actual, nuevo)
