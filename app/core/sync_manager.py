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
                             proveedor_repo, categoria_repo, usuario_repo,
                             cierre_repo, res_repo, pieza_repo, corte_repo,
                             movimiento_repo)
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


def _num_null(x):
    return Decimal(str(x)) if x is not None else None


# --- PULL: nube -> local ----------------------------------------------------

def _pull_catalogo(local, cloud) -> int:
    """Baja TODO el catálogo y contactos de Neon: categorías, productos,
    clientes y proveedores. Es lo que pobla una PC nueva o restaurada.
    Devuelve cuántos registros se aplicaron."""
    aplicados = 0
    with cloud.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, nombre, margen_pct, activo, updated_at FROM categorias")
        for cat in cur.fetchall():
            categoria_repo.sincronizar_desde_nube(local, cat)
            aplicados += 1

        cur.execute(
            """SELECT id, codigo_barra, nombre, categoria_id, es_pesable,
                      unidad_medida, precio_venta, costo_compra, margen_pct,
                      ubicacion, stock_actual, stock_minimo, controla_stock,
                      controla_vencimiento, activo, updated_at
               FROM productos"""
        )
        for prod in cur.fetchall():
            producto_repo.sincronizar_desde_nube(local, prod)
            aplicados += 1

        cur.execute("SELECT id, nombre, telefono, limite_credito, saldo_cuenta, "
                    "activo, updated_at FROM clientes")
        for cli in cur.fetchall():
            cliente_repo.sincronizar_desde_nube(local, cli)
            aplicados += 1

        cur.execute("SELECT id, nombre, cuit, telefono, email, saldo_cuenta, "
                    "activo, updated_at FROM proveedores")
        for pr in cur.fetchall():
            proveedor_repo.sincronizar_desde_nube(local, pr)
            aplicados += 1

        cur.execute("SELECT id, username, password_hash, salt, rol, activo, "
                    "updated_at FROM usuarios")
        for u in cur.fetchall():
            usuario_repo.sincronizar_desde_nube(local, u)
            aplicados += 1

        cur.execute("SELECT * FROM cierres_caja")
        for cierre in cur.fetchall():
            cierre_repo.sincronizar_desde_nube(local, cierre)
            aplicados += 1

        # Carne: reses -> piezas -> cortes (en ese orden por las FK locales;
        # los productos ya se aplicaron arriba, así el FK cortes->productos entra).
        cur.execute("SELECT * FROM reses")
        for res in cur.fetchall():
            res_repo.sincronizar_desde_nube(local, res)
            aplicados += 1
        cur.execute("SELECT * FROM piezas")
        for pieza in cur.fetchall():
            pieza_repo.sincronizar_desde_nube(local, pieza)
            aplicados += 1
        cur.execute("SELECT * FROM cortes")
        for corte in cur.fetchall():
            corte_repo.sincronizar_desde_nube(local, corte)
            aplicados += 1

    local.commit()
    return aplicados


def _pull_movimientos(local, cloud) -> int:
    """Baja del ledger de Neon los movimientos de stock que esta PC todavía no
    tiene y aplica su delta al stock local (así convergen las dos cajas).

    Debe correr DESPUÉS de _pull_catalogo: los productos tienen que existir
    localmente para poder sumarles el delta. Idempotente por id: un movimiento
    ya aplicado se saltea. Sólo trae del cloud los ids que no tenemos, para no
    reprocesar todo el historial en cada ciclo."""
    locales = {r["id"] for r in
               local.execute("SELECT id FROM movimientos_stock")}
    aplicados = 0
    with cloud.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, producto_id, fecha, tipo, cantidad, referencia_id, "
            "created_at FROM movimientos_stock"
        )
        for m in cur.fetchall():
            if m["id"] in locales:
                continue
            if movimiento_repo.aplicar_desde_nube(local, m):
                aplicados += 1
    local.commit()
    return aplicados


# --- PUSH: local -> nube ----------------------------------------------------

