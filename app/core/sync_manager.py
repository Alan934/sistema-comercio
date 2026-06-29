"""Motor de sincronización híbrida (offline-first).

  - PULL  (nube -> local): baja categorías y precios de productos desde Neon
    y los aplica al SQLite local. NO toca el stock local.
  - PUSH  (local -> nube): sube las ventas con sincronizado=0 (cabecera +
    detalle + pagos) y, si entran bien, las marca como sincronizadas.

`sincronizar_ahora()` hace un ciclo completo y es seguro de llamar desde un
botón o desde el hilo. `SyncManager` corre ese ciclo en un hilo demonio cada
SYNC_INTERVALO_SEG, sin trabar la caja (gracias a WAL, lee mientras se vende).

Idempotencia: en la nube usamos INSERT ... ON CONFLICT (id) DO NOTHING. Si una
venta llegó a subir pero falló el marcado local, el reintento no la duplica.
"""
import threading
from datetime import datetime
from decimal import Decimal

from app.core import db_local, db_cloud, network
from app.repositories import (producto_repo, venta_repo, compra_repo,
                             cuenta_repo, gasto_repo, cliente_repo,
                             proveedor_repo)
from config import settings

try:
    from psycopg.rows import dict_row
except ImportError:
    dict_row = None


# --- Conversión de tipos local (texto) -> Python para Postgres -------------

def _num(x) -> Decimal:
    return Decimal(str(x))


def _dt(x):
    return datetime.fromisoformat(x) if x else None


# --- PULL: nube -> local ----------------------------------------------------

def _pull_catalogo(local, cloud) -> int:
    """Baja categorías y productos. Devuelve cuántos productos se aplicaron."""
    aplicados = 0
    with cloud.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, nombre, margen_pct, activo, updated_at FROM categorias")
        for cat in cur.fetchall():
            margen = str(cat["margen_pct"]) if cat["margen_pct"] is not None else None
            existe = local.execute(
                "SELECT 1 FROM categorias WHERE id = ?", (cat["id"],)
            ).fetchone()
            if existe:
                local.execute(
                    "UPDATE categorias SET nombre=?, margen_pct=?, activo=?, "
                    "updated_at=? WHERE id=?",
                    (cat["nombre"], margen, 1 if cat["activo"] else 0,
                     cat["updated_at"].isoformat(), cat["id"]),
                )
            else:
                local.execute(
                    "INSERT INTO categorias (id, nombre, margen_pct, activo, "
                    "updated_at) VALUES (?,?,?,?,?)",
                    (cat["id"], cat["nombre"], margen, 1 if cat["activo"] else 0,
                     cat["updated_at"].isoformat()),
                )

        cur.execute(
            """SELECT id, codigo_barra, nombre, categoria_id, es_pesable,
                      unidad_medida, precio_venta, costo_compra, margen_pct,
                      stock_actual, stock_minimo, controla_stock,
                      controla_vencimiento, activo, updated_at
               FROM productos"""
        )
        for prod in cur.fetchall():
            producto_repo.sincronizar_desde_nube(local, prod)
            aplicados += 1

    local.commit()
    return aplicados


# --- PUSH: local -> nube ----------------------------------------------------

