"""Acceso a datos de gastos.

Por ahora solo expone lo necesario para la sincronización; el alta de gastos
llegará con el módulo de Reportes/Gastos. La tabla ya existe en el esquema.
"""
import sqlite3


def obtener_pendientes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM gastos WHERE sincronizado = 0 ORDER BY created_at"
    ).fetchall()


def marcar_sincronizado(conn: sqlite3.Connection, gasto_id: str) -> None:
    conn.execute(
        "UPDATE gastos SET sincronizado = 1 WHERE id = ?", (gasto_id,)
    )