def _push_categorias(local, cloud) -> int:
    pendientes = categoria_repo.obtener_pendientes_sync(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for c in pendientes:
                cur.execute(
                    """INSERT INTO categorias (id, nombre, margen_pct, activo, updated_at)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         nombre = EXCLUDED.nombre, margen_pct = EXCLUDED.margen_pct,
                         activo = EXCLUDED.activo, updated_at = EXCLUDED.updated_at""",
                    (c["id"], c["nombre"], _num_null(c["margen_pct"]),
                     bool(c["activo"]), _dt(c["updated_at"])),
                )
    for c in pendientes:
        categoria_repo.marcar_sincronizado(local, c["id"])
    local.commit()
    return len(pendientes)


def _push_productos(local, cloud) -> int:
    pendientes = producto_repo.obtener_pendientes_sync(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for p in pendientes:
                cur.execute(
                    """INSERT INTO productos
                         (id, codigo_barra, nombre, categoria_id, es_pesable,
                          unidad_medida, costo_compra, precio_venta, margen_pct,
                          ubicacion, stock_actual, stock_minimo, controla_stock,
                          controla_vencimiento, activo, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         codigo_barra = EXCLUDED.codigo_barra, nombre = EXCLUDED.nombre,
                         categoria_id = EXCLUDED.categoria_id,
                         es_pesable = EXCLUDED.es_pesable,
                         unidad_medida = EXCLUDED.unidad_medida,
                         costo_compra = EXCLUDED.costo_compra,
                         precio_venta = EXCLUDED.precio_venta,
                         margen_pct = EXCLUDED.margen_pct, ubicacion = EXCLUDED.ubicacion,
                         stock_actual = EXCLUDED.stock_actual,
                         stock_minimo = EXCLUDED.stock_minimo,
                         controla_stock = EXCLUDED.controla_stock,
                         controla_vencimiento = EXCLUDED.controla_vencimiento,
                         activo = EXCLUDED.activo, updated_at = EXCLUDED.updated_at""",
                    (p["id"], p["codigo_barra"], p["nombre"], p["categoria_id"],
                     bool(p["es_pesable"]), p["unidad_medida"], _num(p["costo_compra"]),
                     _num(p["precio_venta"]), _num_null(p["margen_pct"]), p["ubicacion"],
                     _num(p["stock_actual"]), _num(p["stock_minimo"]),
                     bool(p["controla_stock"]), bool(p["controla_vencimiento"]),
                     bool(p["activo"]), _dt(p["updated_at"])),
                )
    for p in pendientes:
        producto_repo.marcar_sincronizado(local, p["id"])
    local.commit()
    return len(pendientes)


def _push_usuarios(local, cloud) -> int:
    pendientes = usuario_repo.obtener_pendientes_sync(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for u in pendientes:
                cur.execute(
                    """INSERT INTO usuarios
                         (id, username, password_hash, salt, rol, activo, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         username = EXCLUDED.username,
                         password_hash = EXCLUDED.password_hash,
                         salt = EXCLUDED.salt, rol = EXCLUDED.rol,
                         activo = EXCLUDED.activo, updated_at = EXCLUDED.updated_at""",
                    (u["id"], u["username"], u["password_hash"], u["salt"],
                     u["rol"], bool(u["activo"]), _dt(u["updated_at"])),
                )
    for u in pendientes:
        usuario_repo.marcar_sincronizado(local, u["id"])
    local.commit()
    return len(pendientes)


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
                          nota, metodo, created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (m["id"], m["entidad_tipo"], m["entidad_id"], _dt(m["fecha"]),
                     m["tipo"], _num(m["monto"]), _num(m["saldo_resultante"]),
                     m["referencia_tipo"], m["referencia_id"], m["nota"],
                     m["metodo"], _dt(m["created_at"])),
                )
    for m in pendientes:
        cuenta_repo.marcar_sincronizado(local, m["id"])
    local.commit()
    return len(pendientes)


def _push_cierres(local, cloud) -> int:
    pendientes = cierre_repo.obtener_pendientes_sync(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for c in pendientes:
                cur.execute(
                    """INSERT INTO cierres_caja
                         (id, fecha, desde, usuario_id, usuario_nombre,
                          ventas_cantidad, total_vendido, efectivo_ventas,
                          transferencia_ventas, tarjeta_ventas, fiado_ventas,
                          cobros_efectivo, pagos_efectivo, gastos_total, fondo,
                          efectivo_esperado, efectivo_contado, diferencia, nota,
                          created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (c["id"], _dt(c["fecha"]), _dt(c["desde"]), c["usuario_id"],
                     c["usuario_nombre"], c["ventas_cantidad"],
                     _num(c["total_vendido"]), _num(c["efectivo_ventas"]),
                     _num(c["transferencia_ventas"]), _num(c["tarjeta_ventas"]),
                     _num(c["fiado_ventas"]), _num(c["cobros_efectivo"]),
                     _num(c["pagos_efectivo"]), _num(c["gastos_total"]),
                     _num(c["fondo"]), _num(c["efectivo_esperado"]),
                     _num(c["efectivo_contado"]), _num(c["diferencia"]),
                     c["nota"], _dt(c["created_at"])),
                )
    for c in pendientes:
        cierre_repo.marcar_sincronizado(local, c["id"])
    local.commit()
    return len(pendientes)


def _push_reses(local, cloud) -> int:
    """Sube las reses pendientes (upsert)."""
    pendientes = res_repo.obtener_pendientes_sync(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for r in pendientes:
                cur.execute(
                    """INSERT INTO reses
                         (id, proveedor_id, fecha, descripcion, peso_total,
                          costo_por_kg, costo_total, margen_pct, condicion, estado,
                          created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         proveedor_id = EXCLUDED.proveedor_id, fecha = EXCLUDED.fecha,
                         descripcion = EXCLUDED.descripcion,
                         peso_total = EXCLUDED.peso_total,
                         costo_por_kg = EXCLUDED.costo_por_kg,
                         costo_total = EXCLUDED.costo_total,
                         margen_pct = EXCLUDED.margen_pct,
                         condicion = EXCLUDED.condicion, estado = EXCLUDED.estado,
                         updated_at = EXCLUDED.updated_at""",
                    (r["id"], r["proveedor_id"], _dt(r["fecha"]), r["descripcion"],
                     _num(r["peso_total"]), _num(r["costo_por_kg"]),
                     _num(r["costo_total"]), _num_null(r["margen_pct"]),
                     r["condicion"], r["estado"], _dt(r["created_at"]),
                     _dt(r["updated_at"])),
                )
    for r in pendientes:
        res_repo.marcar_sincronizado(local, r["id"])
    local.commit()
    return len(pendientes)


def _push_piezas(local, cloud) -> int:
    """Sube las piezas pendientes (upsert). Van después de las reses por la FK."""
    pendientes = pieza_repo.obtener_pendientes_sync(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for p in pendientes:
                cur.execute(
                    """INSERT INTO piezas
                         (id, res_id, nombre, fecha, peso, margen_pct, estado,
                          updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         res_id = EXCLUDED.res_id, nombre = EXCLUDED.nombre,
                         fecha = EXCLUDED.fecha, peso = EXCLUDED.peso,
                         margen_pct = EXCLUDED.margen_pct, estado = EXCLUDED.estado,
                         updated_at = EXCLUDED.updated_at""",
                    (p["id"], p["res_id"], p["nombre"], _dt(p["fecha"]),
                     _num(p["peso"]), _num_null(p["margen_pct"]), p["estado"],
                     _dt(p["updated_at"])),
                )
    for p in pendientes:
        pieza_repo.marcar_sincronizado(local, p["id"])
    local.commit()
    return len(pendientes)


def _push_cortes(local, cloud) -> int:
    """Sube los cortes CONFIRMADOS pendientes (upsert). Los borradores no suben."""
    pendientes = corte_repo.obtener_pendientes_sync_confirmados(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for c in pendientes:
                cur.execute(
                    """INSERT INTO cortes
                         (id, pieza_id, producto_id, descripcion, peso,
                          precio_venta_kg, margen_pct, costo_kg, subtotal,
                          es_desperdicio, confirmado, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         pieza_id = EXCLUDED.pieza_id,
                         producto_id = EXCLUDED.producto_id,
                         descripcion = EXCLUDED.descripcion, peso = EXCLUDED.peso,
                         precio_venta_kg = EXCLUDED.precio_venta_kg,
                         margen_pct = EXCLUDED.margen_pct, costo_kg = EXCLUDED.costo_kg,
                         subtotal = EXCLUDED.subtotal,
                         es_desperdicio = EXCLUDED.es_desperdicio,
                         confirmado = EXCLUDED.confirmado,
                         updated_at = EXCLUDED.updated_at""",
                    (c["id"], c["pieza_id"], c["producto_id"], c["descripcion"],
                     _num(c["peso"]), _num(c["precio_venta_kg"]),
                     _num_null(c["margen_pct"]), _num(c["costo_kg"]),
                     _num(c["subtotal"]), bool(c["es_desperdicio"]),
                     bool(c["confirmado"]), _dt(c["updated_at"])),
                )
    for c in pendientes:
        corte_repo.marcar_sincronizado(local, c["id"])
    local.commit()
    return len(pendientes)


def _push_movimientos(local, cloud) -> int:
    """Sube los movimientos de stock pendientes. Son inmutables (nunca se
    editan), así que ON CONFLICT DO NOTHING alcanza para la idempotencia."""
    pendientes = movimiento_repo.obtener_pendientes_sync(local)
    if not pendientes:
        return 0
    with cloud.transaction():
        with cloud.cursor() as cur:
            for m in pendientes:
                cur.execute(
                    """INSERT INTO movimientos_stock
                         (id, producto_id, fecha, tipo, cantidad,
                          referencia_id, created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (m["id"], m["producto_id"], _dt(m["fecha"]), m["tipo"],
                     _num(m["cantidad"]), m["referencia_id"],
                     _dt(m["created_at"])),
                )
    for m in pendientes:
        movimiento_repo.marcar_sincronizado(local, m["id"])
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
                         (id, fecha, tipo, descripcion, monto, proveedor_id,
                          metodo, created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (g["id"], _dt(g["fecha"]), g["tipo"], g["descripcion"],
                     _num(g["monto"]), g["proveedor_id"], g["metodo"],
                     _dt(g["created_at"])),
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
        # SUBIR todo lo pendiente (catálogo completo + transacciones).
        cat = _push_categorias(local, cloud)
        prod = _push_productos(local, cloud)
        usuarios = _push_usuarios(local, cloud)
        contactos = _push_catalogo(local, cloud)
        ventas = _push_ventas(local, cloud)
        compras = _push_compras(local, cloud)
        # Carne: reses -> piezas -> cortes (ese orden por las FK de la nube).
        reses = _push_reses(local, cloud)
        piezas = _push_piezas(local, cloud)
        cortes = _push_cortes(local, cloud)
        movimientos = _push_cuenta(local, cloud)
        mov_stock = _push_movimientos(local, cloud)
        gastos = _push_gastos(local, cloud)
        cierres = _push_cierres(local, cloud)
        # BAJAR todo lo que falte (pobla una PC nueva o restaurada).
        bajados = _pull_catalogo(local, cloud)
        # El stock converge acá: aplica los deltas del ledger de las otras PCs.
        mov_stock_bajados = _pull_movimientos(local, cloud)
        return {"ok": True,
                "categorias_subidas": cat,
                "productos_subidos": prod,
                "usuarios_subidos": usuarios,
                "contactos_subidos": contactos,
                "ventas_subidas": ventas,
                "compras_subidas": compras,
                "reses_subidas": reses,
                "piezas_subidas": piezas,
                "cortes_subidos": cortes,
                "movimientos_subidos": movimientos,
                "movimientos_stock_subidos": mov_stock,
                "gastos_subidos": gastos,
                "cierres_subidos": cierres,
                "bajados_de_nube": bajados,
                "movimientos_stock_bajados": mov_stock_bajados}
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
