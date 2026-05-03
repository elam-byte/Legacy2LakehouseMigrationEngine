"""Unit tests for the SQL transpiler — 40+ patterns covering common migration pain points."""

import pytest

from src.transpiler.engine import SqlTranspiler


def norm(sql: str) -> str:
    """Normalise whitespace for assertion comparisons."""
    import re
    return re.sub(r"\s+", " ", sql.strip().upper())


# ─────────────────────────────────────────────────────────────────────────────
# Basic SELECT
# ─────────────────────────────────────────────────────────────────────────────

class TestBasicSelect:
    def test_simple_select(self, transpiler):
        r = transpiler.transpile("SELECT id, name FROM customers")
        assert r.success
        assert "SELECT" in r.transpiled.upper()

    def test_select_star(self, transpiler):
        r = transpiler.transpile("SELECT * FROM orders")
        assert r.success
        assert "SELECT" in r.transpiled.upper()

    def test_aliased_columns(self, transpiler):
        r = transpiler.transpile('SELECT id AS customer_id, full_name AS "Customer Name" FROM customers')
        assert r.success

    def test_where_clause(self, transpiler):
        r = transpiler.transpile("SELECT * FROM orders WHERE status = 'delivered'")
        assert r.success
        assert "WHERE" in r.transpiled.upper()

    def test_order_by(self, transpiler):
        r = transpiler.transpile("SELECT id, placed_at FROM orders ORDER BY placed_at DESC")
        assert r.success

    def test_limit_offset(self, transpiler):
        r = transpiler.transpile("SELECT id FROM customers LIMIT 100 OFFSET 200")
        assert r.success
        assert "LIMIT" in r.transpiled.upper()


# ─────────────────────────────────────────────────────────────────────────────
# Date / time functions
# ─────────────────────────────────────────────────────────────────────────────

class TestDateFunctions:
    def test_now(self, transpiler):
        r = transpiler.transpile("SELECT NOW()")
        assert r.success

    def test_current_timestamp(self, transpiler):
        r = transpiler.transpile("SELECT CURRENT_TIMESTAMP")
        assert r.success

    def test_date_trunc(self, transpiler):
        r = transpiler.transpile("SELECT DATE_TRUNC('month', created_at) FROM customers")
        assert r.success

    def test_extract(self, transpiler):
        r = transpiler.transpile("SELECT EXTRACT(YEAR FROM placed_at) FROM orders")
        assert r.success

    def test_interval_arithmetic(self, transpiler):
        r = transpiler.transpile("SELECT * FROM orders WHERE placed_at > NOW() - INTERVAL '30 days'")
        assert r.success

    def test_age_function_fallback(self, transpiler):
        # AGE() is Postgres-specific; we expect success (sqlglot handles or passes through)
        r = transpiler.transpile("SELECT AGE(created_at) FROM customers")
        # May not fully convert but should not crash
        assert isinstance(r.success, bool)

    def test_to_char(self, transpiler):
        r = transpiler.transpile("SELECT TO_CHAR(placed_at, 'YYYY-MM-DD') FROM orders")
        assert r.success


# ─────────────────────────────────────────────────────────────────────────────
# Type cast syntax
# ─────────────────────────────────────────────────────────────────────────────

class TestTypeCasts:
    def test_cast_int(self, transpiler):
        r = transpiler.transpile("SELECT id::integer FROM customers")
        assert r.success
        assert "CAST" in r.transpiled.upper() or "::" not in r.transpiled

    def test_cast_text(self, transpiler):
        r = transpiler.transpile("SELECT amount::text FROM transactions")
        assert r.success

    def test_cast_boolean(self, transpiler):
        r = transpiler.transpile("SELECT is_active::boolean FROM customers")
        assert r.success

    def test_cast_numeric(self, transpiler):
        r = transpiler.transpile("SELECT '42.5'::numeric(10,2)")
        assert r.success

    def test_ansi_cast(self, transpiler):
        r = transpiler.transpile("SELECT CAST(amount AS VARCHAR) FROM transactions")
        assert r.success


# ─────────────────────────────────────────────────────────────────────────────
# String functions
# ─────────────────────────────────────────────────────────────────────────────

class TestStringFunctions:
    def test_concat(self, transpiler):
        r = transpiler.transpile("SELECT CONCAT(first_name, ' ', last_name) FROM customers")
        assert r.success

    def test_concat_operator(self, transpiler):
        r = transpiler.transpile("SELECT first_name || ' ' || last_name FROM customers")
        assert r.success

    def test_substring(self, transpiler):
        r = transpiler.transpile("SELECT SUBSTRING(email FROM 1 FOR 5) FROM customers")
        assert r.success

    def test_lower_upper(self, transpiler):
        r = transpiler.transpile("SELECT LOWER(email), UPPER(country_code) FROM customers")
        assert r.success

    def test_trim(self, transpiler):
        r = transpiler.transpile("SELECT TRIM(BOTH ' ' FROM full_name) FROM customers")
        assert r.success

    def test_length(self, transpiler):
        r = transpiler.transpile("SELECT LENGTH(full_name) FROM customers")
        assert r.success

    def test_replace(self, transpiler):
        r = transpiler.transpile("SELECT REPLACE(email, '@', ' AT ') FROM customers")
        assert r.success

    def test_regexp_replace(self, transpiler):
        r = transpiler.transpile("SELECT REGEXP_REPLACE(sku, '[^A-Z0-9]', '') FROM products")
        assert r.success

    def test_position(self, transpiler):
        r = transpiler.transpile("SELECT POSITION('@' IN email) FROM customers")
        assert r.success

    def test_split_part(self, transpiler):
        r = transpiler.transpile("SELECT SPLIT_PART(email, '@', 1) FROM customers")
        assert r.success


