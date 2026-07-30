# Balanza etiquetadora Systel Cuora MAX — configuración

Guía para dejar la balanza imprimiendo etiquetas que el sistema pueda escanear en
la Caja. Referencias de página al manual `Cuora-MAX-ST-manual_ESP.pdf`.

**Cómo funciona, en una línea:** la balanza imprime un código de barras que lleva
adentro el **número del corte (PLU)** y el **importe**. La Caja lo lee, reconoce
el corte, cobra el importe impreso y descuenta los kg del stock. Un escaneo, sin
tipear el peso.

---

## Antes de empezar

Para entrar al menú: tecla **Aceptar** → elegir usuario **Administrador** →
**clave** (de fábrica es `1234`, pág. 27).

La configuración de la Parte A se hace **una sola vez**. La Parte B (cargar los
cortes) se repite cada vez que aparece un corte nuevo.

---

## PARTE A — Configuración del equipo (una sola vez)

Los tres primeros son los que hacen que la etiqueta sea legible por el sistema.
Si alguno está mal, no funciona nada.

### A1. Coma de precio → `6.0` ⚠️ CRÍTICO

`8. configurar equipo` → `5. Moneda` → **Coma de precio** (pág. 41)

| Opción | Muestra | Sirve? |
|---|---|---|
| `4.2` | `$0000.00` | ❌ tope $9.999,99 — no alcanza para carne a $19.500/kg |
| `6.0` | `$ 000000` | ✅ **esta** |

El sistema está programado para leer el importe en **pesos enteros**, que es lo
que manda el modo `6.0`. Si algún día se cambia a `4.2`, hay que avisar: se toca
una línea en `app/core/balanza.py` (`IMPORTE_DECIMALES = 2`).

Acá también se define el símbolo monetario (`$`).

### A2. Código de barras de venta por peso → `20PPPPIIIIII` ⚠️ CRÍTICO

`8. configurar equipo` → `2. Balanza` → `2. codigo de barras` → `1. Venta por Peso`
(págs. 38-39)

Son 12 dígitos configurables. Tiene que quedar exactamente:

```
2 0 P P P P I I I I I I
└┬┘ └──┬──┘ └────┬────┘
 │     │         └── I = Importe total (6 dígitos)
 │     └── P = Código de PLU (4 dígitos)
 └── cabecera fija "20" = artículo pesable
```

Es **la configuración de fábrica**, así que lo más probable es que ya esté bien:
solo hay que entrar y verificar. Las letras se eligen con las teclas de escritura
y el teclado numérico.

No hace falta tocar `2. Venta por Unidad` ni `3. Suma de Artículos` — el sistema
solo lee la cabecera `20`.

### A3. Imprimir códigos de barras en tickets → `SI` ⚠️ CRÍTICO

`8. configurar equipo` → `2. Balanza` → `2. codigo de barras` → `4. Imprimir en Tickets`
→ **`2. SI`** (pág. 41)

Esta opción existe para ahorrar papel. Si queda en `NO`, **la etiqueta sale sin
código de barras** y no hay nada que escanear. El manual lo aclara expresamente.

### A4. Precios permitidos → `1. Solo Lista 1` (recomendado)

`8. configurar equipo` → `2. Balanza` → `4. Precios permitidos` (pág. 39)

| Opción | Qué habilita |
|---|---|
| `1. Solo Lista 1` | ✅ solo el precio cargado en el PLU |
| `2. Solo Lista 1 y 2` | agrega el precio alternativo (mayorista) |
| `3. Listas y Manual` | ⚠️ permite tipear un precio a mano en la venta |

**Recomendado `1`.** Con la opción `3`, alguien puede pesar con un precio inventado
que no coincide con el del sistema: la plata cobrada saldría bien (se cobra el
importe impreso) pero **los kg descontados del stock saldrían mal**, porque el
sistema deduce el peso dividiendo por *su* precio.

### A5. Tipo de papel → `1. papel continuo`

`8. configurar equipo` → `1. menu impresion` → `1. Tipo de papel` (pág. 36)

