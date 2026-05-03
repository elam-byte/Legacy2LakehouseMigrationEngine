-- Seed 200,000 orders, then 400,000 order_items
INSERT INTO orders (customer_id, order_ref, status, subtotal, tax_amount, discount_amount, total, currency, shipping_country, placed_at)
SELECT
    1 + (i % 50000)                                                         AS customer_id,
    'ORD-' || LPAD(i::TEXT, 8, '0')                                         AS order_ref,
    (ARRAY['pending','confirmed','shipped','delivered','delivered','delivered','cancelled','refunded'])[1 + (i % 8)] AS status,
    ROUND((CAST(random() * 4900 AS NUMERIC) + 100), 2)                      AS subtotal,
    ROUND((CAST(random() * 400 AS NUMERIC)), 2)                             AS tax_amount,
    ROUND((CAST(random() * 200 AS NUMERIC)), 2)                             AS discount_amount,
    0                                                                        AS total,  -- updated below
    'USD'                                                                    AS currency,
    (ARRAY['US','GB','DE','FR','CA','AU'])[1 + (i % 6)]                    AS shipping_country,
    NOW() - (i * 0.5 || ' hours')::INTERVAL                                AS placed_at
FROM generate_series(1, 200000) AS s(i);

-- Compute total
UPDATE orders SET total = ROUND(subtotal + tax_amount - discount_amount, 2);

-- Seed 400,000 order_items (2 items per order on average)
INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total)
SELECT
    1 + (i % 200000)                                                        AS order_id,
    1 + (i % 5000)                                                          AS product_id,
    1 + (i % 5)                                                             AS quantity,
    ROUND((CAST(random() * 490 AS NUMERIC) + 10), 2)                        AS unit_price,
    0                                                                        AS line_total
FROM generate_series(1, 400000) AS s(i);

UPDATE order_items SET line_total = ROUND(quantity * unit_price, 2);
