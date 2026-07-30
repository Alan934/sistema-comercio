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
import os
import re
import socket
import ssl
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

# Variables que el bootloader de PyInstaller le pasa a sus procesos hijos. Hay
# que sacarlas antes de relanzar el .exe: si las hereda, el bootloader nuevo
# cree que es el hijo del bootloader que acaba de morir, no extrae nada y
# busca python313.dll en la carpeta %TEMP%\_MEIxxxxxx del proceso viejo, que
# ya fue borrada. Eso da "Failed to load Python DLL ... No se puede encontrar
# el módulo especificado" (y abrirlo a mano después funciona, porque desde el
# Explorador el entorno viene limpio).
_VARS_PYINSTALLER = (
    "_PYI_APPLICATION_HOME_DIR",   # PyInstaller 6.x: la carpeta _MEI
    "_PYI_ARCHIVE_FILE",
    "_PYI_PARENT_PROCESS_LEVEL",
    "_PYI_SPLASH_IPC",
    "_MEIPASS2",                   # PyInstaller 5.x y anteriores
)


def _entorno_limpio() -> dict:
    """Copia del entorno sin los rastros del bootloader (ver _VARS_PYINSTALLER)."""
    return {k: v for k, v in os.environ.items()
            if k not in _VARS_PYINSTALLER and not k.startswith("_PYI_")}


class UpdaterError(Exception):
    pass


def _motivo_de_red(e: Exception) -> str:
    """Traduce una falla de red a algo accionable.

    Antes todo esto caía en un único "Sin conexión a internet", que en una PC
    que sí tiene internet manda a revisar justo donde no está el problema: las
    causas reales suelen ser el reloj de Windows atrasado (el certificado de
    GitHub "todavía no es válido"), el antivirus interceptando HTTPS, o una
    conexión lenta que no llega a responder dentro del timeout.
    """
    causa = getattr(e, "reason", None) or e
    if isinstance(causa, ssl.SSLCertVerificationError):
        # Llegar acá significa que fallaron los dos intentos de _abrir(): ni el
        # almacén de Windows ni el bundle propio validaron el certificado. Ahí
        # ya no es un raíz faltante, así que se apunta a las otras dos causas.
        return ("No se pudo validar el certificado de GitHub, ni con los "
                "certificados de Windows ni con los que trae la app. Revisá la "
                "fecha y hora de la PC; si están bien, casi seguro es el "
                "antivirus revisando las conexiones HTTPS (hay que desactivar "
                "ese escaneo o poner Kiosko.exe como excepción).")
    if isinstance(causa, ssl.SSLError):
        return f"Falló la conexión segura con GitHub (TLS): {causa}."
    if isinstance(causa, socket.gaierror):
        return ("Hay conexión pero no se pudo resolver github.com (DNS). "
                "Probá abrir github.com en el navegador de esta PC.")
    if isinstance(causa, TimeoutError):
        return ("GitHub no respondió a tiempo. Puede ser que la conexión esté "
                "lenta: esperá un momento y probá de nuevo.")
    if isinstance(causa, ConnectionError):
        return ("La conexión con GitHub fue rechazada o cortada "
                f"({type(causa).__name__}). Puede ser el firewall o el "
                "antivirus bloqueando Kiosko.exe.")
    return f"No se pudo conectar con GitHub: {causa}"


def _contextos_ssl():
    """Contextos SSL a probar, en orden.

    1. El de siempre: valida contra el almacén de certificados de Windows.
    2. El bundle de certifi, que viaja adentro del .exe.

    El segundo hace falta porque Windows descarga los certificados raíz que le
    faltan solo cuando los necesita, y ese mecanismo lo dispara el navegador
    (schannel), nunca Python/OpenSSL. Peor todavía si en esa PC navegan con
    Chrome o Firefox, que traen su propio almacén y no tocan el de Windows: el
    navegador entra a github.com sin problema y la app falla con "certificate
    verify failed" aunque la fecha y hora estén perfectas.

    El orden no es intercambiable: si un antivirus intercepta HTTPS con su
    propio raíz instalado en Windows, el primero funciona y el de certifi
    fallaría. Probando Windows primero se cubren los dos casos.
    """
    yield ssl.create_default_context()
    try:
        import certifi
        yield ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 - sin certifi, o su cacert.pem ilegible
        # Se corta sin yield: el llamador reporta el error original del primer
        # intento, que es el útil, en vez de uno sobre el bundle de respaldo.
        return


