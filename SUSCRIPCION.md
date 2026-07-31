# Suscripción del software

Cómo funciona el cobro mensual del sistema al comercio, cómo se registra y qué
pasa cuando no se paga.

## Quién hace qué

| Rol | Qué ve y qué puede hacer |
|---|---|
| **Super administrador** (quien vende el sistema) | Configura el contrato, registra los cobros, anula un pago mal cargado. Nunca se le bloquea nada. |
| **Administrador** (el dueño del comercio) | Ve la sección **💳 Suscripción** en solo lectura: estado, días restantes, meses pagados, historial y a dónde pagar. |
| **Empleado** | No ve nada de esto y nunca se entera. |

## El modelo: meses de crédito

Un pago **no cubre un período concreto**, compra **N meses de crédito** (de 1 a 12).
La cobertura es siempre:

```
cubierto_hasta = fecha_inicio + suma de los meses de todos los pagos válidos
```

Por eso el orden en que se cargan los pagos no importa, pagar doce meses juntos es
un solo registro con `meses = 12`, y nunca quedan huecos ni períodos superpuestos.
Si el 31 de enero + 1 mes cae en un mes más corto, la fecha baja al último día del
mes (28/29 de febrero).

**Ojo con el atraso:** los meses corren desde donde quedó la cobertura, no desde
hoy. Si el comercio debe un mes y paga uno, se pone al día pero no se le perdona
el atraso ya corrido. Para perdonarlo hay que correr la fecha de inicio o usar el
estado manual «Forzar activa».

## Los cuatro estados

| Estado | Cuándo | Qué pasa |
|---|---|---|
| **Al día** | faltan más de 7 días | nada |
| **Por vencer** | faltan 7 días o menos | banner ámbar arriba |
| **Vencida** | pasó el vencimiento, atraso ≤ 30 días | banner rojo + aviso al entrar, con la fecha exacta de suspensión |
| **Suspendida** | atraso > 30 días (`gracia_dias`) | **Caja y Clientes siguen funcionando**; Stock, Carne, Proveedores, Reportes, Cierres y Usuarios muestran una pantalla de bloqueo con los datos de pago |

El plazo de gracia es configurable. La sección Suscripción queda siempre
accesible: es donde se ve cuánto y dónde pagar.

## Cómo se cobra en la práctica

1. En **tu** PC (con el mismo `NEON_DATABASE_URL` del comercio en el `.env`),
   entrás como super administrador.
2. **💳 Suscripción → ⚙ Configurar**: primer día cobrado, cuota mensual, días de
   gracia y los datos para que te paguen (alias/CBU/teléfono). Eso último lo ve
   la dueña en su pantalla.
3. Cuando te paga: **＋ Registrar pago** → meses, monto (se sugiere solo: meses ×
   cuota, editable), efectivo o transferencia, y una nota si hace falta. El
   diálogo muestra en vivo hasta cuándo queda cubierto.
4. En menos de un minuto (con internet) el pago aparece en la PC del comercio.

Si cargaste algo mal: **🗑 Anular** en la fila del pago. El pago queda en el
historial marcado como anulado y la cobertura se acorta.

## Por qué no se puede hacer trampa

El comercio tiene la base en su propia PC, así que hay tres capas:

1. **Firma HMAC.** Cada pago y la configuración van firmados con un secreto que
   está dentro del `.exe` (`app/core/licencia.py`). Una fila insertada a mano con
   un editor de SQLite no valida y **no suma meses**: aparece marcada
   «⚠ sin validar» en el historial. Adulterar los meses o el monto de un pago
   legítimo lo invalida entero.
2. **La nube manda.** Es la única parte del sistema donde el pull *reemplaza* en
   vez de fusionar (`sync_manager._pull_suscripcion`): baja la configuración y
   los pagos de Neon y borra los pagos locales que allá no existen. Cualquier
   invento local dura hasta el próximo ciclo de sincronización.
   Si la nube todavía no tiene la suscripción configurada, no toca nada (para que
   una base de nube vacía no borre el historial).
3. **Anti-reloj.** El cálculo usa `max(reloj de la PC, última fecha vista)`:
   atrasar el reloj de Windows no devuelve días. Y cada sincronización pisa esa
   marca con la fecha del **servidor**, lo que además repara un reloj que hubiera
   quedado adelantado por error.

Además, la configuración se replica en un **sello firmado** en
`data/licencia.dat`: borrar la fila de `suscripcion` de la base no desactiva
nada, se restaura sola en el próximo arranque.

**Alcance honesto:** el secreto viaja dentro del `.exe`, así que alguien con
conocimientos podría extraerlo. Esto frena el ataque realista (editar la base con
DB Browser), y la capa de la nube corrige el resto.

## Dónde vive cada cosa

```
data/schema_local.sql        tablas suscripcion + suscripcion_pagos
data/schema_cloud.sql        espejo en Neon
app/core/suscripcion.py      cálculo del estado (lógica pura, sin base)
app/core/licencia.py         firma HMAC + sello en disco
app/repositories/suscripcion_repo.py
app/services/suscripcion_service.py
app/core/sync_manager.py     _push_suscripcion / _pull_suscripcion
app/ui/views/suscripcion_view.py
app/ui/dialogs/suscripcion_dialog.py
app/ui/app_window.py         banner, aviso al entrar y pantalla de bloqueo
app/models/usuario.py        SECCIONES_SIN_SUSCRIPCION (qué sigue andando)
```

## Limitaciones conocidas

- **Un comercio por base de nube.** La tabla `suscripcion` tiene una sola fila.
  Para un segundo cliente hace falta otro Neon (y cambiar el `.env`) o un panel
  aparte que lea varias bases.
- **Sin internet nunca**, la corrección desde la nube no llega; quedan en pie la
  firma, el sello y la marca de agua.
- El aviso al entrar se muestra **una vez por sesión**; el banner queda siempre.