Las opciones son `1. papel continuo` y `2. no imprimir`. Tiene que estar en `1`
(la opción `2` desactiva la impresión por completo). El equipo reconoce solo si
lo cargado es papel continuo o etiqueta autoadhesiva.

### A6. Reloj

`8. configurar equipo` → `2. Balanza` → `1. Actualizar reloj` (pág. 37)

No afecta al escaneo, pero la etiqueta imprime fecha y hora de envasado. En la
etiqueta de prueba figuraba `16/Jul/2026 20:36` — conviene que sea la real.

### A7. Datos del comercio — el pie de la etiqueta

`8. configurar equipo` → `4. Datos del comercio` (pág. 41)

Hoy la etiqueta sale con los textos de fábrica. Son **dos líneas de texto libre**
que se imprimen al pie de cada etiqueta y ticket:

| Campo | Qué dice hoy | Qué poner |
|---|---|---|
| **Línea 1** | `NOMBRE COMERCIO` | El nombre del negocio |
| **Línea 2** | `Direccion - Telefono - Fax` | Dirección, teléfono, lo que corresponda |

Se escriben con el teclado de letras de la balanza. La Línea 1 admite hasta 18
caracteres; si el nombre es largo, conviene abreviar.

Estas dos líneas también salen en los listados que imprime la balanza.

### A8. Conectividad → NO activar la espera de sincronización

`8. configurar equipo` → `3. conectividad` (pág. 40)

**Dejar como está.** Esta sección es para el software propietario de Systel, que
no usamos. El punto importante: **no activar** la opción *"esperar sincronización
de datos al encender/inicio"*. Si se activa, la balanza queda esperando que una PC
le actualice las bases y **no deja operar** hasta que eso pase — y como nadie va a
sincronizar, quedaría trabada mostrando "ACCEDIENDO A LA RED".

Si llegara a pasar: `SALE` para saltear el mensaje, después la clave de
Administrador para operar sin red.

---

## PARTE B — Cargar los cortes (PLU)

`4. Artículos / PLU (Alta-Baja-Modificación)` → `2. editar/crear PLU` (págs. 32-34)

Los campos son estos:

| # | Campo | Qué poner |
|---|---|---|
| 1 | **N° de PLU** | La *posición de memoria* (1 a 8000). Con las flechas se navega por las vacías. |
| 2 | **Código** | ⚠️ **Este es el número que va en el código de barras.** Ver el recuadro de abajo. |
| 3 | **N° sector** | `2 CARNICERIA` para carne, `1 FIAMBRES Y LACTEOS` para fiambre (vienen precargados). |
| 4 | **Descripción** | El nombre del corte, **igual al del sistema**. |
| 5 | **Tipo** | `2. VENTA POR PESO` ← obligatorio, es lo que dispara la cabecera `20`. |
| 6 | **Precio Lista 1** | El precio por kg. **Nunca 0.** |
| 7 | **Precio Lista 2** | Vacío (es el precio alternativo/mayorista). |
| 8 | **Días de vencimiento** | Días que dura el producto. Es lo que completa el `Vto:` de la etiqueta (ver D2). |
| 9 | **TARA** | `0`, salvo que se use una bandeja fija (se descuenta del peso). |
| 10 | **EAN** | **`1. USAR EAN GRAL.`** ← obligatorio, hace que use el formato de A2. |

Termina con "Operación Exitosa" y se pasa al siguiente corte.

> ### ⚠️ Ojo: son DOS números distintos
>
> La balanza maneja **"N° de PLU"** y **"Código de PLU"** por separado. En el
> listado de artículos que imprime aparecen los dos:
>
> ```
> Numero de PLU     15        ← posición en memoria
> Codigo de PLU    201        ← código del artículo
> ```
>
> La leyenda de campos del código de barras dice **`P = Código de PLU`** (pág. 39),
> y el ticket de ejemplo del manual muestra `(C.PLU) - Descripcion: (0261) - DURAZNO`.
> O sea que **lo que viaja en el código de barras es el Código, no la posición.**
>
> **Verificalo antes de cargar los 15 cortes** (5 minutos, y evita rehacer todo):
> cargá un artículo de prueba con los dos números **distintos a propósito** —
> por ejemplo N° de PLU `1` y Código `250`— pesá algo, y mirá qué dígitos salen
> en las posiciones 3 a 6 del código de barras. Si salen `0250`, el número que hay
> que poner en el sistema es el **Código**. Para leerlo rápido:
>
> ```bash
> python decodificar_etiqueta.py 2002500123456
> ```
>
> Lo más simple, si la balanza lo permite: **poné el mismo número en los dos
> campos** y te olvidás del tema.

