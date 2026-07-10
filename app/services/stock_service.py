"""Lógica de negocio de stock: alta/edición de productos y alertas."""
from datetime import date
from decimal import Decimal

from app.core import db_local, pricing
# parse_fecha vive en utils (lo comparte la migración de db_local); se reexporta
# acá para no romper los `stock_service.parse_fecha` que ya usa la UI.
from app.core.utils import ahora_iso, nuevo_id, normalizar_nombre, parse_fecha
from app.models.producto import Producto
from app.repositories import producto_repo, lote_repo, categoria_repo, movimiento_repo


class StockError(Exception):
    """Error de negocio esperable."""


def _a_margen(valor) -> Decimal | None:
    """Texto/None -> Decimal o None (margen vacío = usar el de la categoría)."""
    if valor is None or str(valor).strip() == "":
        return None
    return Decimal(str(valor).replace(",", "."))


def _normalizar(datos: dict, *, con_id: bool) -> dict:
    """Completa valores por defecto y normaliza tipos para guardar."""
    nombre = normalizar_nombre(datos.get("nombre") or "")
    if not nombre:
        raise StockError("El producto necesita un nombre.")
    # Si controla vencimiento, en el ALTA la fecha del primer lote es obligatoria
    # (en la edición las fechas se gestionan aparte, con el gestor de lotes).
    controla_venc = bool(datos.get("controla_vencimiento"))
    fecha_venc = parse_fecha(datos.get("fecha_vencimiento"))
    if controla_venc and not con_id and fecha_venc is None:
        raise StockError("Indicá la fecha de vencimiento (formato dd/mm/aaaa).")
    margen = _a_margen(datos.get("margen_pct"))
    completo = {
        "codigo_barra": (datos.get("codigo_barra") or None),
        "nombre": nombre,
        "categoria_id": datos.get("categoria_id"),
        "margen_pct": str(margen) if margen is not None else None,
        "ubicacion": (datos.get("ubicacion") or "").strip() or None,
        "es_pesable": 1 if datos.get("es_pesable") else 0,
        "unidad_medida": datos.get("unidad_medida") or ("KG" if datos.get("es_pesable") else "UN"),
        "costo_compra": str(datos.get("costo_compra", "0")),
        "precio_venta": str(datos.get("precio_venta", "0")),
        "stock_minimo": str(datos.get("stock_minimo", "0")),
        "controla_stock": 1 if datos.get("controla_stock", True) else 0,
        "controla_vencimiento": 1 if controla_venc else 0,
        "activo": 1 if datos.get("activo", True) else 0,
        "updated_at": ahora_iso(),
        # Clave auxiliar (empieza con _, el repo la ignora al bindear): la usan
        # crear/actualizar para armar el lote de vencimiento.
        "_fecha_vencimiento": fecha_venc,
    }
    if con_id:
        completo["id"] = datos["id"]
    return completo


def _aplicar_margen(conn, completo: dict) -> None:
    """Si hay margen efectivo (producto o categoría), pisa precio_venta con el
    calculado a partir del costo. Si no hay margen, deja el precio manual."""
    margen_prod = _a_margen(completo.get("margen_pct"))
    margen_cat = None
    if completo.get("categoria_id"):
        cat = categoria_repo.obtener(conn, completo["categoria_id"])
        if cat is not None:
            margen_cat = cat.margen_pct
    margen = pricing.margen_efectivo(margen_prod, margen_cat)
    if margen is not None:
        completo["precio_venta"] = str(
            pricing.precio_desde_margen(completo["costo_compra"], margen))


def crear_producto(datos: dict) -> str:
    """Alta de producto. Devuelve el id generado."""
    completo = _normalizar(datos, con_id=False)
    completo["id"] = nuevo_id()
    completo["stock_actual"] = str(datos.get("stock_actual", "0"))
    conn = db_local.connect()
    try:
        with conn:
            _aplicar_margen(conn, completo)
            producto_repo.crear(conn, completo)
            # Lote inicial del alta: solo si hay stock que vencer. Un lote en 0
            # no aporta nada (no hay unidades que caduquen) y ensucia la lista;
            # la fecha se cargará con el primer remito o desde el gestor.
            if completo["_fecha_vencimiento"] and \
                    Decimal(completo["stock_actual"]) > 0:
                lote_repo.crear(conn, completo["id"],
                                completo["_fecha_vencimiento"],
                                completo["stock_actual"])
    finally:
        conn.close()
    return completo["id"]


def actualizar_producto(producto_id: str, datos: dict) -> None:
    """Edita un producto existente. Si `datos` trae stock_actual, ajusta el
    stock a ese valor dejando el movimiento (AJUSTE) para que se sincronice;
    si no lo trae, no toca el stock."""
    completo = _normalizar({**datos, "id": producto_id}, con_id=True)
    ajusta_stock = datos.get("stock_actual") is not None
    if ajusta_stock:
        try:
            nuevo_stock = Decimal(str(datos["stock_actual"]).replace(",", "."))
        except (ArithmeticError, ValueError):
            raise StockError("Stock inválido.")
        if nuevo_stock < 0:
            raise StockError("El stock no puede ser negativo.")
    conn = db_local.connect()
    try:
        with conn:
            _aplicar_margen(conn, completo)
            producto_repo.actualizar(conn, completo)
            if ajusta_stock:
                producto_repo.ajustar_stock(conn, producto_id, nuevo_stock)
    finally:
        conn.close()


