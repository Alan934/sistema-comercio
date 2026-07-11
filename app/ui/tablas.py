"""Utilidad de UI compartida: pinta una lista de filas EN TANDAS.

Crear widgets de CustomTkinter es caro (~6 ms por fila: cada fila son varios
frames/labels/botones-canvas). Dibujar cientos de una sola vez bloquea el event
loop y congela la app en una PC de gama baja. `PintorEnTandas` dibuja de a pocas
filas cediendo el control entre tanda y tanda (con `after`), así la ventana sigue
respondiendo y se puede navegar mientras la tabla se llena.

Uso típico en una vista:

    self._pintor = PintorEnTandas(self.tabla)      # una vez, en __init__
    ...
    for w in self.tabla.winfo_children(): w.destroy()
    self._pintor.pintar(filas, self._fila)         # filas: list; _fila(item, i)
"""

FILAS_POR_TANDA = 25  # cada tanda bloquea ~150 ms como mucho


class PintorEnTandas:
    def __init__(self, widget, filas_por_tanda: int = FILAS_POR_TANDA):
        self._widget = widget
        self._n = filas_por_tanda
        self._after_id = None

    def cancelar(self) -> None:
        """Frena un pintado en curso (p. ej. antes de re-dibujar)."""
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def pintar(self, items: list, construir_fila) -> None:
        """Dibuja `items` en tandas. `construir_fila(item, indice)` crea una fila."""
        self.cancelar()
        self._paso(items, 0, construir_fila)

    def _paso(self, items: list, desde: int, construir_fila) -> None:
        fin = min(desde + self._n, len(items))
        for i in range(desde, fin):
            construir_fila(items[i], i)
        if fin < len(items):
            self._after_id = self._widget.after(
                1, lambda: self._paso(items, fin, construir_fila))
        else:
            self._after_id = None