> **Precio 0 = "precio abierto".** Si se deja en cero, la balanza va a pedir el
> precio a mano en **cada** venta de ese artículo (pág. 33). No es lo que queremos.

### Lista de PLU

Números sugeridos: carne del 1 al 19, fiambres del 20 en adelante. Dejar huecos
para lo que venga después. **Conviene imprimir esta tabla y pegarla al lado de la
balanza.**

| PLU | Corte | Precio/kg | ✔ balanza | ✔ sistema |
|----|----|----|----|----|
| 1 | Asado 1ra | $19.500 | ☐ | ☐ |
| 2 | Asado Criollo | $15.000 | ☐ | ☐ |
| 3 | Bifes | $19.500 | ☐ | ☐ |
| 4 | Carne Moler | $10.500 | ☐ | ☐ |
| 5 | Costeleta | $17.000 | ☐ | ☐ |
| 6 | Costilla | $17.000 | ☐ | ☐ |
| 7 | Grasa | $3.000 | ☐ | ☐ |
| 8 | LTira | $19.500 | ☐ | ☐ |
| 9 | Lomo Chato | $19.000 | ☐ | ☐ |
| 10 | Osobuco | $9.500 | ☐ | ☐ |
| 11 | Paleta | $19.000 | ☐ | ☐ |
| 12 | Recorte | $10.500 | ☐ | ☐ |
| 13 | Recorte Moler | $10.500 | ☐ | ☐ |
| 14 | Tortuguita | $15.000 | ☐ | ☐ |
| 20 | Paleta Común (fiambre) | $2.700 | ☐ | ☐ |

*(precios al 2026-07-17 — verificar contra el sistema antes de cargar)*

### Del lado del sistema

- **Cortes que ya existen:** Stock → ✏ Editar → tildar "Se vende al peso" →
  campo **"PLU balanza"** → el número → Guardar.
- **Cortes nuevos:** cargarlos con su PLU directamente en el diálogo de corte de
  Carne. Al confirmar la pieza, el producto se crea con el número ya puesto.

El sistema no deja repetir un número: avisa qué producto o qué corte ya lo usa.

---

## PARTE C — Accesos directos (opcional, muy recomendado)

`4. Artículos / PLU` → `4. Accesos directos` → `1. ASIGNAR ACCESOS DIRECTOS`
(pág. 35)

Permite asignar hasta **60 teclas** (las del sector con letras) a los cortes más
vendidos: se elige el PLU y se presiona la tecla que lo va a llamar. Son 30
directos + 30 con 2ª Función.

Para quien atiende, es la diferencia entre acordarse de un número y apretar una
tecla. Vale la pena cargar ahí los 8 o 10 cortes de mayor salida.

---

## PARTE D — Los datos que salen en la etiqueta

La etiqueta de referencia salió con varios campos vacíos o con textos de fábrica.
Acá está cada uno y dónde se completa.

```
        Venta por Peso                  ← título fijo del formato
Env:  16/Jul/2026  Hora: 20:36          ← D1  reloj del equipo
Vto:  ----         TARA: 0.000kg(T)     ← D2  días de vencimiento · D3 tara
PLU:  0            PESO: 1.005kg(N)     ← D4  artículo elegido al pesar
                   PRECIO/kg: 11000     ← del PLU (Precio Lista 1)
        IMPORTE ($)  11055              ← calculado
   |||||||||||||||||||||||              ← A2 + A3 (código de barras)
      2000000110554
        NOMBRE COMERCIO                 ← A7  Línea 1
   Direccion - Telefono - Fax           ← A7  Línea 2
```

