"""
Prometheus metrics for the migration engine.

Exposes an HTTP endpoint on port 8000 when start_http_server() is called.
Metrics are also available for scraping by Prometheus without starting the
server — the MigrationOrchestrator updates them directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prometheus_client import Counter, Gauge, Histogram, start_http_server


@dataclass
class MigrationMetrics:
    # Table-level counters and gauges
    migration_rows_inserted: Counter = field(
        default_factory=lambda: Counter(
            "migration_rows_inserted_total",
            "Total rows inserted into Iceberg",
            ["table_name"],
        )
    )
    migration_bytes_transferred: Counter = field(
        default_factory=lambda: Counter(
            "migration_bytes_transferred_total",
            "Approximate bytes written to MinIO",
            ["table_name"],
        )
    )
    migration_table_rows: Gauge = field(
        default_factory=lambda: Gauge(
            "migration_table_rows_total",
            "Source row count per table",
            ["table_name"],
        )
    )
    migration_table_duration: Gauge = field(
        default_factory=lambda: Gauge(
            "migration_table_duration_seconds",
            "Wall-clock seconds to migrate each table",
            ["table_name"],
        )
    )
    migration_tables_completed: Counter = field(
        default_factory=lambda: Counter(
            "migration_tables_completed_total",
            "Number of tables successfully migrated",
        )
    )
    migration_tables_validated_ok: Counter = field(
        default_factory=lambda: Counter(
            "migration_tables_validated_ok_total",
            "Number of tables that passed post-migration validation",
        )
    )
    migration_errors: Counter = field(
        default_factory=lambda: Counter(
            "migration_errors_total",
            "Total migration errors encountered",
        )
    )
    migration_cpu_seconds: Counter = field(
        default_factory=lambda: Counter(
            "migration_cpu_seconds_total",
            "Approximate CPU-seconds consumed (proxy for compute cost)",
        )
    )

    def start_server(self, port: int = 8000) -> None:
        start_http_server(port)


_metrics: MigrationMetrics | None = None


def get_metrics() -> MigrationMetrics:
    global _metrics
    if _metrics is None:
        _metrics = MigrationMetrics()
    return _metrics
