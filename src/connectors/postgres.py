"""PostgreSQL connector — schema discovery and streaming row extraction."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator, Iterator

import psycopg2
import psycopg2.extras

from src.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    column_default: str | None
    char_max_length: int | None
    numeric_precision: int | None
    numeric_scale: int | None


@dataclass
class TableSchema:
    name: str
    schema: str
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count: int = 0
    primary_key: list[str] = field(default_factory=list)


class PostgresConnector:
    def __init__(self, dsn: str | None = None) -> None:
        cfg = get_settings()
        self._dsn = dsn or cfg.postgres_dsn
        self._conn: psycopg2.extensions.connection | None = None

    def connect(self) -> None:
        self._conn = psycopg2.connect(self._dsn)
        self._conn.autocommit = False
        log.info("Connected to PostgreSQL at %s", self._dsn.split("@")[-1])

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
            log.info("PostgreSQL connection closed")

    @contextmanager
    def cursor(self):
        if self._conn is None or self._conn.closed:
            self.connect()
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur

    # ── Schema discovery ──────────────────────────────────────────────────────

    def discover_tables(self, schema: str = "public") -> list[TableSchema]:
        """Return metadata for all user tables in *schema*."""
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        with self.cursor() as cur:
            cur.execute(sql, (schema,))
            names = [row["table_name"] for row in cur.fetchall()]

        return [self.describe_table(name, schema) for name in names]

    def describe_table(self, table: str, schema: str = "public") -> TableSchema:
        col_sql = """
            SELECT
                column_name,
                data_type,
                is_nullable = 'YES'          AS is_nullable,
                column_default,
                character_maximum_length     AS char_max_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        pk_sql = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema    = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema    = %s
              AND tc.table_name      = %s
            ORDER BY kcu.ordinal_position
        """
        count_sql = f'SELECT COUNT(*) AS n FROM "{schema}"."{table}"'

        with self.cursor() as cur:
            cur.execute(col_sql, (schema, table))
            cols = [
                ColumnInfo(
                    name=r["column_name"],
                    data_type=r["data_type"],
                    is_nullable=r["is_nullable"],
                    column_default=r["column_default"],
                    char_max_length=r["char_max_length"],
                    numeric_precision=r["numeric_precision"],
                    numeric_scale=r["numeric_scale"],
                )
                for r in cur.fetchall()
            ]
            cur.execute(pk_sql, (schema, table))
            pk = [r["column_name"] for r in cur.fetchall()]
            cur.execute(count_sql)
            row_count = cur.fetchone()["n"]

        return TableSchema(
            name=table, schema=schema, columns=cols, row_count=row_count, primary_key=pk
        )

    # ── Data streaming ────────────────────────────────────────────────────────

    def stream_rows(
        self, table: str, schema: str = "public", batch_size: int = 10_000
    ) -> Iterator[list[dict]]:
        """Yield batches of rows as lists of dicts. Uses server-side cursor."""
        query = f'SELECT * FROM "{schema}"."{table}"'
        cursor_name = f"migrate_{schema}_{table}"

        if self._conn is None or self._conn.closed:
            self.connect()

        with self._conn.cursor(name=cursor_name, cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query)
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                yield [dict(r) for r in rows]

    def execute_scalar(self, sql: str, params: tuple = ()) -> object:
        with self.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return list(row.values())[0] if row else None