### D1. `Env:` y `Hora:` — fecha de envasado

Sale del reloj del equipo. Si está mal, se corrige en **A6**
(`8. configurar equipo` → `2. Balanza` → `1. Actualizar reloj`).

### D2. `Vto:` — fecha de vencimiento

En la etiqueta de referencia dice `----` porque el artículo tiene **días de
vencimiento = 0**. Es un campo **por artículo**, no general: se carga al crear o
editar el PLU (paso 8 de la Parte B).

La balanza calcula `Vto: = fecha de envasado + días`. Por ejemplo, con 5 días en
un corte envasado el 16/Jul, la etiqueta va a decir `Vto: 21/Jul/2026`.

Para ver cómo quedó cargado cada artículo, la balanza imprime el listado completo
con `3. Listados` → `PLUs por sector` → `1. Completo`, que muestra por cada PLU:
precios, tipo de venta, sector, N° de PLU, Código de PLU, días de vencimiento y tara.

### D3. `TARA` — peso del envase

También es por artículo (paso 9 de la Parte B). Si se pesa siempre con la misma
bandeja o bolsa, se carga acá y la balanza lo descuenta solo. En `0.000kg` no
descuenta nada. El tope es el 5% de la capacidad del equipo (o sea 1,5 kg en una
balanza de 30 kg).

### D4. `PLU:` — el artículo

Aparece vacío cuando se pesa **sin elegir artículo**. Con el PLU cargado y
seleccionado, sale el número y la descripción del corte. Si este campo está
vacío, el código de barras lleva PLU `0000` y el sistema no puede saber qué es.

### Lo que NO se puede cambiar

El diseño del formato de etiqueta (qué campos, en qué orden, el título "Venta por
Peso") no se configura desde el teclado: viene con el formato de fábrica. Lo
editable es el **contenido** de cada campo, que es todo lo de arriba.

---

## PARTE E — Verificar que quedó bien

1. Cargar un corte de prueba (por ejemplo Paleta, PLU 11, $19.000/kg).
2. Pesar 0,500 kg e imprimir la etiqueta.
3. Mirar el código impreso: tiene que empezar con **`20`**, seguir con el PLU en
   4 dígitos (`0011`) y después el importe en 6 (`009500`):

   ```
   Paleta, PLU 11, 0,500 kg × $19.000 = $9.500
   → 2000110095000
     └┬┘└─┬┘└──┬─┘└ dígito verificador
      │   │    └ importe $9.500
      │   └ PLU 11
      └ pesable
   ```

   Otros ejemplos: Asado 1ra (PLU 1) 1,250 kg × $19.500 = $24.375 →
   `2000010243754`. Carne Moler (PLU 4) 2 kg × $10.500 = $21.000 → `2000040210009`.

4. Escanear esa etiqueta en la Caja. Tiene que entrar sola, **sin pedir el peso**,
   con el nombre del corte y el importe exacto de la etiqueta.

Si la Caja avisa **"Etiqueta sin artículo"**, se pesó sin seleccionar el PLU.
Si avisa **"PLU sin producto"**, falta cargar ese número en el producto del sistema.

### Si algo no cierra

Hay una herramienta que decodifica cualquier código y dice exactamente qué trae:

```bash
python decodificar_etiqueta.py 2000110095000
```

Sin argumentos entra en modo interactivo y se puede escanear con la pistolita
directo sobre la consola, una etiqueta atrás de otra. Informa si el código es
válido (y si no, **por qué** no), qué PLU e importe lleva, a qué producto
corresponde, cuántos kg deduce y si el precio coincide con el del sistema. No
escribe nada en la base, solo lee.

---

## Mantenimiento: cuando cambian los precios

Este es el punto que hay que tener presente todos los días.

**El precio vive en dos lugares** — la tabla de PLU de la balanza y el catálogo del
sistema — y hay que actualizarlo en los dos. La balanza sincroniza únicamente con
el software propietario de Systel (protocolo no documentado), así que no se puede
automatizar.

Para cambiar solo precios, sin editar el PLU entero:
`4. Artículos / PLU` → `1. cambiar precios`

### El sistema ayuda de dos maneras

**Después de confirmar una pieza** aparece sola la lista *"Precios para la
balanza"*: muestra qué cortes quedaron con otro precio (con el anterior y el
nuevo), cuáles son nuevos y cuáles quedaron sin PLU. Es la lista para ir a
cargar.

