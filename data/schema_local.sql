-- ============================================================================
--  Esquema de la base local (SQLite) - Kiosko POS
--  Idempotente: usa CREATE ... IF NOT EXISTS, se puede ejecutar en cada arranque.
--  Convenciones:
--    - id: TEXT con UUID generado en Python (offline-first).
--    - flags 0/1: INTEGER.
--    - dinero: NUMERIC(12,2); cantidades/peso: NUMERIC(12,3). Decimal en Python.
--    - fechas: TEXT en ISO8601 UTC.
-- ============================================================================

-- ---------- Catálogo y stock ------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias (
    id           TEXT PRIMARY KEY,
    nombre       TEXT NOT NULL,
    margen_pct   NUMERIC(6,2),                 -- margen de ganancia por defecto (%)
    activo       INTEGER NOT NULL DEFAULT 1,
    sincronizado INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS productos (
    id                   TEXT PRIMARY KEY,
    codigo_barra         TEXT UNIQUE,
    nombre               TEXT NOT NULL,
    categoria_id         TEXT REFERENCES categorias(id),
    es_pesable           INTEGER NOT NULL DEFAULT 0,
    unidad_medida        TEXT NOT NULL DEFAULT 'UN',
    costo_compra         NUMERIC(12,2) NOT NULL DEFAULT 0,
    precio_venta         NUMERIC(12,2) NOT NULL DEFAULT 0,
    margen_pct           NUMERIC(6,2),                -- override del margen (NULL = usa la categoría)
    ubicacion            TEXT,                        -- dónde está físicamente (ej. "Depósito 1")
    stock_actual         NUMERIC(12,3) NOT NULL DEFAULT 0,
    stock_minimo         NUMERIC(12,3) NOT NULL DEFAULT 0,
    controla_stock       INTEGER NOT NULL DEFAULT 1,
    controla_vencimiento INTEGER NOT NULL DEFAULT 0,
    activo               INTEGER NOT NULL DEFAULT 1,
    sincronizado         INTEGER NOT NULL DEFAULT 0,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lotes (
    id                 TEXT PRIMARY KEY,
    producto_id        TEXT NOT NULL REFERENCES productos(id),
    fecha_vencimiento  TEXT,
    cantidad           NUMERIC(12,3) NOT NULL DEFAULT 0,
    compra_id          TEXT,
    activo             INTEGER NOT NULL DEFAULT 1,
    updated_at         TEXT NOT NULL
);

-- Libro de movimientos de stock (ledger): fuente de verdad del stock para
-- sincronizar entre PCs. Cada cambio de stock (venta, remito, despiece, alta,
-- ajuste) anota UNA fila inmutable con la cantidad con signo (+ entra, − sale).
-- El stock_actual del producto es una caché = suma de estos deltas. Al bajar
-- movimientos de otra PC, se aplica su delta al stock_actual local. Idempotente
-- por id (UUID): cada movimiento se aplica exactamente una vez por PC.
CREATE TABLE IF NOT EXISTS movimientos_stock (
    id            TEXT PRIMARY KEY,
    producto_id   TEXT NOT NULL REFERENCES productos(id),
    fecha         TEXT NOT NULL,                    -- ISO local
    tipo          TEXT NOT NULL,                    -- VENTA | COMPRA | DESPIECE | ALTA | AJUSTE
    cantidad      NUMERIC(12,3) NOT NULL,           -- con signo: + entrada, − salida
    referencia_id TEXT,                             -- venta_id / compra_id / corte_id / NULL
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

-- ---------- Proveedores y compras ------------------------------------------
CREATE TABLE IF NOT EXISTS proveedores (
    id            TEXT PRIMARY KEY,
    nombre        TEXT NOT NULL,
    cuit          TEXT,
    telefono      TEXT,
    email         TEXT,
    saldo_cuenta  NUMERIC(12,2) NOT NULL DEFAULT 0,   -- lo que LE DEBEMOS
    activo        INTEGER NOT NULL DEFAULT 1,
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS compras (
    id            TEXT PRIMARY KEY,
    proveedor_id  TEXT NOT NULL REFERENCES proveedores(id),
    fecha         TEXT NOT NULL,
    nro_remito    TEXT,
    total         NUMERIC(12,2) NOT NULL DEFAULT 0,
    condicion     TEXT NOT NULL DEFAULT 'CONTADO',     -- CONTADO | CUENTA_CORRIENTE
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS compras_detalle (
    id             TEXT PRIMARY KEY,
    compra_id      TEXT NOT NULL REFERENCES compras(id),
    producto_id    TEXT NOT NULL REFERENCES productos(id),
    cantidad       NUMERIC(12,3) NOT NULL,
    costo_unitario NUMERIC(12,2) NOT NULL,
    subtotal       NUMERIC(12,2) NOT NULL
);

-- ---------- Carne: despiece de reses ----------------------------------------
--  Una res (media res) ingresa por kg a un costo/kg; se subdivide en piezas
--  (Espalda/Pierna, se bajan en días distintos) y cada pieza en cortes. Al
--  confirmar la pieza, cada corte suma stock a un producto pesable. La res
--  queda ABIERTA hasta terminar de bajar todas sus piezas.
CREATE TABLE IF NOT EXISTS reses (
    id            TEXT PRIMARY KEY,
    proveedor_id  TEXT REFERENCES proveedores(id),   -- quién vendió la res (opcional)
    fecha         TEXT NOT NULL,                      -- día que ingresó
    descripcion   TEXT NOT NULL DEFAULT 'Media res',  -- ej "Media res novillo"
    peso_total    NUMERIC(12,3) NOT NULL DEFAULT 0,   -- kg ingresados (ej 120)
    costo_por_kg  NUMERIC(12,2) NOT NULL DEFAULT 0,   -- $ por kg (ej 10000)
    costo_total   NUMERIC(12,2) NOT NULL DEFAULT 0,   -- peso_total * costo_por_kg
    margen_pct    NUMERIC(6,2),                       -- margen por defecto (hereda a piezas/cortes)
    condicion     TEXT NOT NULL DEFAULT 'CONTADO',    -- CONTADO | CUENTA_CORRIENTE
    estado        TEXT NOT NULL DEFAULT 'ABIERTA',    -- ABIERTA | CERRADA
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS piezas (
    id            TEXT PRIMARY KEY,
    res_id        TEXT NOT NULL REFERENCES reses(id),
    nombre        TEXT NOT NULL,                      -- Espalda | Pierna | ...
    fecha         TEXT NOT NULL,                      -- día que se bajó la pieza
    peso          NUMERIC(12,3) NOT NULL DEFAULT 0,   -- kg de la pieza (suma de cortes)
    margen_pct    NUMERIC(6,2),                       -- override del margen de la res
    estado        TEXT NOT NULL DEFAULT 'ABIERTA',    -- ABIERTA | CERRADA (stock ya cargado)
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cortes (
    id              TEXT PRIMARY KEY,
    pieza_id        TEXT NOT NULL REFERENCES piezas(id),
    producto_id     TEXT REFERENCES productos(id),      -- corte-producto que recibe stock (NULL hasta confirmar)
    descripcion     TEXT NOT NULL,                      -- nombre del corte (snapshot)
    peso            NUMERIC(12,3) NOT NULL DEFAULT 0,   -- kg del corte
    precio_venta_kg NUMERIC(12,2) NOT NULL DEFAULT 0,   -- $ por kg de venta
    margen_pct      NUMERIC(6,2),                       -- override (corte > pieza > res)
    costo_kg        NUMERIC(12,2) NOT NULL DEFAULT 0,   -- snapshot costo/kg de la res al confirmar
    subtotal        NUMERIC(12,2) NOT NULL DEFAULT 0,   -- peso * precio_venta_kg
    es_desperdicio  INTEGER NOT NULL DEFAULT 0,         -- 1 = merma/hueso sin venta
    confirmado      INTEGER NOT NULL DEFAULT 0,         -- 1 = ya sumó stock al producto
    sincronizado    INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);

-- ---------- Clientes (fiados) y ventas -------------------------------------
CREATE TABLE IF NOT EXISTS clientes (
    id              TEXT PRIMARY KEY,
    nombre          TEXT NOT NULL,
    telefono        TEXT,
    limite_credito  NUMERIC(12,2) NOT NULL DEFAULT 0,
    saldo_cuenta    NUMERIC(12,2) NOT NULL DEFAULT 0,  -- lo que NOS DEBE
    activo          INTEGER NOT NULL DEFAULT 1,
    sincronizado    INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas (
    id            TEXT PRIMARY KEY,
    fecha         TEXT NOT NULL,
    cliente_id    TEXT REFERENCES clientes(id),         -- NULL = consumidor final
    subtotal      NUMERIC(12,2) NOT NULL,
    descuento     NUMERIC(12,2) NOT NULL DEFAULT 0,
    total         NUMERIC(12,2) NOT NULL,
    costo_total   NUMERIC(12,2) NOT NULL DEFAULT 0,     -- snapshot para ganancia neta
    estado        TEXT NOT NULL DEFAULT 'COMPLETADA',   -- COMPLETADA | ANULADA
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas_detalle (
    id              TEXT PRIMARY KEY,
    venta_id        TEXT NOT NULL REFERENCES ventas(id),
    producto_id     TEXT NOT NULL REFERENCES productos(id),
    descripcion     TEXT NOT NULL,                      -- snapshot del nombre
    cantidad        NUMERIC(12,3) NOT NULL,             -- soporta 0.750 kg
    precio_unitario NUMERIC(12,2) NOT NULL,             -- snapshot precio
    costo_unitario  NUMERIC(12,2) NOT NULL,             -- snapshot costo
    subtotal        NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS pagos_venta (
    id        TEXT PRIMARY KEY,
    venta_id  TEXT NOT NULL REFERENCES ventas(id),
    metodo    TEXT NOT NULL,    -- EFECTIVO | TRANSFERENCIA | TARJETA | FIADO
    monto     NUMERIC(12,2) NOT NULL
);

-- ---------- Cuenta corriente unificada (clientes y proveedores) ------------
CREATE TABLE IF NOT EXISTS cuenta_movimientos (
    id                TEXT PRIMARY KEY,
    entidad_tipo      TEXT NOT NULL,        -- CLIENTE | PROVEEDOR
    entidad_id        TEXT NOT NULL,
    fecha             TEXT NOT NULL,
    tipo              TEXT NOT NULL,        -- DEBE (deuda) | HABER (pago)
    monto             NUMERIC(12,2) NOT NULL,
    saldo_resultante  NUMERIC(12,2) NOT NULL,
    referencia_tipo   TEXT,                 -- VENTA | COMPRA | PAGO | AJUSTE
    referencia_id     TEXT,
    nota              TEXT,
    metodo            TEXT,                 -- medio de pago (solo en PAGO): EFECTIVO/...
    sincronizado      INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL
);

-- ---------- Cierres de caja (arqueo) ----------------------------------------
CREATE TABLE IF NOT EXISTS cierres_caja (
    id                   TEXT PRIMARY KEY,
    fecha                TEXT NOT NULL,          -- cuándo se hizo el cierre (local)
    desde                TEXT,                   -- inicio del período (cierre anterior)
    usuario_id           TEXT,
    usuario_nombre       TEXT,
    ventas_cantidad      INTEGER NOT NULL DEFAULT 0,
    total_vendido        NUMERIC(12,2) NOT NULL DEFAULT 0,
    efectivo_ventas      NUMERIC(12,2) NOT NULL DEFAULT 0,
    transferencia_ventas NUMERIC(12,2) NOT NULL DEFAULT 0,
    tarjeta_ventas       NUMERIC(12,2) NOT NULL DEFAULT 0,
    fiado_ventas         NUMERIC(12,2) NOT NULL DEFAULT 0,
    cobros_efectivo      NUMERIC(12,2) NOT NULL DEFAULT 0,  -- cobros de fiado en efectivo
    pagos_efectivo       NUMERIC(12,2) NOT NULL DEFAULT 0,  -- pagos a proveedores en efectivo
    gastos_total         NUMERIC(12,2) NOT NULL DEFAULT 0,
    fondo                NUMERIC(12,2) NOT NULL DEFAULT 0,
    efectivo_esperado    NUMERIC(12,2) NOT NULL DEFAULT 0,
    efectivo_contado     NUMERIC(12,2) NOT NULL DEFAULT 0,
    diferencia           NUMERIC(12,2) NOT NULL DEFAULT 0,
    nota                 TEXT,
    sincronizado         INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL
);

-- ---------- Usuarios --------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    rol           TEXT NOT NULL,               -- SUPER_ADMIN | ADMIN | EMPLEADO
    activo        INTEGER NOT NULL DEFAULT 1,
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL
);

-- ---------- Gastos ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS gastos (
    id            TEXT PRIMARY KEY,
    fecha         TEXT NOT NULL,
    tipo          TEXT NOT NULL,            -- FIJO | VARIABLE
    descripcion   TEXT NOT NULL,
    monto         NUMERIC(12,2) NOT NULL,
    proveedor_id  TEXT REFERENCES proveedores(id),
    metodo        TEXT NOT NULL DEFAULT 'EFECTIVO',   -- medio de pago del gasto
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

-- ---------- Índices ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_mov_stock_sync ON movimientos_stock(sincronizado);
CREATE INDEX IF NOT EXISTS idx_mov_stock_prod ON movimientos_stock(producto_id);
CREATE INDEX IF NOT EXISTS idx_prod_codigo  ON productos(codigo_barra);
CREATE INDEX IF NOT EXISTS idx_prod_nombre  ON productos(nombre);
CREATE INDEX IF NOT EXISTS idx_ventas_sync  ON ventas(sincronizado);
CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha);
CREATE INDEX IF NOT EXISTS idx_cm_entidad   ON cuenta_movimientos(entidad_tipo, entidad_id);
CREATE INDEX IF NOT EXISTS idx_lotes_venc   ON lotes(fecha_vencimiento);
CREATE INDEX IF NOT EXISTS idx_piezas_res   ON piezas(res_id);
CREATE INDEX IF NOT EXISTS idx_cortes_pieza ON cortes(pieza_id);
