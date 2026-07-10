"""Lógica de negocio de stock: alta/edición de productos y alertas."""
from datetime import date, datetime
from decimal import Decimal

from app.core import db_local, pricing
from app.core.utils import ahora_iso, nuevo_id, normalizar_nombre
from app.models.producto import Producto
from app.repositories import producto_repo, lote_repo, categoria_repo


class StockError(Exception):
    """Error de negocio esperable."""


def parse_fecha(texto: str | None) -> str | None:
    """Normaliza una fecha escrita por el usuario a ISO (YYYY-MM-DD).

    Acepta dd/mm/aaaa, dd-mm-aaaa y el propio ISO. Devuelve None si está vacía
    o no se puede interpretar."""
    texto = (texto or "").strip()
    if not texto:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date().isoformat()
        except ValueError:
            continue
    return None


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
            if completo["_fecha_vencimiento"]:
                # Lote inicial del alta: usa el stock inicial como cantidad.
                lote_repo.crear(conn, completo["id"],
                                completo["_fecha_vencimiento"],
                                completo["stock_actual"])
    finally:
        conn.close()
    return completo["id"]


def actualizar_producto(producto_id: str, datos: dict) -> None:
    """Edita un producto existente (no cambia el stock_actual)."""
    completo = _normalizar({**datos, "id": producto_id}, con_id=True)
    conn = db_local.connect()
    try:
        with conn:
            _aplicar_margen(conn, completo)
            producto_repo.actualizar(conn, completo)
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
        venc = date.fromisoformat(r["fecha_vencimiento"])
        salida.append({
            "producto": r["producto_nombre"],
            "fecha_vencimiento": r["fecha_vencimiento"],
            "cantidad": r["cantidad"],
            "dias_restantes": (venc - hoy).days,
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
        dias = (date.fromisoformat(f) - hoy).days if f else None
        salida.append({"id": r["id"], "fecha_vencimiento": f,
                       "cantidad": r["cantidad"], "dias_restantes": dias})
    return salida


def agregar_lote(producto_id: str, fecha_texto: str, cantidad_texto: str = "0") -> None:
    """Agrega un lote (fecha + cantidad) a un producto. No pisa los existentes."""
    fecha = parse_fecha(fecha_texto)
    if fecha is None:
        raise StockError("Fecha inválida (formato dd/mm/aaaa).")
    try:
        cantidad = Decimal(str(cantidad_texto or "0").replace(",", "."))
    except (ArithmeticError, ValueError):
        raise StockError("Cantidad inválida.")
    if cantidad < 0:
        raise StockError("La cantidad no puede ser negativa.")
    conn = db_local.connect()
    try:
        with conn:
            lote_repo.crear(conn, producto_id, fecha, str(cantidad))
    finally:
        conn.close()


def eliminar_lote(lote_id: str) -> None:
    """Da de baja (borrado lógico) un lote."""
    conn = db_local.connect()
    try:
        with conn:
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
        dr = (date.fromisoformat(r["fecha_vencimiento"]) - hoy).days
        pid = r["producto_id"]
        if pid not in mapa or dr < mapa[pid]:
            mapa[pid] = dr
    return mapa
