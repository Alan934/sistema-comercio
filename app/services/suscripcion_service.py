"""Lógica de negocio de la suscripción del software.

Quién hace qué:
  - SUPER_ADMIN (quien vende el sistema): configura el contrato y registra los
    pagos que le hace el comercio.
  - ADMIN (el dueño del comercio): mira el estado y su historial, nada más.
  - EMPLEADO: no ve nada de esto.

Todo lo que se escribe va firmado (app/core/licencia.py) y se replica en un
sello en disco, así editar la base a mano no cambia el resultado.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from app.core import db_local, licencia, suscripcion
from app.core.utils import ahora_iso, ahora_local, nuevo_id, parse_fecha
from app.models.usuario import SUPER_ADMIN
from app.repositories import suscripcion_repo as repo

METODOS = ("EFECTIVO", "TRANSFERENCIA")


class SuscripcionError(Exception):
    """Error de negocio esperable."""


def puede_administrar(usuario) -> bool:
    """Solo el super administrador cobra: configura y carga pagos."""
    return getattr(usuario, "rol", None) == SUPER_ADMIN


# --- Fecha efectiva ---------------------------------------------------------

def hoy_efectivo(conn) -> date:
    """La fecha con la que se calcula todo: el máximo entre el reloj de la PC y
    la última fecha que el sistema vio. Atrasar el reloj de Windows no devuelve
    días. Si la marca quedara adelantada (reloj mal puesto), el primer sync la
    corrige con la fecha del servidor (ver registrar_fecha_servidor)."""
    hoy = date.today()
    fila = repo.obtener_config(conn)
    marca = _a_fecha(fila["ultima_fecha_vista"]) if fila is not None else None
    if marca is None:
        sello = licencia.leer_sello()
        marca = _a_fecha(sello.get("ultima_fecha_vista")) if sello else None

    efectiva = max(hoy, marca) if marca else hoy
    if fila is not None and (marca is None or efectiva > marca):
        with conn:
            repo.actualizar_marca(conn, efectiva.isoformat())
        _sellar(conn)
    return efectiva


def registrar_fecha_servidor(conn, fecha) -> None:
    """Fija la marca de agua con la fecha del servidor de la nube, que es
    autoritativa. Se llama desde el sync: además de impedir el atraso del reloj,
    repara una marca que hubiera quedado adelantada por un reloj mal puesto."""
    f = _a_fecha(fecha)
    if f is None or repo.obtener_config(conn) is None:
        return
    with conn:
        repo.actualizar_marca(conn, f.isoformat())
    _sellar(conn)


# --- Lectura ----------------------------------------------------------------

def _leer_config(conn):
    """Devuelve (fila, alterada). Si la fila fue borrada o modificada por fuera
    del sistema, la restaura desde el sello en disco; si no hay sello, informa
    que está alterada para que la interfaz lo muestre."""
    fila = repo.obtener_config(conn)
    sello = licencia.leer_sello()
    sello_sirve = bool(sello and sello.get("fecha_inicio"))

    if fila is None:
        if sello_sirve:
            with conn:
                repo.restaurar_config(conn, sello)
            return repo.obtener_config(conn), False
        return None, False

    if licencia.config_valida(fila):
        return fila, False

    # La fila no valida: alguien la tocó (o viene de una versión anterior).
    if sello_sirve:
        with conn:
            repo.restaurar_config(conn, sello)
        fila = repo.obtener_config(conn)
        return fila, not licencia.config_valida(fila)
    return fila, True


def _pagos_validos(conn):
    """Separa los pagos que la aplicación firmó de los que aparecieron por otro
    lado. Los inválidos NO suman cobertura."""
    filas = repo.listar_pagos(conn)
    validos = [f for f in filas if licencia.pago_valido(f)]
    return filas, validos


def estado_actual() -> suscripcion.EstadoSuscripcion:
    """Estado de la suscripción hoy. Es la función que consulta la interfaz."""
    conn = db_local.connect()
    try:
        return _estado(conn)
    finally:
        conn.close()


def _estado(conn) -> suscripcion.EstadoSuscripcion:
    fila, alterada = _leer_config(conn)
    todos, validos = _pagos_validos(conn)
    hoy = hoy_efectivo(conn)
    if alterada:
        # No se puede confiar en la fila: se ignora el override manual para que
        # nadie se declare "activo" editando la base. El resto se conserva y la
        # nube lo corrige en el próximo sync.
        fila = dict(_a_dict(fila), estado_manual=None)
    est = suscripcion.calcular(fila, validos, hoy)
    est.pagos_invalidos = len(todos) - len(validos)
    return est


def resumen() -> dict:
    """Estado + historial completo para la vista. Cada pago viene con su
    validez ya resuelta."""
    conn = db_local.connect()
    try:
        fila, alterada = _leer_config(conn)
        todos, validos = _pagos_validos(conn)
        est = _estado(conn)
        pagos = [{
            "id": p["id"],
            "fecha": p["fecha"],
            "meses": p["meses"],
            "monto": Decimal(str(p["monto"] or 0)),
            "metodo": p["metodo"],
            "nota": p["nota"],
            "registrado_por": p["registrado_por"],
            "anulado": bool(p["anulado"]),
            "valido": licencia.pago_valido(p),
        } for p in todos]
        cfg = _a_dict(fila)
        return {
            "estado": est,
            "pagos": pagos,
            "config_alterada": alterada,
            "comercio": cfg.get("comercio") or "",
            "datos_pago": cfg.get("datos_pago") or "",
            "estado_manual": cfg.get("estado_manual") or "",
            "gracia_dias": cfg.get("gracia_dias") or suscripcion.GRACIA_DIAS_DEFECTO,
        }
    finally:
        conn.close()


# --- Escritura (solo super admin) -------------------------------------------

def configurar(rol_actor: str, fecha_inicio: str, monto_mensual,
               gracia_dias=suscripcion.GRACIA_DIAS_DEFECTO, datos_pago: str = "",
               comercio: str = "", estado_manual: str | None = None) -> None:
    """Alta o cambio del contrato. `fecha_inicio` acepta dd/mm/aaaa o ISO."""
    _exigir_super_admin(rol_actor)
    iso = parse_fecha(fecha_inicio)
    if not iso:
        raise SuscripcionError(
            "Poné una fecha de inicio válida (dd/mm/aaaa).")
    monto = _a_monto(monto_mensual, "El monto mensual")
    try:
        gracia = int(gracia_dias)
    except (TypeError, ValueError):
        raise SuscripcionError("Los días de gracia tienen que ser un número.")
    if gracia < 0 or gracia > 365:
        raise SuscripcionError("Los días de gracia van de 0 a 365.")

    manual = (estado_manual or "").strip().upper() or None
    if manual not in (None, suscripcion.MANUAL_ACTIVA, suscripcion.MANUAL_SUSPENDIDA):
        raise SuscripcionError("Estado manual desconocido.")

    cfg = {
        "id": repo.ID_CONFIG,
        "comercio": (comercio or "").strip() or None,
        "fecha_inicio": iso,
        "monto_mensual": str(monto),
        "gracia_dias": gracia,
        "datos_pago": (datos_pago or "").strip() or None,
        "estado_manual": manual,
        "ultima_fecha_vista": None,
        "firma": None,
        "updated_at": ahora_iso(),
    }
    cfg["firma"] = licencia.firmar_config(cfg)

    conn = db_local.connect()
    try:
        # Conserva la marca de agua que ya tuviera esta PC.
        actual = repo.obtener_config(conn)
        if actual is not None:
            cfg["ultima_fecha_vista"] = actual["ultima_fecha_vista"]
        with conn:
            repo.guardar_config(conn, cfg)
        _sellar(conn)
    finally:
        conn.close()


def registrar_pago(rol_actor: str, meses, monto, metodo: str = "EFECTIVO",
                   nota: str = "", registrado_por: str = "") -> str:
    """Carga un cobro: `meses` de crédito que corren desde donde haya quedado
    la cobertura. Devuelve el id del pago."""
    _exigir_super_admin(rol_actor)
    try:
        n = int(meses)
    except (TypeError, ValueError):
        raise SuscripcionError("Indicá cuántos meses cubre el pago.")
    if n < 1 or n > suscripcion.MESES_MAXIMO:
        raise SuscripcionError(
            f"Los meses van de 1 a {suscripcion.MESES_MAXIMO}.")
    importe = _a_monto(monto, "El monto")
    met = (metodo or "").strip().upper() or "EFECTIVO"
    if met not in METODOS:
        raise SuscripcionError("Medio de pago desconocido.")

    pago = {
        "id": nuevo_id(),
        "fecha": ahora_local(),
        "meses": n,
        "monto": str(importe),
        "metodo": met,
        "nota": (nota or "").strip() or None,
        "registrado_por": (registrado_por or "").strip() or None,
        "anulado": 0,
        "firma": None,
        "created_at": ahora_iso(),
    }
    pago["firma"] = licencia.firmar_pago(pago)

    conn = db_local.connect()
    try:
        if repo.obtener_config(conn) is None:
            raise SuscripcionError(
                "Primero configurá la suscripción (fecha de inicio y monto).")
        with conn:
            repo.crear_pago(conn, pago)
    finally:
        conn.close()
    return pago["id"]


def anular_pago(rol_actor: str, pago_id: str) -> None:
    """Deja el pago sin efecto (no se borra: queda en el historial)."""
    _exigir_super_admin(rol_actor)
    conn = db_local.connect()
    try:
        fila = repo.obtener_pago(conn, pago_id)
        if fila is None:
            raise SuscripcionError("Ese pago ya no existe.")
        if fila["anulado"]:
            raise SuscripcionError("Ese pago ya estaba anulado.")
        firma = licencia.firmar_pago(dict(_a_dict(fila), anulado=1))
        with conn:
            repo.anular_pago(conn, pago_id, firma)
    finally:
        conn.close()


# --- Auxiliares -------------------------------------------------------------

def _exigir_super_admin(rol_actor: str) -> None:
    if rol_actor != SUPER_ADMIN:
        raise SuscripcionError(
            "Solo el super administrador puede administrar la suscripción.")


def _sellar(conn) -> None:
    fila = repo.obtener_config(conn)
    if fila is not None:
        licencia.guardar_sello(fila)


def _a_monto(valor, etiqueta: str) -> Decimal:
    try:
        monto = Decimal(str(valor).replace(",", ".").strip() or "0")
    except (InvalidOperation, AttributeError):
        raise SuscripcionError(f"{etiqueta} tiene que ser un número.")
    if monto < 0:
        raise SuscripcionError(f"{etiqueta} no puede ser negativo.")
    return monto.quantize(Decimal("0.01"))


def _a_fecha(valor) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _a_dict(fila) -> dict:
    if fila is None:
        return {}
    if isinstance(fila, dict):
        return dict(fila)
    return {k: fila[k] for k in fila.keys()}
