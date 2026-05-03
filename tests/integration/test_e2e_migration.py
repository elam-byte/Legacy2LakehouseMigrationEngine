"""
End-to-end integration tests.

Requires the full Docker Compose stack to be running:
  make up && make wait

Run with:
  pytest tests/integration -m integration
"""

import os

import pytest


pytestmark = pytest.mark.integration

SKIP_REASON = "Docker Compose stack not running (set RUN_INTEGRATION_TESTS=1 to enable)"
ENABLED = os.getenv("RUN_INTEGRATION_TESTS", "").strip() == "1"


@pytest.fixture(scope="module")
def pg():
    if not ENABLED:
        pytest.skip(SKIP_REASON)
    from src.connectors.postgres import PostgresConnector
    conn = PostgresConnector()
    conn.connect()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def trino():
    if not ENABLED:
        pytest.skip(SKIP_REASON)
    from src.connectors.trino import TrinoConnector
    conn = TrinoConnector()
    conn.connect()
    yield conn
    conn.close()


class TestPostgresConnectivity:
    def test_can_list_tables(self, pg):
        tables = pg.discover_tables("public")
        names = [t.name for t in tables]
        assert "customers" in names
        assert "orders" in names

    def test_customers_row_count(self, pg):
        tables = pg.discover_tables("public")
        customers = next(t for t in tables if t.name == "customers")
        assert customers.row_count == 50_000

    def test_stream_rows(self, pg):
        batches = list(pg.stream_rows("customers", batch_size=1000))
        total = sum(len(b) for b in batches)
        assert total == 50_000


class TestTrinoConnectivity:
    def test_health_check(self, trino):
        assert trino.health_check()

    def test_federated_postgres_query(self, trino):
        rows = trino.execute("SELECT COUNT(*) AS n FROM postgres.public.customers")
        assert rows[0]["n"] == 50_000

    def test_iceberg_schema_exists(self, trino):
        assert trino.schema_exists("iceberg", "warehouse")


class TestMigrationPipeline:
    def test_single_table_migration(self, trino):
        from src.pipeline.migrate import MigrationOrchestrator
        orch = MigrationOrchestrator()
        report = orch.run(tables=["customers"])
        assert report.succeeded == 1
        assert report.failed == 0

    def test_validation_passes(self, trino):
        from src.pipeline.validate import validate_migration
        results = validate_migration(tables=["customers"])
        assert all(r.passed for r in results)

    def test_federated_cross_catalog_join(self, trino):
        sql = """
            SELECT c.tier, COUNT(o.id) AS orders
            FROM postgres.public.customers c
            JOIN iceberg.warehouse.orders o ON o.customer_id = c.id
            GROUP BY c.tier
            ORDER BY orders DESC
            LIMIT 5
        """
        rows = trino.execute(sql)
        assert len(rows) > 0
