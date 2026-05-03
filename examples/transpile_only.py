"""
Example: SQL transpilation without data movement.

Demonstrates how to use the SqlTranspiler to convert legacy SQL
to Trino-compatible SQL purely in Python — no database required.

Run:
    python examples/transpile_only.py
"""

from src.transpiler.engine import SqlTranspiler

# ── PostgreSQL → Trino examples ───────────────────────────────────────────────

pg_transpiler = SqlTranspiler(source_dialect="postgres")

print("=" * 70)
print("PostgreSQL → Trino Transpilation Examples")
print("=" * 70)

examples = [
    (
        "Date arithmetic",
        "SELECT * FROM orders WHERE placed_at > NOW() - INTERVAL '30 days'",
    ),
    (
        "Type cast (::) syntax",
        "SELECT amount::numeric(12,2), status::text FROM transactions",
    ),
    (
        "Date truncation",
        "SELECT DATE_TRUNC('month', placed_at), COUNT(*) FROM orders GROUP BY 1",
    ),
    (
        "Window function",
        """SELECT
    customer_id,
    placed_at,
    SUM(total) OVER (
        PARTITION BY customer_id
        ORDER BY placed_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total
FROM orders""",
    ),
    (
        "CTE with joins",
        """WITH top_customers AS (
    SELECT customer_id, SUM(total) AS ltv
    FROM orders
    WHERE status = 'delivered'
    GROUP BY customer_id
    HAVING SUM(total) > 10000
)
SELECT c.full_name, c.email, tc.ltv
FROM customers c
JOIN top_customers tc ON tc.customer_id = c.id
ORDER BY tc.ltv DESC
LIMIT 50""",
    ),
    (
        "REGEXP_REPLACE",
        "SELECT REGEXP_REPLACE(email, '@.*$', '') AS username FROM customers",
    ),
    (
        "EXTRACT",
        "SELECT EXTRACT(YEAR FROM processed_at) AS yr, SUM(amount) FROM transactions GROUP BY 1",
    ),
]

for title, sql in examples:
    result = pg_transpiler.transpile(sql)
    status = "✓" if result.success else "⚠"
    print(f"\n[{status}] {title}")
    print("  Input:  ", sql[:80].replace("\n", " ").strip())
    print("  Output: ", result.transpiled[:120].replace("\n", " ").strip())
    if result.warnings:
        for w in result.warnings:
            print(f"  Warning: {w}")

# ── Oracle → Trino examples ───────────────────────────────────────────────────

print("\n" + "=" * 70)
print("Oracle → Trino Transpilation Examples")
print("=" * 70)

oracle_transpiler = SqlTranspiler(source_dialect="oracle")

oracle_examples = [
    ("NVL function", "SELECT NVL(notes, 'No notes') FROM orders"),
    ("DECODE function", "SELECT DECODE(status,'pending','P','delivered','D','X') FROM orders"),
    ("ROWNUM pagination", "SELECT * FROM customers WHERE ROWNUM <= 100"),
    ("SYSDATE", "SELECT * FROM orders WHERE placed_at > SYSDATE - 30"),
    ("TRUNC date", "SELECT TRUNC(processed_at) AS txn_date FROM transactions"),
    ("TO_DATE", "SELECT TO_DATE('2024-01-01', 'YYYY-MM-DD') FROM DUAL"),
]

for title, sql in oracle_examples:
    result = oracle_transpiler.transpile(sql)
    status = "✓" if result.success else "⚠"
    print(f"\n[{status}] {title}")
    print("  Input:  ", sql)
    print("  Output: ", result.transpiled[:120].replace("\n", " ").strip())

print("\nDone.")
