"""Publica un release en GitHub para que las otras PCs se auto-actualicen.

Automatiza el flujo completo:
  1. Empuja la rama actual a origin (para que el tag apunte al commit correcto).
  2. Recompila dist/Kiosko.exe con PyInstaller (embebe la APP_VERSION actual).
  3. Crea el Release vX.Y.Z en GitHub y adjunta el .exe (lo que el updater baja).

Uso:
    python release.py                 # notas genéricas
    python release.py "Texto de las notas del release"

Requisitos (una sola vez):
    - gh CLI instalado y autenticado:  gh auth login
    - Antes de correr esto: subí APP_VERSION en config/settings.py.

El tag se arma como v{APP_VERSION}. Si ese tag ya existe, GitHub lo rechaza:
subí la versión en settings.py antes de publicar.
"""
import subprocess
import sys

from config import settings

VERSION = settings.APP_VERSION
TAG = f"v{VERSION}"
EXE = "dist/Kiosko.exe"


def _run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> None:
    notas = sys.argv[1] if len(sys.argv) > 1 else (
        f"Version {VERSION}. Actualizacion automatica: abri la app y toca "
        "'Buscar actualizacion'.")

    # 1) Empujar el commit (el tag del release apuntara a este estado).
    _run(["git", "push", "origin", "HEAD"])

    # 2) Recompilar el .exe con la version embebida actual.
    _run([sys.executable, "build.py"])

    # 3) Crear el release y adjuntar el .exe.
    _run(["gh", "release", "create", TAG, EXE,
          "--title", TAG, "--notes", notas])

    print(f"\n[OK] Release {TAG} publicado con {EXE} adjunto.")
    print("Las PCs con una version anterior lo veran al 'Buscar actualizacion'.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Fallo el comando (codigo {e.returncode}). "
              "Revisa el mensaje de arriba.")
        sys.exit(1)
