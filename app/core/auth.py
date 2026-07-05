"""Hash y verificación de contraseñas con la librería estándar (PBKDF2-SHA256).

No se guarda la contraseña, solo su hash + un salt aleatorio por usuario.
"""
import hashlib
import secrets

_ITERACIONES = 120_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Devuelve (salt, hash) en hexadecimal. Si no se pasa salt, genera uno."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERACIONES)
    return salt, dk.hex()


def verificar(password: str, salt: str, hash_hex: str) -> bool:
    """True si la contraseña coincide con el hash guardado."""
    _, calculado = hash_password(password, salt)
    return secrets.compare_digest(calculado, hash_hex)
