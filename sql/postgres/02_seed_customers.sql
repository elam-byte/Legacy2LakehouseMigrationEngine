-- Seed 50,000 customers using generate_series (no external fixtures needed)
INSERT INTO customers (full_name, email, country_code, tier, credit_limit, is_active, created_at)
SELECT
    'Customer ' || i                                                        AS full_name,
    'customer_' || i || '@example-' || (i % 100) || '.com'                AS email,
    (ARRAY['US','GB','DE','FR','CA','AU','JP','IN','BR','MX'])[1 + (i % 10)] AS country_code,
    (ARRAY['standard','standard','standard','premium','premium','vip'])[1 + (i % 6)] AS tier,
    ROUND((CAST(random() * 50000 AS NUMERIC) + 1000), 2)                   AS credit_limit,
    CASE WHEN i % 20 = 0 THEN FALSE ELSE TRUE END                          AS is_active,
    NOW() - (i || ' hours')::INTERVAL                                      AS created_at
FROM generate_series(1, 50000) AS s(i);