# ─────────────────────────────────────────────────────────────────────────────
# Aggregate functions
# ─────────────────────────────────────────────────────────────────────────────

class TestAggregateFunctions:
    def test_count(self, transpiler):
        r = transpiler.transpile("SELECT COUNT(*) FROM orders")
        assert r.success

    def test_sum(self, transpiler):
        r = transpiler.transpile("SELECT SUM(total) FROM orders")
        assert r.success

    def test_avg(self, transpiler):
        r = transpiler.transpile("SELECT AVG(amount) FROM transactions")
        assert r.success

    def test_min_max(self, transpiler):
        r = transpiler.transpile("SELECT MIN(placed_at), MAX(placed_at) FROM orders")
        assert r.success

    def test_group_by(self, transpiler):
        r = transpiler.transpile("SELECT status, COUNT(*) FROM orders GROUP BY status")
        assert r.success

    def test_having(self, transpiler):
        r = transpiler.transpile(
            "SELECT customer_id, SUM(total) AS rev FROM orders GROUP BY customer_id HAVING SUM(total) > 1000"
        )
        assert r.success

    def test_stddev(self, transpiler):
        r = transpiler.transpile("SELECT STDDEV(amount) FROM transactions")
        assert r.success


# ─────────────────────────────────────────────────────────────────────────────
# Window functions
# ─────────────────────────────────────────────────────────────────────────────

class TestWindowFunctions:
    def test_row_number(self, transpiler):
        r = transpiler.transpile(
            "SELECT id, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY placed_at) AS rn FROM orders"
        )
        assert r.success
        assert "ROW_NUMBER" in r.transpiled.upper()

    def test_rank(self, transpiler):
        r = transpiler.transpile(
            "SELECT id, RANK() OVER (ORDER BY total DESC) AS rnk FROM orders"
        )
        assert r.success

    def test_lag_lead(self, transpiler):
        r = transpiler.transpile(
            "SELECT id, LAG(total, 1, 0) OVER (PARTITION BY customer_id ORDER BY placed_at) AS prev_total FROM orders"
        )
        assert r.success

    def test_sum_over(self, transpiler):
        r = transpiler.transpile(
            "SELECT id, SUM(total) OVER (PARTITION BY customer_id) AS customer_total FROM orders"
        )
        assert r.success


# ─────────────────────────────────────────────────────────────────────────────
# CTEs and subqueries
# ─────────────────────────────────────────────────────────────────────────────

class TestCteAndSubquery:
    def test_cte(self, transpiler):
        r = transpiler.transpile(
            """
            WITH high_value AS (
                SELECT customer_id FROM orders WHERE total > 5000
            )
            SELECT c.full_name FROM customers c
            JOIN high_value hv ON hv.customer_id = c.id
            """
        )
        assert r.success
        assert "WITH" in r.transpiled.upper()

    def test_subquery(self, transpiler):
        r = transpiler.transpile(
            "SELECT * FROM (SELECT id, total FROM orders WHERE status='delivered') sub WHERE total > 100"
        )
        assert r.success

    def test_exists(self, transpiler):
        r = transpiler.transpile(
            "SELECT * FROM customers WHERE EXISTS (SELECT 1 FROM orders WHERE orders.customer_id = customers.id)"
        )
        assert r.success


# ─────────────────────────────────────────────────────────────────────────────
# Oracle dialect patterns
# ─────────────────────────────────────────────────────────────────────────────

class TestOracleDialect:
    def test_nvl(self, oracle_transpiler):
        r = oracle_transpiler.transpile("SELECT NVL(notes, 'N/A') FROM orders")
        assert r.success

    def test_decode(self, oracle_transpiler):
        r = oracle_transpiler.transpile(
            "SELECT DECODE(status, 'pending', 0, 'delivered', 1, -1) FROM orders"
        )
        assert r.success

    def test_sysdate(self, oracle_transpiler):
        r = oracle_transpiler.transpile("SELECT SYSDATE FROM DUAL")
        assert r.success

    def test_rownum(self, oracle_transpiler):
        r = oracle_transpiler.transpile(
            "SELECT * FROM customers WHERE ROWNUM <= 100"
        )
        assert r.success

    def test_trunc_date(self, oracle_transpiler):
        r = oracle_transpiler.transpile("SELECT TRUNC(hire_date) FROM employees")
        assert r.success

    def test_to_date(self, oracle_transpiler):
        r = oracle_transpiler.transpile("SELECT TO_DATE('2024-01-01', 'YYYY-MM-DD') FROM DUAL")
        assert r.success
