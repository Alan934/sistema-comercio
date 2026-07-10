"""Lógica de negocio del despiece de carne (reses -> piezas -> cortes).

Una res entra por kg a un costo/kg. Se subdivide en piezas (Espalda, Pierna),
que pueden bajarse en días distintos, y cada pieza en cortes con su kg y
precio/kg. Al CONFIRMAR una pieza, cada corte carga stock a un producto pesable
(categoría "Carne"), quedando listo para venderse por peso en la Caja.

Costeo (tal como lo hace la carnicera): todos los cortes de una res comparten el
mismo costo/kg (el de la res). La ganancia de una pieza es:
    venta de sus cortes  -  (kg de la pieza x costo/kg de la res).
A nivel res se informa además la ganancia REAL incluyendo la merma (los kg que
se pierden entre la res y las piezas), que la planilla a mano no contempla.

Todo lo que muta la base va dentro de `with conn:` (una transacción): o entra
completo, o no entra nada. Confirmar una pieza es la operación crítica.
"""
from decimal import Decimal, ROUND_HALF_UP

from app.core import db_local, pricing
from app.core.utils import ahora_iso, ahora_local, nuevo_id, normalizar_nombre
from app.models.res import Res, CONTADO, CUENTA_CORRIENTE, ABIERTA, CERRADA
from app.models.pieza import Pieza
from app.models.corte import Corte
from app.repositories import (res_repo, pieza_repo, corte_repo, producto_repo,
                              categoria_repo, cuenta_repo, movimiento_repo)

CENTAVOS = Decimal("0.01")
KILOS = Decimal("0.001")
CATEGORIA_CARNE = "Carne"


class DespieceError(Exception):
    """Error de negocio esperable."""


# --- Helpers de conversión --------------------------------------------------

def _dec(valor, campo: str = "valor") -> Decimal:
    """Texto/número (acepta coma decimal) -> Decimal. Lanza si no parsea."""
    try:
        return Decimal(str(valor).replace(",", ".").strip())
    except Exception:
        raise DespieceError(f"{campo} inválido: {valor!r}")


def _dec_opt(valor) -> Decimal | None:
    """Igual que _dec pero vacío/None -> None (para márgenes opcionales)."""
    if valor is None or str(valor).strip() == "":
        return None
    return _dec(valor)


def _peso(valor, campo: str = "peso") -> Decimal:
    return _dec(valor, campo).quantize(KILOS, rounding=ROUND_HALF_UP)


def _plata(valor, campo: str = "monto") -> Decimal:
    return _dec(valor, campo).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


# --- Precio de un corte (jerarquía de margen: corte > pieza > res) ----------

def _resolver_precio(precio_dado, margen_corte, pieza: Pieza, res: Res) -> Decimal:
    """Precio/kg del corte: si se da explícito, ese; si no, se deriva del margen
    efectivo (corte, o pieza, o res) aplicado al costo/kg de la res; si no hay
    ningún margen, 0 (se cargará el precio a mano más tarde)."""
    if precio_dado is not None and str(precio_dado).strip() != "":
        return _plata(precio_dado, "precio")
    margen = margen_corte
    if margen is None:
        margen = pieza.margen_pct
    if margen is None:
        margen = res.margen_pct
    if margen is not None:
        return pricing.precio_desde_margen(res.costo_por_kg, margen)
    return Decimal("0.00")


# --- Reses ------------------------------------------------------------------

