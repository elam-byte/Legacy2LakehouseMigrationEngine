-- Seed 500,000 financial transactions
INSERT INTO transactions (order_id, txn_ref, txn_type, amount, currency, gateway, gateway_txn_id, status, processed_at, settled_at)
SELECT
    1 + (i % 200000)                                                         AS order_id,
    'TXN-' || LPAD(i::TEXT, 10, '0')                                         AS txn_ref,
    (ARRAY['charge','charge','charge','charge','refund','adjustment','chargeback'])[1 + (i % 7)] AS txn_type,
    ROUND((CAST(random() * 4900 AS NUMERIC) + 10), 2)                        AS amount,
    'USD'                                                                     AS currency,
    (ARRAY['stripe','paypal','braintree','adyen','square'])[1 + (i % 5)]    AS gateway,
    'gw_' || md5(i::TEXT)                                                    AS gateway_txn_id,
    (ARRAY['success','success','success','success','success','failed','pending','reversed'])[1 + (i % 8)] AS status,
    NOW() - (i * 0.25 || ' hours')::INTERVAL                                AS processed_at,
    CASE WHEN i % 10 != 0 THEN NOW() - (i * 0.20 || ' hours')::INTERVAL ELSE NULL END AS settled_at
FROM generate_series(1, 500000) AS s(i);
