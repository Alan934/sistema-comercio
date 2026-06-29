"""Carrito de venta: estado en memoria de la caja. Sin acceso a base de datos.

Toda la aritmética de dinero usa Decimal y se redondea a centavos al calcular
subtotales, para evitar el arrastre de errores de punto flotante.
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from app.models.producto import Producto

CENTAVOS = Decimal("0.01")


def _a_centavos(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


@dataclass
class ItemCarrito:
    producto_id: str
    descripcion: str
    cantidad: Decimal          # unidades, o kg si es pesable (ej. 0.750)
    precio_unitario: Decimal   # por unidad o por kg
    costo_unitario: Decimal    # snapshot para calcular ganancia
    es_pesable: bool
    controla_stock: bool

    @property
    def subtotal(self) -> Decimal:
        return _a_centavos(self.precio_unitario * self.cantidad)

    @property
    def costo_total(self) -> Decimal:
        return _a_centavos(self.costo_unitario * self.cantidad)


@dataclass
class Carrito:
    items: list[ItemCarrito] = field(default_factory=list)

    def agregar(self, producto: Producto, cantidad: Decimal) -> ItemCarrito:
        """Agrega un producto. Si NO es pesable y ya está en el carrito,
        acumula la cantidad en la misma línea (comportamiento típico de caja)."""
        if not producto.es_pesable:
            for item in self.items:
                if item.producto_id == producto.id:
                    item.cantidad += cantidad
                    return item

        item = ItemCarrito(
            producto_id=producto.id,
            descripcion=producto.nombre,
            cantidad=cantidad,
            precio_unitario=producto.precio_venta,
            costo_unitario=producto.costo_compra,
            es_pesable=producto.es_pesable,
            controla_stock=producto.controla_stock,
        )
        self.items.append(item)
        return item

    def quitar(self, indice: int) -> None:
        del self.items[indice]

    def cambiar_cantidad(self, indice: int, cantidad: Decimal) -> None:
        """Fija la cantidad de un ítem. Si llega a cero (o menos), lo quita."""
        if cantidad <= 0:
            self.quitar(indice)
        else:
            self.items[indice].cantidad = cantidad

    def vaciar(self) -> None:
        self.items.clear()

    def esta_vacio(self) -> bool:
        return len(self.items) == 0

    @property
    def subtotal(self) -> Decimal:
        return _a_centavos(sum((i.subtotal for i in self.items), Decimal("0")))

    @property
    def costo_total(self) -> Decimal:
        return _a_centavos(sum((i.costo_total for i in self.items), Decimal("0")))

    @property
    def total(self) -> Decimal:
        # Por ahora total == subtotal. Cuando agreguemos descuentos, se resta acá.
        return self.subtotal
