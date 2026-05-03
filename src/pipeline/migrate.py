"""
Migration orchestrator.

Strategy: Zero-Copy via Trino federation.

  INSERT INTO iceberg.warehouse.<table>
  SELECT ... FROM postgres.public.<table>

Trino reads PostgreSQL in-place via the JDBC connector and writes Parquet files
to MinIO through the Iceberg connector. No intermediate staging, no proprietary
tools.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from src.config import get_settings
from src.connectors.postgres import PostgresConnector, TableSchema
from src.connectors.trino import TrinoConnector
from src.metrics.prometheus import get_metrics
from src.pipeline.discover import discover_schema
from src.transpiler.engine import SqlTranspiler

log = logging.getLogger(__name__)
console = Console()


@dataclass
class TableMigrationResult:
    table: str
    success: bool
    source_rows: int = 0
    target_rows: int = 0
    duration_seconds: float = 0.0
    error: str = ""


@dataclass
class MigrationReport:
    results: list[TableMigrationResult] = field(default_factory=list)

    @property
    def total_tables(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def total_rows(self) -> int:
        return sum(r.target_rows for r in self.results)

    @property
    def total_seconds(self) -> float:
        return sum(r.duration_seconds for r in self.results)


class MigrationOrchestrator:
    def __init__(self) -> None:
        self.cfg = get_settings()
        self.pg = PostgresConnector()
        self.trino = TrinoConnector()
        self.transpiler = SqlTranspiler(source_dialect="postgres")
        self.metrics = get_metrics()

    def run(self, tables: list[str] | None = None) -> MigrationReport:
        """
        Run the full migration pipeline.

        1. Connect to both databases.
        2. Discover source tables (or use *tables* allowlist).
        3. For each table: create Iceberg table, migrate via INSERT SELECT.
        4. Return a MigrationReport.
        """
        self.pg.connect()
        self.trino.connect()
        report = MigrationReport()

        try:
            all_tables = discover_schema(self.pg)
            if tables:
                all_tables = [t for t in all_tables if t.name in tables]

            if not all_tables:
                console.print("[yellow]No tables found to migrate.[/]")
                return report

            self._ensure_target_schema()

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Migrating tables", total=len(all_tables))
                for ts in all_tables:
                    progress.update(task, description=f"[cyan]{ts.name}")
                    result = self._migrate_table(ts)
                    report.results.append(result)
                    progress.advance(task)

        finally:
            self.pg.close()
            self.trino.close()

        self._print_report(report)
        return report

    # ── Private helpers ───────────────────────────────────────────────────────

    def _ensure_target_schema(self) -> None:
        cat = self.cfg.target_catalog
        sch = self.cfg.target_schema
        if not self.trino.schema_exists(cat, sch):
            self.trino.execute_update(f"CREATE SCHEMA IF NOT EXISTS {cat}.{sch}")
            log.info("Created schema %s.%s", cat, sch)

    def _migrate_table(self, ts: TableSchema) -> TableMigrationResult:
        table = ts.name
        cat = self.cfg.target_catalog
        sch = self.cfg.target_schema
        src_cat = "postgres"
        src_sch = self.cfg.source_schema
        start = time.monotonic()

        log.info("Migrating %s (%s rows)…", table, f"{ts.row_count:,}")
        self.metrics.migration_table_rows.labels(table_name=table).set(ts.row_count)

        try:
            # 1. Build Iceberg CREATE TABLE from PG column metadata
            create_sql = self._build_create_table(ts)
            self.trino.execute_update(create_sql)
            log.debug("Created Iceberg table %s.%s.%s", cat, sch, table)

            # 2. Zero-copy INSERT SELECT via Trino federation
            col_list = self._safe_column_list(ts)
            insert_sql = (
                f'INSERT INTO "{cat}"."{sch}"."{table}" ({col_list})\n'
                f'SELECT {col_list} FROM "{src_cat}"."{src_sch}"."{table}"'
            )
            self.trino.execute_update(insert_sql)

            # 3. Count target rows
            target_rows = self.trino.row_count(cat, sch, table)
            duration = time.monotonic() - start

            self.metrics.migration_rows_inserted.labels(table_name=table).inc(target_rows)
            self.metrics.migration_table_duration.labels(table_name=table).set(duration)
            self.metrics.migration_tables_completed.inc()

            log.info(
                "✓ %s: %s rows in %.1fs",
                table,
                f"{target_rows:,}",
                duration,
            )
            return TableMigrationResult(
                table=table,
                success=True,
                source_rows=ts.row_count,
                target_rows=target_rows,
                duration_seconds=duration,
            )

        except Exception as exc:
            duration = time.monotonic() - start
            self.metrics.migration_errors.inc()
            log.error("✗ %s failed: %s", table, exc)
            return TableMigrationResult(
                table=table,
                success=False,
                source_rows=ts.row_count,
                duration_seconds=duration,
                error=str(exc),
            )

    def _build_create_table(self, ts: TableSchema) -> str:
        """Build an Iceberg-compatible CREATE TABLE DDL from TableSchema."""
        from src.transpiler.type_map import map_pg_type

        cat = self.cfg.target_catalog
        sch = self.cfg.target_schema
        cols = []
        for col in ts.columns:
            iceberg_type = map_pg_type(col.data_type)
            null_clause = "" if col.is_nullable else " NOT NULL"
            cols.append(f'    "{col.name}" {iceberg_type}{null_clause}')

        col_defs = ",\n".join(cols)
        return (
            f'CREATE TABLE IF NOT EXISTS "{cat}"."{sch}"."{ts.name}" (\n'
            f"{col_defs}\n"
            f") WITH (format = 'PARQUET')"
        )

    def _safe_column_list(self, ts: TableSchema) -> str:
        """Return a quoted, comma-separated column list, excluding SERIAL sequences."""
        serial_defaults = ("nextval(", "auto_increment")
        cols = []
        for col in ts.columns:
            default = (col.column_default or "").lower()
            if any(d in default for d in serial_defaults) and col.data_type in (
                "integer",
                "bigint",
                "smallint",
            ):
                # Still include the value — Trino reads it as-is from PG
                pass
            cols.append(f'"{col.name}"')
        return ", ".join(cols)

    def _print_report(self, report: MigrationReport) -> None:
        from rich.table import Table as RichTable

        t = RichTable(title="Migration Report", show_lines=True)
        t.add_column("Table", style="bold")
        t.add_column("Status")
        t.add_column("Source Rows", justify="right")
        t.add_column("Target Rows", justify="right")
        t.add_column("Duration")
        t.add_column("Error")

        for r in report.results:
            status = "[green]✓ OK[/]" if r.success else "[red]✗ FAIL[/]"
            t.add_row(
                r.table,
                status,
                f"{r.source_rows:,}",
                f"{r.target_rows:,}",
                f"{r.duration_seconds:.1f}s",
                r.error[:60] if r.error else "",
            )

        console.print(t)
        console.print(
            f"[bold]{'[green]' if report.failed == 0 else '[red]'}"
            f"{report.succeeded}/{report.total_tables} tables migrated, "
            f"{report.total_rows:,} rows, {report.total_seconds:.1f}s total[/]"
        )
