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
    margen_pct  NUMERIC(6,2),
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
    margen_pct           NUMERIC(6,2),
    ubicacion            TEXT,
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

-- Libro de movimientos de stock (ledger). Respaldo central + fuente que cada
-- PC baja para converger su stock. Inmutable; sin FK a productos a propósito.
CREATE TABLE IF NOT EXISTS movimientos_stock (
    id            TEXT PRIMARY KEY,
    producto_id   TEXT NOT NULL,
    fecha         TIMESTAMPTZ NOT NULL,
    tipo          TEXT NOT NULL,
    cantidad      NUMERIC(12,3) NOT NULL,
    referencia_id TEXT,
    created_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS proveedores (
    id            TEXT PRIMARY KEY,
    nombre        TEXT NOT NULL,
    cuit          TEXT,
    telefono      TEXT,
    email         TEXT,
    saldo_cuenta  NUMERIC(12,2) NOT NULL DEFAULT 0,
    activo        BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS compras (
    id            TEXT PRIMARY KEY,
    proveedor_id  TEXT,
    fecha         TIMESTAMPTZ NOT NULL,
    nro_remito    TEXT,
    total         NUMERIC(12,2) NOT NULL DEFAULT 0,
    condicion     TEXT NOT NULL DEFAULT 'CONTADO',
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS compras_detalle (
    id             TEXT PRIMARY KEY,
    compra_id      TEXT NOT NULL REFERENCES compras(id),
    producto_id    TEXT NOT NULL,
    cantidad       NUMERIC(12,3) NOT NULL,
    costo_unitario NUMERIC(12,2) NOT NULL,
    subtotal       NUMERIC(12,2) NOT NULL
);

-- ---------- Carne: despiece de reses (espejo del local) --------------------
CREATE TABLE IF NOT EXISTS reses (
    id            TEXT PRIMARY KEY,
    proveedor_id  TEXT,
    fecha         TIMESTAMPTZ NOT NULL,
    descripcion   TEXT NOT NULL DEFAULT 'Media res',
    peso_total    NUMERIC(12,3) NOT NULL DEFAULT 0,
    costo_por_kg  NUMERIC(12,2) NOT NULL DEFAULT 0,
    costo_total   NUMERIC(12,2) NOT NULL DEFAULT 0,
    margen_pct    NUMERIC(6,2),
    condicion     TEXT NOT NULL DEFAULT 'CONTADO',
    estado        TEXT NOT NULL DEFAULT 'ABIERTA',
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS piezas (
    id            TEXT PRIMARY KEY,
    res_id        TEXT NOT NULL REFERENCES reses(id),
    nombre        TEXT NOT NULL,
    fecha         TIMESTAMPTZ NOT NULL,
    peso          NUMERIC(12,3) NOT NULL DEFAULT 0,
    margen_pct    NUMERIC(6,2),
    estado        TEXT NOT NULL DEFAULT 'ABIERTA',
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cortes (
    id              TEXT PRIMARY KEY,
    pieza_id        TEXT NOT NULL REFERENCES piezas(id),
    producto_id     TEXT,
    descripcion     TEXT NOT NULL,
    peso            NUMERIC(12,3) NOT NULL DEFAULT 0,
    precio_venta_kg NUMERIC(12,2) NOT NULL DEFAULT 0,
    margen_pct      NUMERIC(6,2),
    costo_kg        NUMERIC(12,2) NOT NULL DEFAULT 0,
    subtotal        NUMERIC(12,2) NOT NULL DEFAULT 0,
    es_desperdicio  BOOLEAN NOT NULL DEFAULT FALSE,
    confirmado      BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMPTZ NOT NULL
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
    metodo            TEXT,
    created_at        TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS gastos (
    id            TEXT PRIMARY KEY,
    fecha         TIMESTAMPTZ NOT NULL,
    tipo          TEXT NOT NULL,
    descripcion   TEXT NOT NULL,
    monto         NUMERIC(12,2) NOT NULL,
    proveedor_id  TEXT,
    metodo        TEXT NOT NULL DEFAULT 'EFECTIVO',
    created_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cierres_caja (
    id                   TEXT PRIMARY KEY,
    fecha                TIMESTAMPTZ NOT NULL,
    desde                TIMESTAMPTZ,
    usuario_id           TEXT,
    usuario_nombre       TEXT,
    ventas_cantidad      INTEGER NOT NULL DEFAULT 0,
    total_vendido        NUMERIC(12,2) NOT NULL DEFAULT 0,
    efectivo_ventas      NUMERIC(12,2) NOT NULL DEFAULT 0,
    transferencia_ventas NUMERIC(12,2) NOT NULL DEFAULT 0,
    tarjeta_ventas       NUMERIC(12,2) NOT NULL DEFAULT 0,
    fiado_ventas         NUMERIC(12,2) NOT NULL DEFAULT 0,
    cobros_efectivo      NUMERIC(12,2) NOT NULL DEFAULT 0,
    pagos_efectivo       NUMERIC(12,2) NOT NULL DEFAULT 0,
    gastos_total         NUMERIC(12,2) NOT NULL DEFAULT 0,
    fondo                NUMERIC(12,2) NOT NULL DEFAULT 0,
    efectivo_esperado    NUMERIC(12,2) NOT NULL DEFAULT 0,
    efectivo_contado     NUMERIC(12,2) NOT NULL DEFAULT 0,
    diferencia           NUMERIC(12,2) NOT NULL DEFAULT 0,
    nota                 TEXT,
    created_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    rol           TEXT NOT NULL,
    activo        BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cloud_mov_stock_prod ON movimientos_stock(producto_id);
CREATE INDEX IF NOT EXISTS idx_cloud_ventas_fecha ON ventas(fecha);
CREATE INDEX IF NOT EXISTS idx_cloud_det_venta    ON ventas_detalle(venta_id);
CREATE INDEX IF NOT EXISTS idx_cloud_det_compra   ON compras_detalle(compra_id);
CREATE INDEX IF NOT EXISTS idx_cloud_cm_entidad   ON cuenta_movimientos(entidad_tipo, entidad_id);
CREATE INDEX IF NOT EXISTS idx_cloud_piezas_res    ON piezas(res_id);
CREATE INDEX IF NOT EXISTS idx_cloud_cortes_pieza  ON cortes(pieza_id);
