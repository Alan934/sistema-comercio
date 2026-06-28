"""Empaqueta la app en un único Kiosko.exe con PyInstaller.

Uso:  python build.py
Resultado:  dist/Kiosko.exe

Notas:
  - --onefile: un solo .exe (simplifica el auto-updater: se reemplaza un archivo).
  - --windowed: sin ventana de consola.
  - Los .sql del esquema se empaquetan adentro (se extraen a una carpeta temporal).
  - La base SQLite y el .env NO se empaquetan: viven al lado del .exe y
    sobreviven a las actualizaciones (ver config/settings.py).
"""
import PyInstaller.__main__

# Separador de --add-data en Windows es ';'  (origen;destino_dentro_del_exe)
ADD = ";"

PyInstaller.__main__.run([
    "main.py",
    "--name", "Kiosko",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    # Recursos empaquetados (solo lectura).
    "--add-data", f"data/schema_local.sql{ADD}data",
    "--add-data", f"data/schema_cloud.sql{ADD}data",
    # Dependencias con datos/binarios propios.
    "--collect-all", "customtkinter",
    "--collect-all", "psycopg",
    "--collect-all", "psycopg_binary",
    # Ícono (descomentar cuando tengamos assets/icon.ico):
    # "--icon", "assets/icon.ico",
])