def crear_res(descripcion, peso_total, costo_por_kg, proveedor_id=None,
              margen_pct=None, condicion=CONTADO) -> str:
    """Da de alta una media res (o res). Si es a cuenta corriente, suma la deuda
    del costo total al proveedor. Devuelve el id de la res."""
    peso = _peso(peso_total, "peso de la res")
    costo = _plata(costo_por_kg, "costo por kg")
    if peso <= 0:
        raise DespieceError("El peso de la res debe ser mayor a 0.")
    if costo < 0:
        raise DespieceError("El costo por kg no puede ser negativo.")
    if condicion not in (CONTADO, CUENTA_CORRIENTE):
        raise DespieceError(f"Condición inválida: {condicion}")
    if condicion == CUENTA_CORRIENTE and not proveedor_id:
        raise DespieceError("Para cuenta corriente hay que elegir un proveedor.")

    costo_total = _plata(peso * costo)
    res = Res(
        id=nuevo_id(), proveedor_id=(proveedor_id or None), fecha=ahora_local(),
        descripcion=(descripcion or "Media res").strip(), peso_total=peso,
        costo_por_kg=costo, costo_total=costo_total, condicion=condicion,
        estado=ABIERTA, margen_pct=_dec_opt(margen_pct))

    conn = db_local.connect()
    try:
        with conn:
            res_repo.crear(conn, res)
            if condicion == CUENTA_CORRIENTE:
                cuenta_repo.registrar_movimiento(
                    conn, entidad_tipo="PROVEEDOR", entidad_id=proveedor_id,
                    tipo=cuenta_repo.DEBE, monto=costo_total,
                    referencia_tipo="RES", referencia_id=res.id,
                    nota=f"{res.descripcion} ({peso} kg)")
    finally:
        conn.close()
    return res.id


def cerrar_res(res_id: str) -> None:
    """Marca la res como CERRADA (ya se terminaron de bajar todas sus piezas)."""
    conn = db_local.connect()
    try:
        with conn:
            if res_repo.obtener(conn, res_id) is None:
                raise DespieceError("La res no existe.")
            res_repo.cambiar_estado(conn, res_id, CERRADA)
    finally:
        conn.close()


def eliminar_res(res_id: str) -> None:
    """Elimina una res cargada por error, con sus piezas y cortes. Solo se
    permite si NINGUNA pieza se confirmó (todavía no cargó stock). Si era a
    cuenta corriente, revierte la deuda que había sumado al proveedor. Todo en
    una sola transacción."""
    conn = db_local.connect()
    try:
        with conn:
            res = res_repo.obtener(conn, res_id)
            if res is None:
                raise DespieceError("La res no existe.")
            if corte_repo.hay_confirmados_por_res(conn, res_id):
                raise DespieceError(
                    "Esta res ya tiene piezas confirmadas (cargó stock); "
                    "no se puede eliminar.")
            # Revertir la deuda del proveedor si la res era a cuenta corriente.
            if res.condicion == CUENTA_CORRIENTE and res.proveedor_id:
                cuenta_repo.registrar_movimiento(
                    conn, entidad_tipo="PROVEEDOR", entidad_id=res.proveedor_id,
                    tipo=cuenta_repo.HABER, monto=res.costo_total,
                    referencia_tipo="RES", referencia_id=res.id,
                    nota=f"Anulación de {res.descripcion}")
            # Borrar cortes -> piezas -> res (respeta las FK).
            for pieza in pieza_repo.listar_por_res(conn, res_id):
                corte_repo.eliminar_por_pieza(conn, pieza.id)
            pieza_repo.eliminar_por_res(conn, res_id)
            res_repo.eliminar(conn, res_id)
    finally:
        conn.close()


def listar_reses(solo_abiertas: bool = False) -> list[Res]:
    conn = db_local.connect()
    try:
        return res_repo.listar(conn, solo_abiertas)
    finally:
        conn.close()


def obtener_res(res_id: str) -> Res | None:
    conn = db_local.connect()
    try:
        return res_repo.obtener(conn, res_id)
    finally:
        conn.close()


# --- Piezas -----------------------------------------------------------------

