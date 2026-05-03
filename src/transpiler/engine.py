"""
SQL transpiler: converts legacy Postgres/Oracle SQL → Trino-compatible SQL
using sqlglot as the parsing and rewriting backbone.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import sqlglot
import sqlglot.expressions as exp
from sqlglot import parse_one, transpile

from src.transpiler.type_map import map_pg_type

log = logging.getLogger(__name__)

Dialect = Literal["postgres", "oracle", "mysql", "tsql", "trino"]


@dataclass
class TranspileResult:
    original: str
    transpiled: str
    warnings: list[str]
    success: bool


class SqlTranspiler:
    """
    Converts SQL statements from a legacy dialect to Trino SQL.

    Usage::

        t = SqlTranspiler()
        result = t.transpile("SELECT * FROM users WHERE created_at > NOW()")
        print(result.transpiled)
    """

    def __init__(self, source_dialect: Dialect = "postgres") -> None:
        self.source_dialect = source_dialect

    # ── Public API ────────────────────────────────────────────────────────────

    def transpile(
        self,
        sql: str,
        source: Dialect | None = None,
        target: Dialect = "trino",
    ) -> TranspileResult:
        """Transpile a single SQL statement."""
        src = source or self.source_dialect
        warnings: list[str] = []

        try:
            statements = transpile(sql, read=src, write=target, error_level=None)
            transpiled = ";\n".join(s for s in statements if s.strip())
            return TranspileResult(
                original=sql,
                transpiled=transpiled,
                warnings=warnings,
                success=True,
            )
        except Exception as exc:
            log.warning("Transpile failed for: %s... — %s", sql[:80], exc)
            return TranspileResult(
                original=sql,
                transpiled=sql,
                warnings=[str(exc)],
                success=False,
            )

    def transpile_file(
        self,
        path: Path,
        source: Dialect | None = None,
        target: Dialect = "trino",
    ) -> list[TranspileResult]:
        """Split a SQL file by semicolons and transpile each statement."""
        raw = path.read_text(encoding="utf-8")
        statements = [s.strip() for s in raw.split(";") if s.strip()]
        return [self.transpile(s, source=source, target=target) for s in statements]

    def transpile_ddl_for_iceberg(
        self,
        create_table_sql: str,
        target_catalog: str = "iceberg",
        target_schema: str = "warehouse",
        source: Dialect | None = None,
    ) -> str:
        """
        Convert a PostgreSQL CREATE TABLE statement into an Iceberg-compatible
        CREATE TABLE statement suitable for execution on Trino.

        Key transformations applied beyond sqlglot:
        - Strips SERIAL/BIGSERIAL → INTEGER/BIGINT (Iceberg has no sequences)
        - Rewrites column types via type_map
        - Removes unsupported constraints (CHECK, DEFAULT expressions, FK refs)
        - Adds Iceberg WITH options (format, partitioning)
        - Prefixes table name with catalog.schema
        """
        src = source or self.source_dialect
        warnings: list[str] = []

        try:
            tree = parse_one(create_table_sql, dialect=src)
        except Exception as exc:
            log.error("Could not parse DDL: %s", exc)
            return create_table_sql

        if not isinstance(tree, exp.Create):
            return self.transpile(create_table_sql, source=src).transpiled

        table_expr = tree.find(exp.Table)
        if table_expr:
            table_name = table_expr.name
            table_expr.set("db", exp.to_identifier(target_schema))
            table_expr.set("catalog", exp.to_identifier(target_catalog))

        # Rewrite column definitions
        schema_def = tree.find(exp.Schema)
        if schema_def:
            new_exprs = []
            for expr in schema_def.expressions:
                if isinstance(expr, exp.ColumnDef):
                    expr = self._rewrite_column_def(expr, warnings)
                    new_exprs.append(expr)
                # Drop table-level constraints (PK, FK, CHECK, UNIQUE)
                elif isinstance(expr, (exp.ForeignKey, exp.Check)):
                    warnings.append(f"Dropped constraint: {expr.sql()[:60]}")
                else:
                    new_exprs.append(expr)
            schema_def.set("expressions", new_exprs)

        # Strip CREATE TABLE properties that Trino doesn't understand
        tree.set("properties", None)

        # Add Iceberg WITH clause
        iceberg_with = " WITH (format = 'PARQUET', partitioning = ARRAY[])"

        ddl = tree.sql(dialect="trino")
        # sqlglot may drop WITH if properties were None; append manually
        if "WITH (" not in ddl.upper():
            ddl = ddl.rstrip(";") + iceberg_with

        for w in warnings:
            log.debug("DDL warning: %s", w)

        return ddl

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _rewrite_column_def(
        self, col: exp.ColumnDef, warnings: list[str]
    ) -> exp.ColumnDef:
        """Normalise a single column definition for Iceberg/Trino."""
        # Remap type
        if col.kind:
            pg_type_str = col.kind.sql(dialect="postgres").lower()
            trino_type_str = map_pg_type(pg_type_str)
            try:
                new_kind = parse_one(trino_type_str, into=exp.DataType, dialect="trino")
                col.set("kind", new_kind)
            except Exception:
                warnings.append(f"Could not parse mapped type '{trino_type_str}' for column '{col.name}'")

        # Remove column-level constraints unsupported by Iceberg
        clean_constraints = []
        for constraint in col.constraints:
            kind = constraint.kind
            if isinstance(kind, (exp.GeneratedAsIdentityColumnConstraint, exp.AutoIncrementColumnConstraint)):
                warnings.append(f"Dropped AUTO_INCREMENT/SERIAL on '{col.name}'")
                continue
            if isinstance(kind, exp.CheckColumnConstraint):
                continue
            if isinstance(kind, exp.DefaultColumnConstraint):
                continue
            if isinstance(kind, exp.UniqueColumnConstraint):
                continue
            clean_constraints.append(constraint)
        col.set("constraints", clean_constraints)
        return col


# ── Convenience function ──────────────────────────────────────────────────────

_default_transpiler: SqlTranspiler | None = None


def get_transpiler(source_dialect: Dialect = "postgres") -> SqlTranspiler:
    global _default_transpiler
    if _default_transpiler is None or _default_transpiler.source_dialect != source_dialect:
        _default_transpiler = SqlTranspiler(source_dialect)
    return _default_transpiler
