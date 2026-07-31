"""Acceso a datos de la suscripción del software.

Dos tablas chicas: `suscripcion` (una sola fila, id='DEFAULT') y
`suscripcion_pagos`. La validación de las firmas NO vive acá: este módulo
devuelve las filas tal como están y el servicio decide cuáles valen.
"""
import sqlite3

ID_CONFIG = "DEFAULT"

_COLS_CONFIG = ("id, comercio, fecha_inicio, monto_mensual, gracia_dias, "
                "datos_pago, estado_manual, ultima_fecha_vista, firma, "
                "sincronizado, updated_at")


# --- Configuración ----------------------------------------------------------

def obtener_config(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT {_COLS_CONFIG} FROM suscripcion WHERE id = ?", (ID_CONFIG,)
    ).fetchone()


def guardar_config(conn: sqlite3.Connection, cfg: dict) -> None:
    """Alta o actualización de la fila única. Deja `sincronizado` en 0 para que
    el próximo sync la suba."""
    conn.execute(
        """INSERT INTO suscripcion
           (id, comercio, fecha_inicio, monto_mensual, gracia_dias, datos_pago,
            estado_manual, ultima_fecha_vista, firma, sincronizado, updated_at)
           VALUES (:id, :comercio, :fecha_inicio, :monto_mensual, :gracia_dias,
                   :datos_pago, :estado_manual, :ultima_fecha_vista, :firma, 0,
                   :updated_at)
           ON CONFLICT(id) DO UPDATE SET
               comercio      = excluded.comercio,
               fecha_inicio  = excluded.fecha_inicio,
               monto_mensual = excluded.monto_mensual,
               gracia_dias   = excluded.gracia_dias,
               datos_pago    = excluded.datos_pago,
               estado_manual = excluded.estado_manual,
               firma         = excluded.firma,
               sincronizado  = 0,
               updated_at    = excluded.updated_at""",
        cfg,
    )


def actualizar_marca(conn: sqlite3.Connection, fecha_iso: str) -> None:
    """Adelanta la marca de agua de fecha. No toca `sincronizado`: la marca es
    local (protege contra el reloj de ESTA PC) y no tiene sentido propagarla."""
    conn.execute(
        "UPDATE suscripcion SET ultima_fecha_vista = ? WHERE id = ?",
        (fecha_iso, ID_CONFIG),
    )


# --- Pagos ------------------------------------------------------------------

def crear_pago(conn: sqlite3.Connection, p: dict) -> None:
    conn.execute(
        """INSERT INTO suscripcion_pagos
           (id, fecha, meses, monto, metodo, nota, registrado_por, anulado,
            firma, sincronizado, created_at)
           VALUES (:id, :fecha, :meses, :monto, :metodo, :nota, :registrado_por,
                   0, :firma, 0, :created_at)""",
        p,
    )


def obtener_pago(conn: sqlite3.Connection, pago_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM suscripcion_pagos WHERE id = ?", (pago_id,)
    ).fetchone()


def anular_pago(conn: sqlite3.Connection, pago_id: str, firma: str) -> None:
    """Anular cambia lo que el pago cubre, así que se vuelve a firmar."""
    conn.execute(
        "UPDATE suscripcion_pagos SET anulado = 1, firma = ?, sincronizado = 0 "
        "WHERE id = ?",
        (firma, pago_id),
    )


