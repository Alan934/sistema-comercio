"""Punto de entrada de la aplicación. Ejecutar desde la raíz:  python main.py

Requisitos: pip install -r requirements.txt  (CustomTkinter).
Crea la base local si no existe, pide login y levanta la interfaz según el rol.
"""
from app.core import db_local
from app.services import usuario_service


def main() -> None:
    db_local.init_db()

    # PC nueva/restaurada: si no hay usuarios locales, intentar traerlos (y el
    # catálogo) de la nube antes de pedir el login. Best-effort (si no hay
    # internet, se crea el administrador localmente).
    if not usuario_service.hay_usuarios():
        try:
            from app.core import sync_manager
            sync_manager.sincronizar_ahora()
        except Exception:  # noqa: BLE001
            pass

    # Import diferido: solo se necesita CustomTkinter al levantar la GUI.
    from app.ui.auth_window import AuthWindow
    from app.ui.app_window import AppWindow

    while True:
        auth = AuthWindow()
        auth.mainloop()
        if auth.usuario is None:
            break  # se cerró la ventana de login
        app = AppWindow(auth.usuario)
        app.mainloop()
        if not getattr(app, "cerrar_sesion", False):
            break  # se cerró la app (no fue "cerrar sesión")


if __name__ == "__main__":
    main()