def agregar_pieza(res_id, nombre, margen_pct=None, fecha=None) -> str:
    """Agrega una pieza (Espalda, Pierna, ...) a una res abierta."""
    conn = db_local.connect()
    try:
        with conn:
            res = res_repo.obtener(conn, res_id)
            if res is None:
                raise DespieceError("La res no existe.")
            if res.estado != ABIERTA:
                raise DespieceError("La res está cerrada; no admite más piezas.")
            nom = normalizar_nombre(nombre or "")
            if not nom:
                raise DespieceError("La pieza necesita un nombre (ej. Espalda).")
            pieza = Pieza(
                id=nuevo_id(), res_id=res_id, nombre=nom,
                fecha=(fecha or ahora_local()), peso=Decimal("0"),
                estado=ABIERTA, margen_pct=_dec_opt(margen_pct))
            pieza_repo.crear(conn, pieza)
    finally:
        conn.close()
    return pieza.id


def listar_piezas(res_id: str) -> list[Pieza]:
    conn = db_local.connect()
    try:
        return pieza_repo.listar_por_res(conn, res_id)
    finally:
        conn.close()


# --- Cortes -----------------------------------------------------------------

def agregar_corte(pieza_id, descripcion, peso, precio_venta_kg=None,
                  margen_pct=None, es_desperdicio=False, producto_id=None) -> str:
    """Agrega un renglón de corte a una pieza abierta. El precio se toma
    explícito o se deriva del margen (corte > pieza > res)."""
    conn = db_local.connect()
    try:
        with conn:
            pieza = pieza_repo.obtener(conn, pieza_id)
            if pieza is None:
                raise DespieceError("La pieza no existe.")
            if pieza.estado != ABIERTA:
                raise DespieceError("La pieza ya se confirmó; no admite más cortes.")
            res = res_repo.obtener(conn, pieza.res_id)
            desc = normalizar_nombre(descripcion or "")
            if not desc:
                raise DespieceError("El corte necesita un nombre.")
            peso_d = _peso(peso, "peso del corte")
            if peso_d <= 0:
                raise DespieceError("El peso del corte debe ser mayor a 0.")
            margen_c = _dec_opt(margen_pct)
            precio = (Decimal("0.00") if es_desperdicio
                      else _resolver_precio(precio_venta_kg, margen_c, pieza, res))
            corte = Corte(
                id=nuevo_id(), pieza_id=pieza_id, descripcion=desc, peso=peso_d,
                precio_venta_kg=precio, producto_id=(producto_id or None),
                margen_pct=margen_c, costo_kg=Decimal("0"),
                es_desperdicio=bool(es_desperdicio), confirmado=False)
            corte_repo.crear(conn, corte)
            _refrescar_peso_pieza(conn, pieza_id)
    finally:
        conn.close()
    return corte.id


def editar_corte(corte_id, descripcion, peso, precio_venta_kg=None,
                 margen_pct=None, es_desperdicio=False) -> None:
    """Edita un corte borrador (no confirmado)."""
    conn = db_local.connect()
    try:
        with conn:
            corte = corte_repo.obtener(conn, corte_id)
            if corte is None:
                raise DespieceError("El corte no existe.")
            if corte.confirmado:
                raise DespieceError("El corte ya cargó stock; no se puede editar.")
            pieza = pieza_repo.obtener(conn, corte.pieza_id)
            res = res_repo.obtener(conn, pieza.res_id)
            desc = normalizar_nombre(descripcion or "")
            if not desc:
                raise DespieceError("El corte necesita un nombre.")
            corte.descripcion = desc
            corte.peso = _peso(peso, "peso del corte")
            if corte.peso <= 0:
                raise DespieceError("El peso del corte debe ser mayor a 0.")
            corte.margen_pct = _dec_opt(margen_pct)
            corte.es_desperdicio = bool(es_desperdicio)
            corte.precio_venta_kg = (
                Decimal("0.00") if corte.es_desperdicio
                else _resolver_precio(precio_venta_kg, corte.margen_pct, pieza, res))
            corte_repo.actualizar(conn, corte)
            _refrescar_peso_pieza(conn, corte.pieza_id)
    finally:
        conn.close()