def listar_pagos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Todos los pagos, del más nuevo al más viejo (incluye los anulados: el
    historial se muestra completo)."""
    return conn.execute(
        "SELECT * FROM suscripcion_pagos ORDER BY fecha DESC, created_at DESC"
    ).fetchall()


# --- Sincronización ---------------------------------------------------------

def config_pendiente(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT {_COLS_CONFIG} FROM suscripcion WHERE id = ? AND sincronizado = 0",
        (ID_CONFIG,),
    ).fetchone()


def marcar_config_sincronizada(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE suscripcion SET sincronizado = 1 WHERE id = ?",
                 (ID_CONFIG,))


def pagos_pendientes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM suscripcion_pagos WHERE sincronizado = 0 ORDER BY created_at"
    ).fetchall()


def marcar_pago_sincronizado(conn: sqlite3.Connection, pago_id: str) -> None:
    conn.execute(
        "UPDATE suscripcion_pagos SET sincronizado = 1 WHERE id = ?", (pago_id,)
    )


def ids_pagos(conn: sqlite3.Connection) -> set[str]:
    return {r["id"] for r in conn.execute("SELECT id FROM suscripcion_pagos")}


def restaurar_config(conn: sqlite3.Connection, datos: dict) -> None:
    """Vuelve a escribir la configuración desde el sello en disco (alguien borró
    o alteró la fila). Queda como `sincronizado = 1` para no pisar en la nube
    una configuración que podría ser más nueva que la del sello."""
    conn.execute(
        """INSERT INTO suscripcion
           (id, comercio, fecha_inicio, monto_mensual, gracia_dias, datos_pago,
            estado_manual, ultima_fecha_vista, firma, sincronizado, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,1,?)
           ON CONFLICT(id) DO UPDATE SET
               comercio           = excluded.comercio,
               fecha_inicio       = excluded.fecha_inicio,
               monto_mensual      = excluded.monto_mensual,
               gracia_dias        = excluded.gracia_dias,
               datos_pago         = excluded.datos_pago,
               estado_manual      = excluded.estado_manual,
               ultima_fecha_vista = excluded.ultima_fecha_vista,
               firma              = excluded.firma,
               sincronizado       = 1,
               updated_at         = excluded.updated_at""",
        (datos.get("id") or ID_CONFIG, datos.get("comercio"),
         datos.get("fecha_inicio"), datos.get("monto_mensual") or "0",
         datos.get("gracia_dias") or 30, datos.get("datos_pago"),
         datos.get("estado_manual"), datos.get("ultima_fecha_vista"),
         datos.get("firma"), datos.get("updated_at") or ""),
    )


def reemplazar_config_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """La nube MANDA: pisa la configuración local sin mirar `sincronizado`.
    Conserva la marca de agua local (es de esta PC y no viaja)."""
    conn.execute(
        """INSERT INTO suscripcion
           (id, comercio, fecha_inicio, monto_mensual, gracia_dias, datos_pago,
            estado_manual, ultima_fecha_vista, firma, sincronizado, updated_at)
           VALUES (?,?,?,?,?,?,?,NULL,?,1,?)
           ON CONFLICT(id) DO UPDATE SET
               comercio      = excluded.comercio,
               fecha_inicio  = excluded.fecha_inicio,
               monto_mensual = excluded.monto_mensual,
               gracia_dias   = excluded.gracia_dias,
               datos_pago    = excluded.datos_pago,
               estado_manual = excluded.estado_manual,
               firma         = excluded.firma,
               sincronizado  = 1,
               updated_at    = excluded.updated_at""",
        (fila["id"], fila["comercio"], _texto(fila["fecha_inicio"]),
         str(fila["monto_mensual"]), fila["gracia_dias"], fila["datos_pago"],
         fila["estado_manual"], fila["firma"], _texto(fila["updated_at"])),
    )


def reemplazar_pago_desde_nube(conn: sqlite3.Connection, fila: dict) -> None:
    """Inserta o pisa el pago con lo que dice la nube (incluida la anulación)."""
    conn.execute(
        """INSERT INTO suscripcion_pagos
           (id, fecha, meses, monto, metodo, nota, registrado_por, anulado,
            firma, sincronizado, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,1,?)
           ON CONFLICT(id) DO UPDATE SET
               fecha          = excluded.fecha,
               meses          = excluded.meses,
               monto          = excluded.monto,
               metodo         = excluded.metodo,
               nota           = excluded.nota,
               registrado_por = excluded.registrado_por,
               anulado        = excluded.anulado,
               firma          = excluded.firma,
               sincronizado   = 1""",
        (fila["id"], _texto(fila["fecha"]), fila["meses"], str(fila["monto"]),
         fila["metodo"], fila["nota"], fila["registrado_por"],
         1 if fila["anulado"] else 0, fila["firma"], _texto(fila["created_at"])),
    )


def borrar_pagos_ajenos(conn: sqlite3.Connection, ids_nube: set[str]) -> int:
    """Elimina los pagos locales que la nube no conoce y que ya no están
    esperando subir. Es la parte que desarma la edición manual de la base: una
    fila inventada no está en la nube ni quedó pendiente de sync, así que se va.
    Devuelve cuántos borró."""
    sobrantes = [
        r["id"] for r in conn.execute(
            "SELECT id FROM suscripcion_pagos WHERE sincronizado = 1")
        if r["id"] not in ids_nube
    ]
    # Los inventados a mano suelen tener sincronizado = 0 (es el default de la
    # tabla), así que además se descartan los pendientes con firma inválida:
    # eso lo resuelve el servicio al calcular, no hace falta borrarlos acá.
    for pid in sobrantes:
        conn.execute("DELETE FROM suscripcion_pagos WHERE id = ?", (pid,))
    return len(sobrantes)


def _texto(valor):
    """Los timestamps/fechas de Postgres llegan como date/datetime."""
    if valor is None:
        return None
    return valor.isoformat() if hasattr(valor, "isoformat") else str(valor)