def _abrir(url: str, timeout: int, sin_redireccion: bool = False):
    """Abre la URL reintentando con el bundle propio si falla la validación del
    certificado. Cualquier otro error (incluido el HTTPError del 302, que el
    llamador necesita para leer el tag) se propaga tal cual."""
    req = urllib.request.Request(url, headers=_HEADERS)
    ultimo = None
    for ctx in _contextos_ssl():
        handlers = [urllib.request.HTTPSHandler(context=ctx)]
        if sin_redireccion:
            handlers.append(_SinRedireccion)
        try:
            return urllib.request.build_opener(*handlers).open(req, timeout=timeout)
        except urllib.error.URLError as e:
            # HTTPError también es URLError, pero su .reason es un texto: solo
            # se reintenta cuando la causa es del lado de TLS. Se toma SSLError
            # entero y no solo SSLCertVerificationError porque un almacén de
            # certificados roto puede fallar de varias formas, y reintentar con
            # el bundle propio no cuesta nada.
            if not isinstance(getattr(e, "reason", None), ssl.SSLError):
                raise
            ultimo = e
    raise ultimo


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
        try:
            # Sin releases, GitHub responde 200 con una página; el 302 con el tag
            # solo aparece cuando hay una publicada.
            resp = _abrir(LATEST_URL, timeout=20, sin_redireccion=True)
            location = resp.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"ok": True, "hay": False,
                        "motivo": "Todavía no hay versiones publicadas."}
            if 300 <= e.code < 400:
                location = e.headers.get("Location", "")
            else:
                return {"ok": False, "motivo": f"GitHub respondió {e.code}."}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"ok": False, "motivo": _motivo_de_red(e)}
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
    try:
        with _abrir(url, timeout=120) as resp:
            esperado = int(resp.headers.get("Content-Length") or 0)
            datos = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UpdaterError(_motivo_de_red(e)) from e
    destino.write_bytes(datos)
    if esperado and destino.stat().st_size != esperado:
        destino.unlink(missing_ok=True)
        raise UpdaterError("La descarga quedó incompleta (tamaño no coincide).")


def _lanzar_swap(actual: Path, nuevo: Path) -> None:
    """Escribe y lanza el .bat que reemplaza el .exe tras cerrar la app.

    Lo delicado acá es el entorno, no los tiempos: hay que borrar las variables
    del bootloader (ver _VARS_PYINSTALLER) antes de cualquier 'start', o el .exe
    nuevo arranca creyéndose hijo del proceso que acaba de morir y falla con
    "Failed to load Python DLL". Se limpian dos veces —en el Popen de abajo y
    acá adentro— porque es barato y una sola omisión rompe la actualización.

    Las esperas usan 'ping -n' y no 'timeout': timeout aborta con "No es
    compatible la redirección de entradas" si la consola no tiene stdin real,
    y en ese caso no esperaría nada.
    """
    nombre = actual.name
    bat = actual.with_name("_actualizar.bat")
    contenido = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        f"echo Actualizando {nombre}... no cierres esta ventana.\r\n"
        "\r\n"
        "rem --- 1) Borrar los rastros del bootloader viejo ----------------\r\n"
        "rem Tiene que ir antes de cualquier 'start' de este archivo.\r\n"
        + "".join(f'set "{v}="\r\n' for v in _VARS_PYINSTALLER) +
        "\r\n"
        "rem --- 2) Esperar a que la app cierre del todo -------------------\r\n"
        ":esperar\r\n"
        f'tasklist /FI "IMAGENAME eq {nombre}" 2>nul | find /I "{nombre}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  ping -n 2 127.0.0.1 >nul\r\n"
        "  goto esperar\r\n"
        ")\r\n"
        "ping -n 3 127.0.0.1 >nul\r\n"
        "\r\n"
        "rem --- 3) Reemplazar el .exe (reintenta si sigue tomado) ---------\r\n"
        "set INTENTOS=0\r\n"
        ":mover\r\n"
        f'move /Y "{nuevo}" "{actual}" >nul 2>&1\r\n'
        "if not errorlevel 1 goto movido\r\n"
        "set /a INTENTOS+=1\r\n"
        "if %INTENTOS% GEQ 10 (\r\n"
        "  echo.\r\n"
        "  echo No se pudo reemplazar el programa: el archivo sigue en uso.\r\n"
        f'  echo Cerra {nombre} y volve a tocar "Buscar actualizacion".\r\n'
        "  echo.\r\n"
        "  pause\r\n"
        f'  start "" "{actual}"\r\n'
        '  del "%~f0"\r\n'
        "  exit /b 1\r\n"
        ")\r\n"
        "ping -n 2 127.0.0.1 >nul\r\n"
        "goto mover\r\n"
        ":movido\r\n"
        "\r\n"
        "rem --- 4) Dejar que el archivo termine de asentarse --------------\r\n"
        "ping -n 3 127.0.0.1 >nul\r\n"
        "\r\n"
        f'start "" "{actual}"\r\n'
        'del "%~f0"\r\n'
    )
    bat.write_text(contenido, encoding="utf-8")
    subprocess.Popen(["cmd", "/c", str(bat)],
                     creationflags=CREATE_NEW_CONSOLE,
                     cwd=str(actual.parent), close_fds=True,
                     env=_entorno_limpio())


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