def _push_catalogo(local, cloud) -> int:
    """Sube clientes y proveedores (con su saldo) usando upsert, así la nube
    refleja nombres y deudas actualizadas. Se vuelven a subir cuando cambian."""
    clientes = cliente_repo.obtener_pendientes_sync(local)
    proveedores = proveedor_repo.obtener_pendientes_sync(local)
    if not clientes and not proveedores:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for c in clientes:
                cur.execute(
                    """INSERT INTO clientes
                         (id, nombre, telefono, limite_credito, saldo_cuenta,
                          activo, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         nombre = EXCLUDED.nombre, telefono = EXCLUDED.telefono,
                         limite_credito = EXCLUDED.limite_credito,
                         saldo_cuenta = EXCLUDED.saldo_cuenta,
                         activo = EXCLUDED.activo, updated_at = EXCLUDED.updated_at""",
                    (c["id"], c["nombre"], c["telefono"], _num(c["limite_credito"]),
                     _num(c["saldo_cuenta"]), bool(c["activo"]), _dt(c["updated_at"])),
                )
            for p in proveedores:
                cur.execute(
                    """INSERT INTO proveedores
                         (id, nombre, cuit, telefono, email, saldo_cuenta,
                          activo, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         nombre = EXCLUDED.nombre, cuit = EXCLUDED.cuit,
                         telefono = EXCLUDED.telefono, email = EXCLUDED.email,
                         saldo_cuenta = EXCLUDED.saldo_cuenta,
                         activo = EXCLUDED.activo, updated_at = EXCLUDED.updated_at""",
                    (p["id"], p["nombre"], p["cuit"], p["telefono"], p["email"],
                     _num(p["saldo_cuenta"]), bool(p["activo"]), _dt(p["updated_at"])),
                )
    for c in clientes:
        cliente_repo.marcar_sincronizado(local, c["id"])
    for p in proveedores:
        proveedor_repo.marcar_sincronizado(local, p["id"])
    local.commit()
    return len(clientes) + len(proveedores)