def quitar_corte(corte_id) -> None:
    """Borra un corte borrador (no confirmado) y refresca el peso de la pieza."""
    conn = db_local.connect()
    try:
        with conn:
            corte = corte_repo.obtener(conn, corte_id)
            if corte is None:
                return
            if corte.confirmado:
                raise DespieceError("El corte ya cargó stock; no se puede quitar.")
            pieza_id = corte.pieza_id
            corte_repo.eliminar(conn, corte_id)
            _refrescar_peso_pieza(conn, pieza_id)
    finally:
        conn.close()


def listar_cortes(pieza_id: str) -> list[Corte]:
    conn = db_local.connect()
    try:
        return corte_repo.listar_por_pieza(conn, pieza_id)
    finally:
        conn.close()


def buscar_productos_carne(texto: str) -> list:
    """Productos de la categoría Carne que matchean el nombre. Es lo que sugiere
    el autocompletado al cargar un corte: solo cortes ya existentes, no todo el
    catálogo del kiosko."""
    conn = db_local.connect()
    try:
        cat_id = _categoria_carne_id(conn, crear=False)
        if cat_id is None:
            return []
        return [p for p in producto_repo.buscar_por_nombre(conn, texto)
                if p.categoria_id == cat_id]
    finally:
        conn.close()


# --- Confirmar pieza (carga el stock) ---------------------------------------

def confirmar_pieza(pieza_id) -> dict:
    """Confirma la pieza: cada corte con precio carga stock a su producto pesable
    (creándolo en la categoría 'Carne' si hace falta). Los desperdicios quedan
    registrados para el costeo pero no generan stock. Transacción única."""
    conn = db_local.connect()
    try:
        with conn:
            pieza = pieza_repo.obtener(conn, pieza_id)
            if pieza is None:
                raise DespieceError("La pieza no existe.")
            if pieza.estado == CERRADA:
                raise DespieceError("La pieza ya está confirmada.")
            res = res_repo.obtener(conn, pieza.res_id)
            cortes = corte_repo.listar_por_pieza(conn, pieza_id)
            if not cortes:
                raise DespieceError("La pieza no tiene cortes para confirmar.")

            cat_id = None
            confirmados = 0
            for c in cortes:
                if c.confirmado:
                    continue
                if c.es_desperdicio:
                    # Sin producto ni stock, pero deja el costo asignado.
                    c.costo_kg = res.costo_por_kg
                    c.confirmado = True
                    corte_repo.actualizar(conn, c)
                    continue
                if c.producto_id:
                    pid = c.producto_id
                    producto_repo.actualizar_costo(conn, pid, res.costo_por_kg)
                    producto_repo.actualizar_precio(conn, pid, c.precio_venta_kg)
                else:
                    if cat_id is None:
                        cat_id = _categoria_carne_id(conn)
                    pid = _crear_producto_corte(
                        conn, c.descripcion, cat_id, res.costo_por_kg,
                        c.precio_venta_kg)
                producto_repo.aumentar_stock(
                    conn, pid, c.peso,
                    tipo=movimiento_repo.DESPIECE, referencia_id=c.id)
                corte_repo.marcar_confirmado(conn, c.id, pid, res.costo_por_kg)
                confirmados += 1

            _refrescar_peso_pieza(conn, pieza_id)
            pieza_repo.cambiar_estado(conn, pieza_id, CERRADA)
    finally:
        conn.close()
    return {"pieza_id": pieza_id, "cortes_confirmados": confirmados}


# --- Resúmenes / ganancia ---------------------------------------------------

