-- Post-migration validation queries.
-- Run via: trino --server localhost:8080 --file sql/trino/validate_migration.sql

-- ── Row count parity checks ───────────────────────────────────────────────────
SELECT
    'customers' AS table_name,
    (SELECT COUNT(*) FROM postgres.public.customers)        AS source_rows,
    (SELECT COUNT(*) FROM iceberg.warehouse.customers)      AS target_rows,
    (SELECT COUNT(*) FROM postgres.public.customers) -
    (SELECT COUNT(*) FROM iceberg.warehouse.customers)      AS delta
UNION ALL
SELECT
    'products',
    (SELECT COUNT(*) FROM postgres.public.products),
    (SELECT COUNT(*) FROM iceberg.warehouse.products),
    (SELECT COUNT(*) FROM postgres.public.products) - (SELECT COUNT(*) FROM iceberg.warehouse.products)
UNION ALL
SELECT
    'orders',
    (SELECT COUNT(*) FROM postgres.public.orders),
    (SELECT COUNT(*) FROM iceberg.warehouse.orders),
    (SELECT COUNT(*) FROM postgres.public.orders) - (SELECT COUNT(*) FROM iceberg.warehouse.orders)
UNION ALL
SELECT
    'order_items',
    (SELECT COUNT(*) FROM postgres.public.order_items),
    (SELECT COUNT(*) FROM iceberg.warehouse.order_items),
    (SELECT COUNT(*) FROM postgres.public.order_items) - (SELECT COUNT(*) FROM iceberg.warehouse.order_items)
UNION ALL
SELECT
    'transactions',
    (SELECT COUNT(*) FROM postgres.public.transactions),
    (SELECT COUNT(*) FROM iceberg.warehouse.transactions),
    (SELECT COUNT(*) FROM postgres.public.transactions) - (SELECT COUNT(*) FROM iceberg.warehouse.transactions);

-- ── Checksum validation (sum of id column as cheap integrity check) ───────────
SELECT 'customers_id_sum'   AS check_name, SUM(CAST(id AS BIGINT)) AS checksum FROM postgres.public.customers
UNION ALL
SELECT 'customers_id_sum',   SUM(CAST(id AS BIGINT)) FROM iceberg.warehouse.customers
UNION ALL
SELECT 'orders_total_sum',   SUM(total) FROM postgres.public.orders
UNION ALL
SELECT 'orders_total_sum',   SUM(total) FROM iceberg.warehouse.orders
UNION ALL
SELECT 'txn_amount_sum',     SUM(amount) FROM postgres.public.transactions
UNION ALL
SELECT 'txn_amount_sum',     SUM(amount) FROM iceberg.warehouse.transactions;

-- ── Federated cross-catalog join (proves zero-copy lakehouse query) ───────────
-- This query joins legacy Postgres with Iceberg in a single Trino statement:
SELECT
    c.tier,
    COUNT(DISTINCT o.id)    AS order_count,
    SUM(t.amount)           AS total_revenue
FROM postgres.public.customers c
JOIN iceberg.warehouse.orders   o  ON o.customer_id = c.id
JOIN iceberg.warehouse.transactions t ON t.order_id = o.id
WHERE t.status = 'success'
GROUP BY c.tier
ORDER BY total_revenue DESC;
