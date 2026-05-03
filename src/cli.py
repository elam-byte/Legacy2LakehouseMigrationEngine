"""
migrate-engine CLI
==================

Commands:
  status      Check connectivity to all services
  discover    Print source schema summary
  transpile   Transpile a SQL file from legacy dialect to Trino SQL
  migrate     Run the full migration pipeline
  validate    Post-migration row-count and checksum validation
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Legacy-to-Lakehouse Migration Engine — Postgres/Oracle → Apache Iceberg via Trino."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


# ── status ────────────────────────────────────────────────────────────────────

@cli.command()
def status() -> None:
    """Check connectivity to PostgreSQL, Trino, MinIO, and Nessie."""
    import urllib.request

    from src.config import get_settings
    from src.connectors.postgres import PostgresConnector
    from src.connectors.trino import TrinoConnector

    cfg = get_settings()
    ok = True

    # PostgreSQL
    try:
        pg = PostgresConnector()
        pg.connect()
        pg.close()
        console.print("[green]✓[/] PostgreSQL reachable")
    except Exception as exc:
        console.print(f"[red]✗[/] PostgreSQL: {exc}")
        ok = False

    # Trino
    trino = TrinoConnector()
    if trino.health_check():
        console.print("[green]✓[/] Trino reachable")
    else:
        console.print("[red]✗[/] Trino not reachable")
        ok = False

    # MinIO
    try:
        url = f"{cfg.minio_endpoint}/minio/health/live"
        urllib.request.urlopen(url, timeout=5)
        console.print("[green]✓[/] MinIO reachable")
    except Exception as exc:
        console.print(f"[red]✗[/] MinIO: {exc}")
        ok = False

    # Nessie
    try:
        url = f"{cfg.nessie_uri.rstrip('/api/v2')}/api/v2/config"
        urllib.request.urlopen(url, timeout=5)
        console.print("[green]✓[/] Nessie reachable")
    except Exception as exc:
        console.print(f"[yellow]?[/] Nessie: {exc}")

    sys.exit(0 if ok else 1)


# ── discover ──────────────────────────────────────────────────────────────────

@cli.command()
def discover() -> None:
    """Introspect the PostgreSQL source schema and print a summary table."""
    from src.pipeline.discover import discover_schema, print_schema_summary

    tables = discover_schema()
    print_schema_summary(tables)


# ── transpile ─────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("sql_file", type=click.Path(exists=True, path_type=Path))
@click.option("--source", "-s", default="postgres", show_default=True,
              type=click.Choice(["postgres", "oracle", "mysql", "tsql"]),
              help="Source SQL dialect")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None,
              help="Write transpiled SQL to this file (default: stdout)")
def transpile(sql_file: Path, source: str, output: Path | None) -> None:
    """Transpile a SQL file from a legacy dialect to Trino SQL."""
    from src.transpiler.engine import SqlTranspiler

    t = SqlTranspiler(source_dialect=source)  # type: ignore[arg-type]
    results = t.transpile_file(sql_file, source=source)  # type: ignore[arg-type]

    lines = []
    for r in results:
        if not r.success:
            console.print(f"[yellow]Warning:[/] {r.warnings[0][:100]}")
        lines.append(r.transpiled)

    out_sql = ";\n\n".join(lines) + ";"

    if output:
        output.write_text(out_sql, encoding="utf-8")
        console.print(f"[green]✓[/] Written to {output}")
    else:
        click.echo(out_sql)


# ── migrate ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--table", "-t", multiple=True,
              help="Migrate only these tables (repeat for multiple). Default: all.")
@click.option("--metrics-port", default=0, show_default=True,
              help="Start Prometheus metrics server on this port (0 = disabled)")
def migrate(table: tuple[str, ...], metrics_port: int) -> None:
    """Run the full migration pipeline: PostgreSQL → Iceberg via Trino."""
    from src.metrics.prometheus import get_metrics
    from src.pipeline.migrate import MigrationOrchestrator

    if metrics_port:
        get_metrics().start_server(metrics_port)
        console.print(f"[dim]Metrics server started on :{metrics_port}[/]")

    orchestrator = MigrationOrchestrator()
    report = orchestrator.run(tables=list(table) if table else None)

    sys.exit(0 if report.failed == 0 else 1)


# ── validate ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--table", "-t", multiple=True,
              help="Validate only these tables. Default: all Iceberg tables.")
def validate(table: tuple[str, ...]) -> None:
    """Post-migration validation: compare row counts and checksums."""
    from src.pipeline.validate import validate_migration

    results = validate_migration(tables=list(table) if table else None)
    failed = [r for r in results if not r.passed]
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    cli()
