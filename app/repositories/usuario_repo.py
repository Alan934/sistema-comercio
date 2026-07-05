"""Acceso a datos de usuarios."""
import sqlite3

from app.core.utils import ahora_iso
from app.models.usuario import Usuario


def _to_usuario(row: sqlite3.Row) -> Usuario:
    return Usuario(id=row["id"], username=row["username"], rol=row["rol"],
                   activo=bool(row["activo"]))


def crear(conn: sqlite3.Connection, usuario_id: str, username: str,
          password_hash: str, salt: str, rol: str) -> None:
    conn.execute(
        """INSERT INTO usuarios
           (id, username, password_hash, salt, rol, activo, sincronizado, updated_at)
           VALUES (?, ?, ?, ?, ?, 1, 0, ?)""",
        (usuario_id, username, password_hash, salt, rol, ahora_iso()),
    )


def obtener_por_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM usuarios WHERE username = ? AND activo = 1", (username,)
    ).fetchone()


def existe_username(conn: sqlite3.Connection, username: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM usuarios WHERE username = ? AND activo = 1", (username,)
    ).fetchone() is not None


def existe_username_otro(conn: sqlite3.Connection, username: str,
                         excluir_id: str) -> bool:
    """True si otro usuario activo (distinto de `excluir_id`) ya usa ese nombre."""
    return conn.execute(
        "SELECT 1 FROM usuarios WHERE username = ? AND id != ? AND activo = 1",
        (username, excluir_id),
    ).fetchone() is not None


def actualizar(conn: sqlite3.Connection, usuario_id: str, username: str,
               password_hash: str | None = None, salt: str | None = None) -> None:
    """Actualiza el nombre y, si se pasan hash+salt, la contraseña. Marca la
    fila para re-sincronizar con la nube."""
    if password_hash is not None and salt is not None:
        conn.execute(
            "UPDATE usuarios SET username = ?, password_hash = ?, salt = ?, "
            "sincronizado = 0, updated_at = ? WHERE id = ?",
            (username, password_hash, salt, ahora_iso(), usuario_id),
        )
    else:
        conn.execute(
            "UPDATE usuarios SET username = ?, sincronizado = 0, updated_at = ? "
            "WHERE id = ?",
            (username, ahora_iso(), usuario_id),
        )


def hay_usuarios(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT COUNT(*) AS n FROM usuarios WHERE activo = 1"
    ).fetchone()["n"] > 0


def listar_activos(conn: sqlite3.Connection) -> list[Usuario]:
    return [_to_usuario(r) for r in conn.execute(
        "SELECT id, username, rol, activo FROM usuarios "
        "WHERE activo = 1 ORDER BY username")]


def desactivar(conn: sqlite3.Connection, usuario_id: str) -> None:
    conn.execute(
        "UPDATE usuarios SET activo = 0, sincronizado = 0, updated_at = ? WHERE id = ?",
        (ahora_iso(), usuario_id),
    )


# --- Sincronización (local <-> nube) ---------------------------------------

def obtener_pendientes_sync(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM usuarios WHERE sincronizado = 0"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, usuario_id: str) -> None:
    conn.execute(
        "UPDATE usuarios SET sincronizado = 1 WHERE id = ?", (usuario_id,)
    )


def sincronizar_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Baja un usuario de Neon (salvo que haya cambios locales sin subir)."""
    actual = conn.execute(
        "SELECT sincronizado FROM usuarios WHERE id = ?", (fila["id"],)
    ).fetchone()
    if actual is not None and actual["sincronizado"] == 0:
        return
    updated = (fila["updated_at"].isoformat()
               if hasattr(fila["updated_at"], "isoformat") else str(fila["updated_at"]))
    if actual is not None:
        conn.execute(
            "UPDATE usuarios SET username = ?, password_hash = ?, salt = ?, "
            "rol = ?, activo = ?, sincronizado = 1, updated_at = ? WHERE id = ?",
            (fila["username"], fila["password_hash"], fila["salt"], fila["rol"],
             1 if fila["activo"] else 0, updated, fila["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO usuarios (id, username, password_hash, salt, rol, "
            "activo, sincronizado, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (fila["id"], fila["username"], fila["password_hash"], fila["salt"],
             fila["rol"], 1 if fila["activo"] else 0, updated),
        )
