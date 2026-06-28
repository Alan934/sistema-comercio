"""Punto de entrada de la aplicación. Ejecutar desde la raíz:  python main.py

Requisitos: pip install -r requirements.txt  (CustomTkinter).
Crea la base local si no existe y levanta la interfaz.
"""
from app.core import db_local


def main() -> None:
    db_local.init_db()
    # Import diferido: solo se necesita CustomTkinter al levantar la GUI.
    from app.ui.app_window import AppWindow
    AppWindow().mainloop()


if __name__ == "__main__":
    main()
