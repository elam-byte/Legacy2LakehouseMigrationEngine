-- Run these via Trino CLI or the migration engine after `make up`
-- Creates Iceberg tables in the Nessie catalog / MinIO warehouse

CREATE SCHEMA IF NOT EXISTS iceberg.warehouse;

-- ── Customers ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS iceberg.warehouse.customers (
    id              INTEGER,
    external_id     VARCHAR,
    full_name       VARCHAR,
    email           VARCHAR,
    country_code    VARCHAR,
    tier            VARCHAR,
    credit_limit    DECIMAL(12,2),
    is_active       BOOLEAN,
    metadata        VARCHAR,       -- JSONB → serialised as VARCHAR in Iceberg
    created_at      TIMESTAMP(6) WITH TIME ZONE,
    updated_at      TIMESTAMP(6) WITH TIME ZONE
)
WITH (
    format           = 'PARQUET',
    partitioning     = ARRAY['country_code'],
    sorted_by        = ARRAY['created_at DESC']
);

-- ── Products ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS iceberg.warehouse.products (
    id              INTEGER,
    sku             VARCHAR,
    name            VARCHAR,
    category        VARCHAR,
    subcategory     VARCHAR,
    unit_price      DECIMAL(10,2),
    cost_price      DECIMAL(10,2),
    stock_qty       INTEGER,
    weight_kg       DECIMAL(8,3),
    is_available    BOOLEAN,
    created_at      TIMESTAMP(6) WITH TIME ZONE
)
WITH (
    format       = 'PARQUET',
    partitioning = ARRAY['category']
);

-- ── Orders ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS iceberg.warehouse.orders (
    id               INTEGER,
    customer_id      INTEGER,
    order_ref        VARCHAR,
    status           VARCHAR,
    subtotal         DECIMAL(12,2),
    tax_amount       DECIMAL(10,2),
    discount_amount  DECIMAL(10,2),
    total            DECIMAL(12,2),
    currency         VARCHAR,
    shipping_country VARCHAR,
    notes            VARCHAR,
    placed_at        TIMESTAMP(6) WITH TIME ZONE,
    updated_at       TIMESTAMP(6) WITH TIME ZONE
)
WITH (
    format           = 'PARQUET',
    partitioning     = ARRAY['month(placed_at)', 'status'],
    sorted_by        = ARRAY['placed_at DESC']
);

-- ── Order Items ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS iceberg.warehouse.order_items (
    id          INTEGER,
    order_id    INTEGER,
    product_id  INTEGER,
    quantity    INTEGER,
    unit_price  DECIMAL(10,2),
    line_total  DECIMAL(12,2)
)
WITH (
    format = 'PARQUET'
);

-- ── Transactions ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS iceberg.warehouse.transactions (
    id              INTEGER,
    order_id        INTEGER,
    txn_ref         VARCHAR,
    txn_type        VARCHAR,
    amount          DECIMAL(12,2),
    currency        VARCHAR,
    gateway         VARCHAR,
    gateway_txn_id  VARCHAR,
    status          VARCHAR,
    processed_at    TIMESTAMP(6) WITH TIME ZONE,
    settled_at      TIMESTAMP(6) WITH TIME ZONE
)
WITH (
    format           = 'PARQUET',
    partitioning     = ARRAY['month(processed_at)', 'gateway'],
    sorted_by        = ARRAY['processed_at DESC']
);
