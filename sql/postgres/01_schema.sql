-- Legacy source schema (PostgreSQL 15)
-- Domain: Retail banking — realistic types that expose common migration pain points:
--   SERIAL (no Iceberg equivalent), TIMESTAMPTZ, NUMERIC precision, TEXT, JSONB

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Customers ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id             SERIAL PRIMARY KEY,
    external_id    UUID          NOT NULL DEFAULT uuid_generate_v4(),
    full_name      TEXT          NOT NULL,
    email          VARCHAR(255)  NOT NULL,
    country_code   CHAR(2)       NOT NULL DEFAULT 'US',
    tier           VARCHAR(20)   NOT NULL DEFAULT 'standard'
                   CHECK (tier IN ('standard', 'premium', 'vip')),
    credit_limit   NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    metadata       JSONB,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customers_email    ON customers(email);
CREATE INDEX idx_customers_tier     ON customers(tier);
CREATE INDEX idx_customers_country  ON customers(country_code);

-- ── Products ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id             SERIAL PRIMARY KEY,
    sku            VARCHAR(50)   NOT NULL UNIQUE,
    name           TEXT          NOT NULL,
    category       VARCHAR(100)  NOT NULL,
    subcategory    VARCHAR(100),
    unit_price     NUMERIC(10,2) NOT NULL,
    cost_price     NUMERIC(10,2) NOT NULL,
    stock_qty      INTEGER       NOT NULL DEFAULT 0,
    weight_kg      NUMERIC(8,3),
    is_available   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_sku      ON products(sku);

-- ── Orders ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id             SERIAL PRIMARY KEY,
    customer_id    INTEGER       NOT NULL REFERENCES customers(id),
    order_ref      VARCHAR(30)   NOT NULL UNIQUE,
    status         VARCHAR(20)   NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','confirmed','shipped','delivered','cancelled','refunded')),
    subtotal       NUMERIC(12,2) NOT NULL,
    tax_amount     NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    discount_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    total          NUMERIC(12,2) NOT NULL,
    currency       CHAR(3)       NOT NULL DEFAULT 'USD',
    shipping_country CHAR(2),
    notes          TEXT,
    placed_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_customer   ON orders(customer_id);
CREATE INDEX idx_orders_status     ON orders(status);
CREATE INDEX idx_orders_placed_at  ON orders(placed_at);

-- ── Order Line Items ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    id             SERIAL PRIMARY KEY,
    order_id       INTEGER       NOT NULL REFERENCES orders(id),
    product_id     INTEGER       NOT NULL REFERENCES products(id),
    quantity       INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price     NUMERIC(10,2) NOT NULL,
    line_total     NUMERIC(12,2) NOT NULL
);

CREATE INDEX idx_order_items_order   ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);

-- ── Financial Transactions ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id             SERIAL PRIMARY KEY,
    order_id       INTEGER       NOT NULL REFERENCES orders(id),
    txn_ref        VARCHAR(40)   NOT NULL UNIQUE,
    txn_type       VARCHAR(20)   NOT NULL
                   CHECK (txn_type IN ('charge','refund','chargeback','adjustment')),
    amount         NUMERIC(12,2) NOT NULL,
    currency       CHAR(3)       NOT NULL DEFAULT 'USD',
    gateway        VARCHAR(50)   NOT NULL DEFAULT 'stripe',
    gateway_txn_id VARCHAR(100),
    status         VARCHAR(20)   NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','success','failed','reversed')),
    processed_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    settled_at     TIMESTAMPTZ
);

CREATE INDEX idx_transactions_order      ON transactions(order_id);
CREATE INDEX idx_transactions_processed  ON transactions(processed_at);
CREATE INDEX idx_transactions_type       ON transactions(txn_type);
CREATE INDEX idx_transactions_status     ON transactions(status);