def resumen_pieza(pieza_id) -> dict:
    """Totales de una pieza: venta de cortes, costo (kg x costo/kg de la res) y
    ganancia. Sirve tanto para el borrador (en vivo) como para la ya confirmada."""
    conn = db_local.connect()
    try:
        pieza = pieza_repo.obtener(conn, pieza_id)
        if pieza is None:
            raise DespieceError("La pieza no existe.")
        res = res_repo.obtener(conn, pieza.res_id)
        cortes = corte_repo.listar_por_pieza(conn, pieza_id)
    finally:
        conn.close()
    venta = sum((c.subtotal for c in cortes), Decimal("0.00"))
    peso = sum((c.peso for c in cortes), Decimal("0"))
    costo = _plata(peso * res.costo_por_kg)
    return {
        "pieza": pieza, "cortes": cortes, "peso": peso,
        "venta": _plata(venta), "costo": costo,
        "ganancia": _plata(venta) - costo,
    }


def resumen_res(res_id) -> dict:
    """Totales de la res completa. `ganancia_piezas` usa el costo solo de los kg
    despiezados (como la planilla); `ganancia_real` descuenta la res entera
    (incluye la merma perdida entre res y piezas)."""
    conn = db_local.connect()
    try:
        res = res_repo.obtener(conn, res_id)
        if res is None:
            raise DespieceError("La res no existe.")
        piezas = pieza_repo.listar_por_res(conn, res_id)
        cortes_por_pieza = {
            p.id: corte_repo.listar_por_pieza(conn, p.id) for p in piezas}
    finally:
        conn.close()

    venta_total = Decimal("0.00")
    peso_piezas = Decimal("0")
    for p in piezas:
        for c in cortes_por_pieza[p.id]:
            venta_total += c.subtotal
            peso_piezas += c.peso
    venta_total = _plata(venta_total)
    costo_piezas = _plata(peso_piezas * res.costo_por_kg)
    merma_kg = res.peso_total - peso_piezas
    return {
        "res": res, "piezas": piezas,
        "venta_total": venta_total,
        "peso_piezas": peso_piezas,
        "costo_piezas": costo_piezas,
        "ganancia_piezas": venta_total - costo_piezas,
        "costo_res": res.costo_total,
        "ganancia_real": venta_total - res.costo_total,
        "merma_kg": merma_kg,
        "merma_costo": _plata(merma_kg * res.costo_por_kg),
    }


# --- Helpers internos -------------------------------------------------------

def _refrescar_peso_pieza(conn, pieza_id) -> Decimal:
    """Recalcula el peso de la pieza como la suma de los kg de sus cortes."""
    total = sum((c.peso for c in corte_repo.listar_por_pieza(conn, pieza_id)),
                Decimal("0")).quantize(KILOS, rounding=ROUND_HALF_UP)
    pieza_repo.actualizar_peso(conn, pieza_id, total)
    return total


def _categoria_carne_id(conn, crear: bool = True):
    """Devuelve el id de la categoría 'Carne'. Con crear=True la crea si no
    existe (al confirmar); con crear=False devuelve None si todavía no hay
    ninguna (al solo buscar, para no crearla de gusto)."""
    for cat in categoria_repo.listar_activas(conn):
        if cat.nombre.strip().lower() == CATEGORIA_CARNE.lower():
            return cat.id
    return categoria_repo.crear(conn, CATEGORIA_CARNE, None) if crear else None


def _crear_producto_corte(conn, nombre, categoria_id, costo, precio) -> str:
    """Crea el producto pesable de un corte (en la categoría Carne) con stock 0;
    el stock lo suma el llamador con aumentar_stock."""
    pid = nuevo_id()
    producto_repo.crear(conn, {
        "id": pid, "codigo_barra": None, "nombre": nombre,
        "categoria_id": categoria_id, "es_pesable": 1, "unidad_medida": "KG",
        "costo_compra": str(costo), "precio_venta": str(precio),
        "margen_pct": None, "ubicacion": None, "stock_actual": "0",
        "stock_minimo": "0", "controla_stock": 1, "controla_vencimiento": 0,
        "activo": 1, "updated_at": ahora_iso(),
    })
    return pid
