-- ============================================================================
--  Esquema de la base central (PostgreSQL / Neon) - Kiosko POS
--  Espejo del esquema local, con tipos nativos de Postgres.
--  Idempotente: CREATE ... IF NOT EXISTS.
--
--  NOTA DE DISEÑO: esta base es un RESPALDO/central de la SQLite local.
--  A propósito NO lleva claves foráneas hacia productos/clientes: como el
--  catálogo puede vivir en la nube y las ventas se suben desde el local,
--  no queremos que una FK faltante bloquee la subida de una venta.
--  El único vínculo que sí garantizamos es detalle/pagos -> ventas, porque
--  se insertan juntos en la misma transacción.
-- ============================================================================

CREATE TABLE IF NOT EXISTS categorias (
    id          TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS productos (
    id                   TEXT PRIMARY KEY,
    codigo_barra         TEXT UNIQUE,
    nombre               TEXT NOT NULL,
    categoria_id         TEXT,
    es_pesable           BOOLEAN NOT NULL DEFAULT FALSE,
    unidad_medida        TEXT NOT NULL DEFAULT 'UN',
    costo_compra         NUMERIC(12,2) NOT NULL DEFAULT 0,
    precio_venta         NUMERIC(12,2) NOT NULL DEFAULT 0,
    stock_actual         NUMERIC(12,3) NOT NULL DEFAULT 0,
    stock_minimo         NUMERIC(12,3) NOT NULL DEFAULT 0,
    controla_stock       BOOLEAN NOT NULL DEFAULT TRUE,
    controla_vencimiento BOOLEAN NOT NULL DEFAULT FALSE,
    activo               BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS clientes (
    id              TEXT PRIMARY KEY,
    nombre          TEXT NOT NULL,
    telefono        TEXT,
    limite_credito  NUMERIC(12,2) NOT NULL DEFAULT 0,
    saldo_cuenta    NUMERIC(12,2) NOT NULL DEFAULT 0,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS proveedores (
    id            TEXT PRIMARY KEY,
    nombre        TEXT NOT NULL,
    cuit          TEXT,
    telefono      TEXT,
    saldo_cuenta  NUMERIC(12,2) NOT NULL DEFAULT 0,
    activo        BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas (
    id            TEXT PRIMARY KEY,
    fecha         TIMESTAMPTZ NOT NULL,
    cliente_id    TEXT,
    subtotal      NUMERIC(12,2) NOT NULL,
    descuento     NUMERIC(12,2) NOT NULL DEFAULT 0,
    total         NUMERIC(12,2) NOT NULL,
    costo_total   NUMERIC(12,2) NOT NULL DEFAULT 0,
    estado        TEXT NOT NULL DEFAULT 'COMPLETADA',
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas_detalle (
    id              TEXT PRIMARY KEY,
    venta_id        TEXT NOT NULL REFERENCES ventas(id),
    producto_id     TEXT NOT NULL,
    descripcion     TEXT NOT NULL,
    cantidad        NUMERIC(12,3) NOT NULL,
    precio_unitario NUMERIC(12,2) NOT NULL,
    costo_unitario  NUMERIC(12,2) NOT NULL,
    subtotal        NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS pagos_venta (
    id        TEXT PRIMARY KEY,
    venta_id  TEXT NOT NULL REFERENCES ventas(id),
    metodo    TEXT NOT NULL,
    monto     NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS cuenta_movimientos (
    id                TEXT PRIMARY KEY,
    entidad_tipo      TEXT NOT NULL,
    entidad_id        TEXT NOT NULL,
    fecha             TIMESTAMPTZ NOT NULL,
    tipo              TEXT NOT NULL,
    monto             NUMERIC(12,2) NOT NULL,
    saldo_resultante  NUMERIC(12,2) NOT NULL,
    referencia_tipo   TEXT,
    referencia_id     TEXT,
    nota              TEXT,
    created_at        TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS gastos (
    id            TEXT PRIMARY KEY,
    fecha         TIMESTAMPTZ NOT NULL,
    tipo          TEXT NOT NULL,
    descripcion   TEXT NOT NULL,
    monto         NUMERIC(12,2) NOT NULL,
    proveedor_id  TEXT,
    created_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cloud_ventas_fecha ON ventas(fecha);
CREATE INDEX IF NOT EXISTS idx_cloud_det_venta    ON ventas_detalle(venta_id);