def _push_ventas(local, cloud) -> int:
    """Sube las ventas pendientes. Devuelve cuántas subieron."""
    pendientes = venta_repo.obtener_pendientes(local)
    subidas = 0
    for v in pendientes:
        detalle = venta_repo.obtener_detalle(local, v["id"])
        pagos = venta_repo.obtener_pagos(local, v["id"])

        with cloud.transaction():
            with cloud.cursor() as cur:
                cur.execute(
                    """INSERT INTO ventas
                         (id, fecha, cliente_id, subtotal, descuento, total,
                          costo_total, estado, created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (v["id"], _dt(v["fecha"]), v["cliente_id"],
                     _num(v["subtotal"]), _num(v["descuento"]), _num(v["total"]),
                     _num(v["costo_total"]), v["estado"],
                     _dt(v["created_at"]), _dt(v["updated_at"])),
                )
                for d in detalle:
                    cur.execute(
                        """INSERT INTO ventas_detalle
                             (id, venta_id, producto_id, descripcion, cantidad,
                              precio_unitario, costo_unitario, subtotal)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO NOTHING""",
                        (d["id"], d["venta_id"], d["producto_id"], d["descripcion"],
                         _num(d["cantidad"]), _num(d["precio_unitario"]),
                         _num(d["costo_unitario"]), _num(d["subtotal"])),
                    )
                for p in pagos:
                    cur.execute(
                        """INSERT INTO pagos_venta (id, venta_id, metodo, monto)
                           VALUES (%s,%s,%s,%s)
                           ON CONFLICT (id) DO NOTHING""",
                        (p["id"], p["venta_id"], p["metodo"], _num(p["monto"])),
                    )

        # La venta ya está a salvo en la nube: la marcamos localmente.
        venta_repo.marcar_sincronizada(local, v["id"])
        local.commit()
        subidas += 1

    return subidas


def _push_compras(local, cloud) -> int:
    """Sube los remitos pendientes (cabecera + detalle)."""
    pendientes = compra_repo.obtener_pendientes(local)
    subidas = 0
    for c in pendientes:
        detalle = compra_repo.obtener_detalle(local, c["id"])
        with cloud.transaction():
            with cloud.cursor() as cur:
                cur.execute(
                    """INSERT INTO compras
                         (id, proveedor_id, fecha, nro_remito, total, condicion,
                          created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (c["id"], c["proveedor_id"], _dt(c["fecha"]), c["nro_remito"],
                     _num(c["total"]), c["condicion"],
                     _dt(c["created_at"]), _dt(c["updated_at"])),
                )
                for d in detalle:
                    cur.execute(
                        """INSERT INTO compras_detalle
                             (id, compra_id, producto_id, cantidad,
                              costo_unitario, subtotal)
                           VALUES (%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO NOTHING""",
                        (d["id"], d["compra_id"], d["producto_id"],
                         _num(d["cantidad"]), _num(d["costo_unitario"]),
                         _num(d["subtotal"])),
                    )
        compra_repo.marcar_sincronizada(local, c["id"])
        local.commit()
        subidas += 1
    return subidas


def _push_cuenta(local, cloud) -> int:
    """Sube los movimientos de cuenta corriente (fiados y deudas/pagos)."""
    pendientes = cuenta_repo.obtener_pendientes(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for m in pendientes:
                cur.execute(
                    """INSERT INTO cuenta_movimientos
                         (id, entidad_tipo, entidad_id, fecha, tipo, monto,
                          saldo_resultante, referencia_tipo, referencia_id,
                          nota, created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (m["id"], m["entidad_tipo"], m["entidad_id"], _dt(m["fecha"]),
                     m["tipo"], _num(m["monto"]), _num(m["saldo_resultante"]),
                     m["referencia_tipo"], m["referencia_id"], m["nota"],
                     _dt(m["created_at"])),
                )
    for m in pendientes:
        cuenta_repo.marcar_sincronizado(local, m["id"])
    local.commit()
    return len(pendientes)


def _push_gastos(local, cloud) -> int:
    """Sube los gastos pendientes."""
    pendientes = gasto_repo.obtener_pendientes(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for g in pendientes:
                cur.execute(
                    """INSERT INTO gastos
                         (id, fecha, tipo, descripcion, monto, proveedor_id, created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (g["id"], _dt(g["fecha"]), g["tipo"], g["descripcion"],
                     _num(g["monto"]), g["proveedor_id"], _dt(g["created_at"])),
                )
    for g in pendientes:
        gasto_repo.marcar_sincronizado(local, g["id"])
    local.commit()
    return len(pendientes)


# --- Ciclo completo ---------------------------------------------------------

def sincronizar_ahora() -> dict:
    """Un ciclo pull+push. Nunca lanza: devuelve un dict con el resultado."""
    if not db_cloud.disponible():
        return {"ok": False, "motivo": "nube no configurada"}
    if dict_row is None:
        return {"ok": False, "motivo": "psycopg no instalado"}
    if not network.hay_internet():
        return {"ok": False, "motivo": "sin internet"}

    local = db_local.connect()
    try:
        cloud = db_cloud.connect()
    except Exception as e:  # noqa: BLE001
        local.close()
        return {"ok": False, "motivo": f"no se pudo conectar a Neon: {e}"}

    try:
        db_cloud.asegurar_schema(cloud)
        productos = _pull_catalogo(local, cloud)
        catalogo = _push_catalogo(local, cloud)
        ventas = _push_ventas(local, cloud)
        compras = _push_compras(local, cloud)
        movimientos = _push_cuenta(local, cloud)
        gastos = _push_gastos(local, cloud)
        return {"ok": True,
                "productos_actualizados": productos,
                "catalogo_subido": catalogo,
                "ventas_subidas": ventas,
                "compras_subidas": compras,
                "movimientos_subidos": movimientos,
                "gastos_subidos": gastos}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "motivo": f"error durante la sync: {e}"}
    finally:
        cloud.close()
        local.close()


# --- Hilo en segundo plano --------------------------------------------------

class SyncManager:
    """Corre sincronizar_ahora() periódicamente en un hilo demonio."""

    def __init__(self, intervalo: int | None = None):
        self.intervalo = intervalo or settings.SYNC_INTERVALO_SEG
        self.ultimo_resultado: dict | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        self._stop.wait(3)  # pequeña gracia para no pelear con el arranque
        while not self._stop.is_set():
            try:
                self.ultimo_resultado = sincronizar_ahora()
            except Exception as e:  # noqa: BLE001  (el hilo nunca debe morir)
                self.ultimo_resultado = {"ok": False, "motivo": str(e)}
            self._stop.wait(self.intervalo)
