"""Mide el rendimiento de las operaciones que hace la app de verdad.

Pensado para correr en CADA PC (la gama baja de la clienta y otra más potente)
y comparar los números. NO abre la GUI: mide el costo real de la base y la
memoria del proceso, que es lo que se nota en una PC con 4 GB de RAM.

Requisito: tener productos cargados (usá primero  python seed_productos.py).

Uso:
    python bench_rendimiento.py
    python bench_rendimiento.py --db ruta.db   # medir sobre otra base
"""
import argparse
import ctypes
import statistics
import sys
import time
from pathlib import Path


def _memoria_mb() -> float | None:
    """Working set (RAM real) del proceso en MB, vía la API de Windows.
    Devuelve None si no se puede (otra plataforma)."""
    try:
        class _MEM(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong),
                        ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        m = _MEM()
        m.cb = ctypes.sizeof(m)
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_MEM), ctypes.c_ulong]
        if psapi.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(m), m.cb):
            return m.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return None


def _medir(descripcion: str, fn, repeticiones: int) -> None:
    """Corre `fn` N veces y reporta tiempo promedio y máximo por llamada (ms)."""
    tiempos = []
    for _ in range(repeticiones):
        t0 = time.perf_counter()
        fn()
        tiempos.append((time.perf_counter() - t0) * 1000)
    prom = statistics.mean(tiempos)
    peor = max(tiempos)
    print(f"  {descripcion:<38} prom {prom:7.2f} ms   peor {peor:7.2f} ms"
          f"   ({repeticiones}x)")


def correr() -> None:
    from app.core import db_local
    from app.services import stock_service, venta_service

    # --- Arranque en frío: abrir base y leer el catálogo completo -----------
    t0 = time.perf_counter()
    db_local.init_db()
    productos = stock_service.listar_productos()
    arranque = (time.perf_counter() - t0) * 1000
    total = len(productos)

    print("=" * 66)
    print("  BENCHMARK DE RENDIMIENTO - Kiosko POS")
    print("=" * 66)
    print(f"  Productos en la base: {total}")
    if total == 0:
        print("\n  (No hay productos. Corre primero:  python seed_productos.py)")
        return
    print(f"  Arranque en frio (abrir base + leer catalogo): {arranque:7.2f} ms")
    print("-" * 66)

    # Muestras reales de códigos y nombres para las búsquedas.
    codigos = [p.codigo_barra for p in productos if p.codigo_barra][:200] or [""]
    letras = ["a", "co", "leche", "jam", "gase", "z", "arcor", "500"]

    # Vista Stock: listar todo el catálogo (lo que se ve al entrar a Stock).
    _medir("Vista Stock (listar catalogo)",
           stock_service.listar_productos, 20)

    # Escaneo con la pistolita: buscar por código exacto.
    idx = {"i": 0}
    def _escanear():
        c = codigos[idx["i"] % len(codigos)]
        idx["i"] += 1
        venta_service.buscar_por_codigo(c)
    _medir("Escaneo por codigo (pistolita)", _escanear, 300)

    # Autocompletado de la caja: buscar por nombre parcial.
    jdx = {"i": 0}
    def _autocompletar():
        t = letras[jdx["i"] % len(letras)]
        jdx["i"] += 1
        venta_service.buscar_por_nombre(t)
    _medir("Autocompletado por nombre", _autocompletar, 100)

    # Alertas que se recalculan al entrar a Stock.
    _medir("Alertas de stock bajo", stock_service.alertas_stock_bajo, 20)
    _medir("Alertas de vencimientos", lambda: stock_service.alertas_vencimientos(7), 20)

    print("-" * 66)
    ram = _memoria_mb()
    if ram is not None:
        print(f"  RAM del proceso Python (working set): {ram:7.1f} MB")
        print("  (Nota: el .exe empaquetado ronda ~68 MB; este numero es solo")
        print("   para COMPARAR entre PCs, no es el consumo del Kiosko.exe.)")
    print("=" * 66)
    print("  Guarda esta salida por PC y comparalas. Un tiempo 'peor' alto y")
    print("  estable = la PC lenta; picos aislados = disco/antivirus.")
    print("=" * 66)


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark de rendimiento del POS.")
    ap.add_argument("--db", metavar="RUTA", help="Base a medir (default: la de la app).")
    args = ap.parse_args()
    if args.db:
        from config import settings
        p = Path(args.db).resolve()
        settings.DATA_DIR = p.parent
        settings.LOCAL_DB_PATH = p
    correr()


if __name__ == "__main__":
    sys.exit(main())
