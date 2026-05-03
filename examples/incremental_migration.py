"""
Example: Incremental (CDC-style) migration pattern.

Instead of migrating the full table on every run, this pattern:
1. Records the highest `updated_at` / `processed_at` watermark from the last run.
2. On the next run, only migrates rows changed since the watermark.
3. Uses Trino's INSERT OVERWRITE (via partition replacement) or MERGE to upsert.

This is NOT a full production CDC pipeline — for that you'd add Debezium +
Kafka + Flink. This example shows the lightweight polling approach suitable
for batch workloads with a reliable update timestamp column.

Requirements: Docker Compose stack running (`make up`) and initial migration
complete (`make migrate`).

Run:
    python examples/incremental_migration.py
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

WATERMARK_FILE = Path(".watermarks.json")


def load_watermarks() -> dict[str, str]:
    if WATERMARK_FILE.exists():
        return json.loads(WATERMARK_FILE.read_text())
    return {}


def save_watermarks(marks: dict[str, str]) -> None:
    WATERMARK_FILE.write_text(json.dumps(marks, indent=2))


def incremental_sync_table(
    table: str,
    ts_column: str,
    watermarks: dict[str, str],
) -> int:
    """
    Migrate rows from postgres.public.<table> where <ts_column> > last watermark.
    Returns the count of rows migrated.
    """
    from src.config import get_settings
    from src.connectors.trino import TrinoConnector

    cfg = get_settings()
    trino = TrinoConnector()
    trino.connect()

    cat = cfg.target_catalog
    sch = cfg.target_schema
    src_cat = "postgres"
    src_sch = cfg.source_schema

    last_mark = watermarks.get(table, "1970-01-01 00:00:00 UTC")
    log.info("Syncing %s since %s", table, last_mark)

    # Insert new/updated rows (append-only for simplicity; use MERGE for upserts)
    insert_sql = f"""
        INSERT INTO "{cat}"."{sch}"."{table}"
        SELECT *
        FROM "{src_cat}"."{src_sch}"."{table}"
        WHERE "{ts_column}" > TIMESTAMP '{last_mark}'
    """
    trino.execute_update(insert_sql)

    # Fetch new watermark from source
    mark_row = trino.execute(
        f'SELECT MAX("{ts_column}") AS wm '
        f'FROM "{src_cat}"."{src_sch}"."{table}"'
    )
    new_mark = str(mark_row[0]["wm"]) if mark_row and mark_row[0]["wm"] else last_mark
    watermarks[table] = new_mark

    # Count migrated rows
    count_sql = (
        f'SELECT COUNT(*) AS n FROM "{src_cat}"."{src_sch}"."{table}" '
        f'WHERE "{ts_column}" > TIMESTAMP \'{last_mark}\''
    )
    count_rows = trino.execute(count_sql)
    n = count_rows[0]["n"] if count_rows else 0
    trino.close()

    log.info("Synced %d rows for %s, new watermark: %s", n, table, new_mark)
    return n


def run_incremental_pipeline() -> None:
    # Tables with their reliable update-timestamp column
    incremental_tables = [
        ("customers", "updated_at"),
        ("orders", "updated_at"),
        ("transactions", "processed_at"),
    ]

    watermarks = load_watermarks()
    total = 0

    for table, ts_col in incremental_tables:
        try:
            n = incremental_sync_table(table, ts_col, watermarks)
            total += n
        except Exception as exc:
            log.error("Failed to sync %s: %s", table, exc)

    save_watermarks(watermarks)
    log.info("Incremental sync complete. Total rows synced: %d", total)
    log.info("Watermarks saved to %s", WATERMARK_FILE)


if __name__ == "__main__":
    run_incremental_pipeline()
