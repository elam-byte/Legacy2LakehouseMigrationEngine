"""Post-migration validation: row count and checksum reconciliation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.connectors.postgres import PostgresConnector
from src.connectors.trino import TrinoConnector
from src.metrics.prometheus import get_metrics

log = logging.getLogger(__name__)
console = Console()


@dataclass
class ValidationResult:
    table: str
    source_count: int
    target_count: int
    count_match: bool
    source_id_sum: int | None
    target_id_sum: int | None
    checksum_match: bool | None

    @property
    def passed(self) -> bool:
        if not self.count_match:
            return False
        if self.checksum_match is not None:
            return self.checksum_match
        return True


def validate_migration(tables: list[str] | None = None) -> list[ValidationResult]:
    """
    For each table, compare COUNT(*) and SUM(id) between source and target.
    Returns a list of ValidationResult objects.
    """
    cfg = get_settings()
    pg = PostgresConnector()
    trino = TrinoConnector()
    metrics = get_metrics()

    pg.connect()
    trino.connect()
    results: list[ValidationResult] = []

    try:
        if tables is None:
            # Auto-discover from Iceberg
            rows = trino.execute(
                f"SELECT table_name FROM {cfg.target_catalog}.information_schema.tables "
                f"WHERE table_schema = '{cfg.target_schema}'"
            )
            tables = [r["table_name"] for r in rows]

        for table in tables:
            result = _validate_table(table, pg, trino, cfg)
            results.append(result)
            if result.passed:
                metrics.migration_tables_validated_ok.inc()

    finally:
        pg.close()
        trino.close()

    _print_validation_report(results)
    return results


def _validate_table(table, pg, trino, cfg) -> ValidationResult:
    src_sch = cfg.source_schema
    cat = cfg.target_catalog
    sch = cfg.target_schema

    src_count = pg.execute_scalar(f'SELECT COUNT(*) FROM "{src_sch}"."{table}"') or 0
    tgt_count = trino.row_count(cat, sch, table)
    count_match = src_count == tgt_count

    # Checksum: only if both sides have an 'id' column
    src_id_sum = None
    tgt_id_sum = None
    checksum_match = None
    try:
        src_id_sum = int(
            pg.execute_scalar(f'SELECT COALESCE(SUM(id), 0) FROM "{src_sch}"."{table}"') or 0
        )
        rows = trino.execute(
            f'SELECT COALESCE(SUM(CAST(id AS BIGINT)), 0) AS s '
            f'FROM "{cat}"."{sch}"."{table}"'
        )
        tgt_id_sum = int(rows[0]["s"]) if rows else 0
        checksum_match = src_id_sum == tgt_id_sum
    except Exception:
        pass  # Table has no 'id' column or type is incompatible

    return ValidationResult(
        table=table,
        source_count=src_count,
        target_count=tgt_count,
        count_match=count_match,
        source_id_sum=src_id_sum,
        target_id_sum=tgt_id_sum,
        checksum_match=checksum_match,
    )


def _print_validation_report(results: list[ValidationResult]) -> None:
    t = Table(title="Validation Report", show_lines=True)
    t.add_column("Table", style="bold")
    t.add_column("Source Count", justify="right")
    t.add_column("Target Count", justify="right")
    t.add_column("Count OK?")
    t.add_column("Checksum OK?")
    t.add_column("Status")

    passed = 0
    for r in results:
        ok = "[green]✓[/]"
        fail = "[red]✗[/]"
        na = "[dim]n/a[/]"
        status = "[green]PASS[/]" if r.passed else "[red]FAIL[/]"
        if r.passed:
            passed += 1
        t.add_row(
            r.table,
            f"{r.source_count:,}",
            f"{r.target_count:,}",
            ok if r.count_match else fail,
            ok if r.checksum_match else (fail if r.checksum_match is False else na),
            status,
        )

    console.print(t)
    total = len(results)
    color = "green" if passed == total else "red"
    console.print(f"[bold {color}]{passed}/{total} tables passed validation[/]")
