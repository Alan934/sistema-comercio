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
    id          TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    margen_pct  NUMERIC(6,2),                 -- margen de ganancia por defecto (%)
    activo      INTEGER NOT NULL DEFAULT 1,
    updated_at  TEXT NOT NULL
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
    stock_actual         NUMERIC(12,3) NOT NULL DEFAULT 0,
    stock_minimo         NUMERIC(12,3) NOT NULL DEFAULT 0,
    controla_stock       INTEGER NOT NULL DEFAULT 1,
    controla_vencimiento INTEGER NOT NULL DEFAULT 0,
    activo               INTEGER NOT NULL DEFAULT 1,
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
    referencia_tipo   TEXT,                 -- VENTA | COMPRA | PAGO
    referencia_id     TEXT,
    nota              TEXT,
    sincronizado      INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL
);

-- ---------- Gastos ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS gastos (
    id            TEXT PRIMARY KEY,
    fecha         TEXT NOT NULL,
    tipo          TEXT NOT NULL,            -- FIJO | VARIABLE
    descripcion   TEXT NOT NULL,
    monto         NUMERIC(12,2) NOT NULL,
    proveedor_id  TEXT REFERENCES proveedores(id),
    sincronizado  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

-- ---------- Índices ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_prod_codigo  ON productos(codigo_barra);
CREATE INDEX IF NOT EXISTS idx_prod_nombre  ON productos(nombre);
CREATE INDEX IF NOT EXISTS idx_ventas_sync  ON ventas(sincronizado);
CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha);
CREATE INDEX IF NOT EXISTS idx_cm_entidad   ON cuenta_movimientos(entidad_tipo, entidad_id);
CREATE INDEX IF NOT EXISTS idx_lotes_venc   ON lotes(fecha_vencimiento);
