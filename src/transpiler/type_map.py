"""
PostgreSQL → Iceberg/Trino type coercion rules.

sqlglot handles most type translations automatically. This module patches
the cases sqlglot either misses or translates to a non-Iceberg-compatible form.
"""

from __future__ import annotations

import re

# Maps (postgres_type_pattern → trino/iceberg_type)
# Keys are lowercase, may contain regex-style wildcards only for the lookup below.
_EXACT: dict[str, str] = {
    "serial": "INTEGER",
    "bigserial": "BIGINT",
    "smallserial": "SMALLINT",
    "text": "VARCHAR",
    "bytea": "VARBINARY",
    "bool": "BOOLEAN",
    "boolean": "BOOLEAN",
    "jsonb": "VARCHAR",       # Iceberg has no native JSON; store as VARCHAR
    "json": "VARCHAR",
    "uuid": "UUID",
    "timestamptz": "TIMESTAMP(6) WITH TIME ZONE",
    "timestamp with time zone": "TIMESTAMP(6) WITH TIME ZONE",
    "timestamp without time zone": "TIMESTAMP(6)",
    "date": "DATE",
    "time": "TIME",
    "timetz": "TIME WITH TIME ZONE",
    "interval": "VARCHAR",    # No Iceberg equivalent; cast to string
    "oid": "BIGINT",
    "name": "VARCHAR",
    "char": "CHAR",
    "bpchar": "CHAR",
    "int2": "SMALLINT",
    "int4": "INTEGER",
    "int8": "BIGINT",
    "float4": "REAL",
    "float8": "DOUBLE",
    "real": "REAL",
    "double precision": "DOUBLE",
    "money": "DECIMAL(19,4)",  # Postgres money → fixed-precision decimal
}


def map_pg_type(pg_type: str) -> str:
    """
    Return the Trino/Iceberg equivalent of a PostgreSQL column type string.

    Handles parameterised types like ``numeric(10,2)``, ``varchar(255)``,
    ``character varying(100)`` etc.
    """
    t = pg_type.strip().lower()

    # Exact match first (covers most cases)
    if t in _EXACT:
        return _EXACT[t]

    # Arrays with parameterised inner types: varchar(n)[] → ARRAY(VARCHAR(n))
    # Must be checked before the bare varchar(n) pattern below.
    m = re.match(r"(.+)\[\]$", t)
    if m:
        inner = map_pg_type(m.group(1))
        return f"ARRAY({inner})"

    # character varying(n) → varchar(n)
    m = re.match(r"character varying\((\d+)\)", t)
    if m:
        return f"VARCHAR({m.group(1)})"

    # varchar(n)
    m = re.match(r"varchar\((\d+)\)", t)
    if m:
        return f"VARCHAR({m.group(1)})"

    # character(n) / char(n)
    m = re.match(r"(?:character|char)\((\d+)\)", t)
    if m:
        return f"CHAR({m.group(1)})"

    # numeric(p,s) / decimal(p,s)
    m = re.match(r"(?:numeric|decimal)\((\d+),\s*(\d+)\)", t)
    if m:
        return f"DECIMAL({m.group(1)},{m.group(2)})"

    # numeric(p) / decimal(p)
    m = re.match(r"(?:numeric|decimal)\((\d+)\)", t)
    if m:
        return f"DECIMAL({m.group(1)},0)"

    # numeric / decimal (no params)
    if t in ("numeric", "decimal"):
        return "DECIMAL(38,9)"

    # timestamp(n)
    m = re.match(r"timestamp\((\d+)\)$", t)
    if m:
        return f"TIMESTAMP({m.group(1)})"

    # timestamp(n) with time zone
    m = re.match(r"timestamp\((\d+)\) with time zone", t)
    if m:
        return f"TIMESTAMP({m.group(1)}) WITH TIME ZONE"

    # integer / int
    if t in ("integer", "int"):
        return "INTEGER"

    # bigint
    if t == "bigint":
        return "BIGINT"

    # smallint
    if t == "smallint":
        return "SMALLINT"

    # Unknown → pass through (let Trino reject at DDL time)
    return pg_type.upper()
