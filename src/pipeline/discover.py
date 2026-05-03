"""Schema discovery: introspect the PostgreSQL source and return table metadata."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.connectors.postgres import PostgresConnector, TableSchema

log = logging.getLogger(__name__)
console = Console()


def discover_schema(connector: PostgresConnector | None = None) -> list[TableSchema]:
    """
    Return a list of TableSchema objects for every user table in the source schema.
    Reuses an existing connector or creates a temporary one.
    """
    cfg = get_settings()
    owns_conn = connector is None
    pg = connector or PostgresConnector()

    try:
        if owns_conn:
            pg.connect()
        tables = pg.discover_tables(cfg.source_schema)
        log.info(
            "Discovered %d tables in schema '%s'",
            len(tables),
            cfg.source_schema,
        )
        return tables
    finally:
        if owns_conn:
            pg.close()


def print_schema_summary(tables: list[TableSchema]) -> None:
    """Pretty-print a table summary using Rich."""
    t = Table(title="Source Schema Summary", show_lines=True)
    t.add_column("Table", style="bold cyan")
    t.add_column("Columns", justify="right")
    t.add_column("Rows", justify="right")
    t.add_column("Primary Key")

    total_rows = 0
    for ts in tables:
        t.add_row(
            ts.name,
            str(len(ts.columns)),
            f"{ts.row_count:,}",
            ", ".join(ts.primary_key) or "—",
        )
        total_rows += ts.row_count

    console.print(t)
    console.print(
        f"[bold green]Total:[/] {len(tables)} tables, {total_rows:,} rows"
    )
