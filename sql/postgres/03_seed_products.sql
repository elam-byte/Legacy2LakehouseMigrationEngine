-- Seed 5,000 products
INSERT INTO products (sku, name, category, subcategory, unit_price, cost_price, stock_qty, weight_kg, is_available)
SELECT
    'SKU-' || LPAD(i::TEXT, 6, '0')                                        AS sku,
    'Product ' || i || ' - ' || cat_data.cat                               AS name,
    cat_data.cat                                                            AS category,
    cat_data.sub                                                            AS subcategory,
    ROUND((CAST(random() * 990 AS NUMERIC) + 10), 2)                       AS unit_price,
    ROUND((CAST(random() * 400 AS NUMERIC) + 5), 2)                        AS cost_price,
    (random() * 1000)::INTEGER                                             AS stock_qty,
    ROUND((CAST(random() * 30 AS NUMERIC) + 0.1), 3)                       AS weight_kg,
    CASE WHEN i % 15 = 0 THEN FALSE ELSE TRUE END                          AS is_available
FROM generate_series(1, 5000) AS s(i)
CROSS JOIN LATERAL (
    SELECT
        (ARRAY['Electronics','Clothing','Home & Garden','Sports','Books','Food & Beverage','Health','Automotive'])[1 + (i % 8)] AS cat,
        (ARRAY['Accessories','Essentials','Premium','Budget','Seasonal','Specialty'])[1 + (i % 6)] AS sub
) cat_data;
