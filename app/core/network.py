"""Chequeo liviano de conectividad. No descarga nada, solo abre un socket."""
import socket


def hay_internet(host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0) -> bool:
    """True si hay salida a internet. Usa DNS de Google (puerto 53) que es
    rápido y casi siempre alcanzable. No bloquea más que `timeout` segundos."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