**Cuando quieras repasar**, el botón **⚖ Balanza** en la pantalla de Stock
muestra todo lo que debería estar cargado, ordenado por PLU.

**Y si igual se pasa por alto:** al escanear una etiqueta cuyo precio no coincide
con el del sistema, la Caja avisa en el momento. Lo detecta comparando el importe
impreso contra el precio del sistema (el peso deducido tiene que caer en un gramo
redondo, y si el precio está mal no cae). Detecta 8 o 9 de cada 10 escaneos, así
que en dos o tres ventas salta seguro. El aviso sale una vez por corte para no
molestar en cada venta.

**Qué pasa si se desfasan:** la plata cobrada sigue siendo correcta (la Caja cobra
el importe impreso en la etiqueta, que es el que el cliente está viendo), pero los
kg que se descuentan del stock se calculan dividiendo ese importe por el precio del
*sistema*. Si los precios no coinciden, **el stock se desvía de a poco**.

Regla práctica: cada vez que un despiece cambia el precio de un corte, actualizarlo
también en la balanza.

---

## Límites y trampas

| Cosa | Detalle |
|---|---|
| **PLU de 5 dígitos** | Si un PLU tiene más dígitos que los configurados (4), la balanza **no imprime** el código de barras (pág. 39). Con números de 1 a 2 cifras no pasa. |
| **Rango de PLU** | La balanza admite 1 a 8000. El código de barras reserva 4 dígitos (hasta 9999). El sistema acepta hasta 9999, así que un número mayor a 8000 lo tomaría el sistema pero no la balanza. |
| **Tope de importe** | 6 dígitos = $999.999 por etiqueta (unos 51 kg a $19.500/kg). Por encima, no imprime el código. |
| **PLU 0000** | Es lo que sale al pesar sin elegir artículo. La etiqueta es válida pero anónima: la Caja no puede saber qué corte es y avisa. |
| **Genéricos** | `8. configurar equipo` → `2. Balanza` → `5. Genericos` define un PLU genérico. Si es de 5 dígitos (ej. 99999), esas etiquetas salen sin código. |

### No tocar

`9. Memoria` tiene tres opciones destructivas (pág. 42):

- `3. Borrar PLUs` — borra **todos** los artículos cargados.
- `4. Borrar Sectores` — borra los sectores con sus artículos.
- `5. Valores de fábrica` — resetea todo, incluida la configuración de la Parte A.

`1. Estado de memoria` sí es útil: muestra cuántos artículos, accesos y sectores
hay usados.

---

## Resumen: checklist

**Una sola vez**

- [ ] A1 · Coma de precio en `6.0`
- [ ] A2 · Código de barras por peso = `20PPPPIIIIII`
- [ ] A3 · Imprimir códigos en tickets = `SI`
- [ ] A4 · Precios permitidos = `Solo Lista 1`
- [ ] A5 · Tipo de papel = `papel continuo`
- [ ] A6 · Reloj en hora
- [ ] A7 · Datos del comercio
- [ ] A8 · Conectividad sin espera de sincronización

**Antes de cargar todo**

- [ ] B · Verificar con un artículo de prueba si el código de barras lleva el
      **Código de PLU** o el **N° de PLU** (ver el recuadro de la Parte B)

**Por cada corte**

- [ ] B · Cargarlo en la balanza (venta por peso + precio + `USAR EAN GRAL.`)
- [ ] B · Días de vencimiento y tara, si corresponden
- [ ] B · El mismo número en el campo "PLU balanza" del producto
- [ ] C · Acceso directo, si es de los que más se venden
- [ ] E · Pesar, imprimir y escanear una etiqueta de prueba
