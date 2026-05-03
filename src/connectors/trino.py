"""Trino connector — query execution and schema management."""

from __future__ import annotations

import logging
from typing import Any

import trino

from src.config import get_settings

log = logging.getLogger(__name__)


class TrinoConnector:
    def __init__(self) -> None:
        cfg = get_settings()
        self._host = cfg.trino_host
        self._port = cfg.trino_port
        self._user = cfg.trino_user
        self._conn: trino.dbapi.Connection | None = None

    def connect(self) -> None:
        self._conn = trino.dbapi.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            http_scheme="http",
        )
        log.info("Connected to Trino at %s:%d", self._host, self._port)

    def _ensure_connected(self) -> trino.dbapi.Connection:
        if self._conn is None:
            self.connect()
        return self._conn

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute *sql* and return all rows as a list of dicts."""
        conn = self._ensure_connected()
        cur = conn.cursor()
        log.debug("Trino execute: %s", sql[:200])
        cur.execute(sql, params or None)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def execute_update(self, sql: str) -> None:
        """Execute a DDL or DML statement and discard results."""
        conn = self._ensure_connected()
        cur = conn.cursor()
        log.debug("Trino update: %s", sql[:200])
        cur.execute(sql)
        try:
            cur.fetchall()
        except Exception:
            pass

    def execute_many(self, statements: list[str]) -> list[str]:
        """Execute statements sequentially; return list of errors (empty = all ok)."""
        errors: list[str] = []
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                self.execute_update(stmt)
            except Exception as exc:
                msg = f"Failed: {stmt[:80]}... — {exc}"
                log.error(msg)
                errors.append(msg)
        return errors

    def schema_exists(self, catalog: str, schema: str) -> bool:
        rows = self.execute(
            f"SELECT schema_name FROM {catalog}.information_schema.schemata "
            f"WHERE schema_name = '{schema}'"
        )
        return len(rows) > 0

    def table_exists(self, catalog: str, schema: str, table: str) -> bool:
        rows = self.execute(
            f"SELECT table_name FROM {catalog}.information_schema.tables "
            f"WHERE table_schema = '{schema}' AND table_name = '{table}'"
        )
        return len(rows) > 0

    def row_count(self, catalog: str, schema: str, table: str) -> int:
        rows = self.execute(f'SELECT COUNT(*) AS n FROM "{catalog}"."{schema}"."{table}"')
        return rows[0]["n"] if rows else 0

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            log.info("Trino connection closed")

    def health_check(self) -> bool:
        try:
            self.execute("SELECT 1")
            return True
        except Exception as exc:
            log.warning("Trino health check failed: %s", exc)
            return False