def listar_productos() -> list[Producto]:
    conn = db_local.connect()
    try:
        return producto_repo.listar_todos(conn)
    finally:
        conn.close()


def obtener_producto(producto_id: str) -> dict | None:
    conn = db_local.connect()
    try:
        row = producto_repo.obtener(conn, producto_id)
        if row is None:
            return None
        datos = dict(row)
        lote = lote_repo.ultimo_activo(conn, producto_id)
        datos["fecha_vencimiento"] = lote["fecha_vencimiento"] if lote else None
        return datos
    finally:
        conn.close()


def buscar_por_codigo(codigo: str) -> Producto | None:
    """Busca un producto por su código de barra exacto (para el lector)."""
    conn = db_local.connect()
    try:
        return producto_repo.buscar_por_codigo(conn, codigo)
    finally:
        conn.close()


def listar_ubicaciones() -> list[str]:
    conn = db_local.connect()
    try:
        return producto_repo.ubicaciones_distintas(conn)
    finally:
        conn.close()


def alertas_stock_bajo() -> list[dict]:
    conn = db_local.connect()
    try:
        rows = producto_repo.listar_stock_bajo(conn)
        return [dict(r) for r in rows]
    finally:
        conn.close()


def alertas_vencimientos(dias: int = 7) -> list[dict]:
    """Lotes por vencer/vencidos, con los días que faltan (negativo = vencido)."""
    conn = db_local.connect()
    try:
        rows = lote_repo.proximos_a_vencer(conn, dias)
    finally:
        conn.close()
    hoy = date.today()
    salida = []
    for r in rows:
        dias = _dias(r["fecha_vencimiento"], hoy)
        if dias is None:
            continue  # fecha ilegible: no la reportamos como alerta
        salida.append({
            "producto": r["producto_nombre"],
            "fecha_vencimiento": r["fecha_vencimiento"],
            "cantidad": r["cantidad"],
            "dias_restantes": dias,
        })
    return salida


def listar_lotes(producto_id: str) -> list[dict]:
    """Todos los lotes activos de un producto, con los días que faltan para
    vencer (negativo = vencido; None si el lote no tiene fecha)."""
    conn = db_local.connect()
    try:
        rows = lote_repo.listar_activos(conn, producto_id)
    finally:
        conn.close()
    hoy = date.today()
    salida = []
    for r in rows:
        f = r["fecha_vencimiento"]
        salida.append({"id": r["id"], "fecha_vencimiento": f,
                       "cantidad": r["cantidad"], "dias_restantes": _dias(f, hoy)})
    return salida


def _dias(fecha_iso: str | None, hoy: date) -> int | None:
    """Días hasta la fecha (negativo = vencida). None si no hay fecha o quedó en
    un formato ilegible: así una fecha corrupta nunca rompe la lista/alertas."""
    if not fecha_iso:
        return None
    try:
        return (date.fromisoformat(fecha_iso) - hoy).days
    except ValueError:
        return None


def agregar_lote(producto_id: str, fecha_texto: str, cantidad_texto: str = "0") -> None:
    """Agrega un lote (fecha + cantidad) a un producto. No pisa los existentes."""
    fecha = parse_fecha(fecha_texto)
    if fecha is None:
        raise StockError("Fecha inválida (formato dd/mm/aaaa).")
    try:
        cantidad = Decimal(str(cantidad_texto or "0").replace(",", "."))
    except (ArithmeticError, ValueError):
        raise StockError("Cantidad inválida.")
    if cantidad <= 0:
        raise StockError("Indicá una cantidad mayor a cero para el lote.")
    conn = db_local.connect()
    try:
        with conn:
            lote_repo.crear(conn, producto_id, fecha, str(cantidad))
    finally:
        conn.close()


def eliminar_lote(lote_id: str, descontar_stock: bool = False) -> None:
    """Da de baja (borrado lógico) un lote. Si `descontar_stock`, además resta del
    stock del producto la cantidad que tenía el lote (mercadería que se retira por
    vencimiento), dejando el movimiento como AJUSTE para que viaje al resto de las
    PCs por el ledger."""
    conn = db_local.connect()
    try:
        with conn:
            if descontar_stock:
                lote = lote_repo.obtener(conn, lote_id)
                if lote is not None:
                    cantidad = Decimal(str(lote["cantidad"]))
                    if cantidad > 0:
                        producto_repo.descontar_stock(
                            conn, lote["producto_id"], cantidad,
                            tipo=movimiento_repo.AJUSTE, referencia_id=lote_id)
            lote_repo.eliminar(conn, lote_id)
    finally:
        conn.close()


def vencimientos_por_producto(dias: int = 7) -> dict[str, int]:
    """{producto_id: días para el vencimiento más próximo} (negativo = vencido).
    Para marcar cada fila de la tabla de stock con su advertencia."""
    conn = db_local.connect()
    try:
        rows = lote_repo.proximos_a_vencer(conn, dias)
    finally:
        conn.close()
    hoy = date.today()
    mapa: dict[str, int] = {}
    for r in rows:
        dr = _dias(r["fecha_vencimiento"], hoy)
        if dr is None:
            continue
        pid = r["producto_id"]
        if pid not in mapa or dr < mapa[pid]:
            mapa[pid] = dr
    return mapa
