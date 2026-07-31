"""Cálculo del estado de la suscripción del software.

Lógica pura: no toca la base ni la interfaz, solo fechas y números, así que se
puede probar sola.

Modelo: cada pago compra N MESES DE CRÉDITO (no un período concreto). La
cobertura es `fecha_inicio + suma de los meses pagados`. De ahí sale todo: los
pagos pueden llegar en cualquier orden, pagar doce meses juntos es un solo
registro con meses=12, y nunca quedan huecos ni períodos superpuestos.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

# Estados posibles, de mejor a peor.
SIN_CONFIGURAR = "SIN_CONFIGURAR"   # todavía no se fijó fecha de inicio: no molesta a nadie
AL_DIA = "AL_DIA"
POR_VENCER = "POR_VENCER"           # entra en la ventana de aviso previo
VENCIDA = "VENCIDA"                 # pasó el vencimiento, corre el plazo de gracia
SUSPENDIDA = "SUSPENDIDA"           # se agotó el plazo de gracia

ETIQUETA_ESTADO = {
    SIN_CONFIGURAR: "Sin configurar",
    AL_DIA: "Al día",
    POR_VENCER: "Por vencer",
    VENCIDA: "Vencida",
    SUSPENDIDA: "Suspendida",
}

# Con cuántos días de anticipación se empieza a avisar.
DIAS_AVISO_PREVIO = 7
# Cuánto tiempo se tolera el atraso antes de suspender.
GRACIA_DIAS_DEFECTO = 30
# Tope de meses que se pueden pagar de una vez.
MESES_MAXIMO = 12

# Overrides manuales que puede fijar el super administrador.
MANUAL_ACTIVA = "ACTIVA"
MANUAL_SUSPENDIDA = "SUSPENDIDA"


def sumar_meses(f: date, meses: int) -> date:
    """Suma meses de calendario conservando el día. Si el día no existe en el
    mes destino, cae al último día de ese mes (31/01 + 1 mes = 28/02)."""
    total = f.month - 1 + meses
    anio = f.year + total // 12
    mes = total % 12 + 1
    dia = min(f.day, _dias_del_mes(anio, mes))
    return date(anio, mes, dia)


def _dias_del_mes(anio: int, mes: int) -> int:
    if mes == 12:
        return 31
    return (date(anio, mes + 1, 1) - date(anio, mes, 1)).days


@dataclass
class EstadoSuscripcion:
    """Foto del estado de la suscripción en un día dado."""
    estado: str
    meses_pagados: int = 0
    fecha_inicio: date | None = None
    cubierto_hasta: date | None = None     # primer día NO cubierto
    fecha_suspension: date | None = None   # cuándo se corta si no paga
    dias_restantes: int = 0                # negativo si ya venció
    dias_de_atraso: int = 0
    dias_para_suspension: int = 0
    monto_mensual: Decimal = Decimal("0")
    gracia_dias: int = GRACIA_DIAS_DEFECTO
    manual: bool = False                   # el estado lo forzó el super admin
    pagos_invalidos: int = 0               # firmas que no validaron

    @property
    def configurada(self) -> bool:
        return self.estado != SIN_CONFIGURAR

    @property
    def suspendida(self) -> bool:
        return self.estado == SUSPENDIDA

    @property
    def vencida(self) -> bool:
        """Vencida o suspendida: en ambos casos hay deuda."""
        return self.estado in (VENCIDA, SUSPENDIDA)

    @property
    def necesita_aviso(self) -> bool:
        return self.estado in (POR_VENCER, VENCIDA, SUSPENDIDA)

    @property
    def etiqueta(self) -> str:
        return ETIQUETA_ESTADO.get(self.estado, self.estado)


def calcular(config, pagos, hoy: date) -> EstadoSuscripcion:
    """Estado de la suscripción.

    `config` es la fila de configuración (dict o sqlite3.Row) o None.
    `pagos` son los pagos YA VALIDADOS (firma correcta): el descarte de los
    adulterados lo hace quien lee la base, acá solo se ignoran los anulados.
    `hoy` debe ser la fecha efectiva (ver suscripcion_service.hoy_efectivo),
    no `date.today()` a secas, para que atrasar el reloj no regale días.
    """
    if config is None or not _valor(config, "fecha_inicio"):
        return EstadoSuscripcion(estado=SIN_CONFIGURAR)

    inicio = _a_fecha(_valor(config, "fecha_inicio"))
    if inicio is None:
        return EstadoSuscripcion(estado=SIN_CONFIGURAR)

    gracia = _a_entero(_valor(config, "gracia_dias"), GRACIA_DIAS_DEFECTO)
    monto = _a_decimal(_valor(config, "monto_mensual"))
    manual = (_valor(config, "estado_manual") or "").strip().upper() or None

    meses = sum(_a_entero(_valor(p, "meses"), 0) for p in pagos
                if not _a_entero(_valor(p, "anulado"), 0))
    cubierto = sumar_meses(inicio, meses)
    suspende_el = cubierto + timedelta(days=gracia)

    restantes = (cubierto - hoy).days
    atraso = max(0, -restantes)

    if manual == MANUAL_SUSPENDIDA:
        estado = SUSPENDIDA
    elif manual == MANUAL_ACTIVA:
        estado = AL_DIA
    elif atraso > gracia:
        estado = SUSPENDIDA
    elif restantes < 0:
        estado = VENCIDA
    elif restantes <= DIAS_AVISO_PREVIO:
        estado = POR_VENCER
    else:
        estado = AL_DIA

    return EstadoSuscripcion(
        estado=estado,
        meses_pagados=meses,
        fecha_inicio=inicio,
        cubierto_hasta=cubierto,
        fecha_suspension=suspende_el,
        dias_restantes=restantes,
        dias_de_atraso=atraso,
        dias_para_suspension=max(0, gracia - atraso) if atraso else 0,
        monto_mensual=monto,
        gracia_dias=gracia,
        manual=manual is not None,
    )


def meses_adeudados(estado: EstadoSuscripcion, hoy: date) -> int:
    """Cuántos meses tendría que pagar para volver a estar al día. 0 si no debe
    nada. Se cuentan meses enteros: un solo día de atraso ya es un mes."""
    if estado.cubierto_hasta is None or estado.dias_restantes >= 0:
        return 0
    n = 0
    tope = estado.cubierto_hasta
    while tope <= hoy:
        n += 1
        tope = sumar_meses(estado.cubierto_hasta, n)
    return n


# --- Auxiliares -------------------------------------------------------------

def _valor(fila, clave):
    """Lee una clave de un dict o de un sqlite3.Row indistintamente."""
    try:
        return fila[clave]
    except (KeyError, IndexError):
        return None


def _a_fecha(valor) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _a_entero(valor, por_defecto: int = 0) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return por_defecto


def _a_decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor if valor not in (None, "") else 0))
    except Exception:  # noqa: BLE001 - valor corrupto en base: se toma cero
        return Decimal("0")
