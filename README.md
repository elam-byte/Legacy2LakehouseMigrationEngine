# Legacy-to-Lakehouse Migration Engine

A production-quality, fully open-source toolkit that modernises legacy relational workloads (PostgreSQL/Oracle) into an Open Lakehouse format (Apache Iceberg on MinIO) using Trino as the zero-copy migration engine.

---

## Why This Project Exists

### The Problem

Enterprises accumulate years of critical business data in traditional RDBMS systems — Oracle, PostgreSQL, SQL Server. These systems are:

| Pain Point | Impact |
|------------|--------|
| **Vendor lock-in** | Proprietary SQL dialects, licensing costs, forced upgrade cycles |
| **Poor analytical performance** | Row-oriented storage is slow for aggregations over millions of rows |
| **No time-travel / schema evolution** | Fixing a bad migration requires restoring from backup |
| **Storage and compute are coupled** | Can't scale storage independently of compute |
| **No open standard** | Data is trapped; switching engines requires a full rewrite |

### The Modern Alternative: Open Lakehouse

Apache Iceberg + open object storage (MinIO/S3) solves every one of these:

- **Vendor-neutral format** — any engine (Trino, Spark, Flink, DuckDB) reads the same files
- **Columnar Parquet storage** — 10–100× faster for analytical queries
- **Time-travel queries** — `SELECT * FROM table FOR TIMESTAMP AS OF '2024-01-01'`
- **Schema evolution** — add/rename/drop columns without rewriting data
- **Decoupled storage/compute** — store petabytes on cheap object storage; spin up compute on demand

### What This Engine Does

This toolkit provides the **bridge** between those two worlds:

1. Introspects your legacy PostgreSQL schema automatically
2. Transpiles SQL dialects (Postgres/Oracle → Trino) using `sqlglot`
3. Migrates data **without staging files** — Trino reads Postgres in-place and writes Iceberg directly
4. Validates the migration with row counts and checksums
5. Tracks everything in a FinOps Grafana dashboard

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Docker Compose Network: lakehouse                   │
│                                                                             │
│   ┌──────────────┐        ┌─────────────────────────────────────────────┐  │
│   │  PostgreSQL  │        │                 TRINO :8080                  │  │
│   │  :5432       │◄──────►│   ┌──────────────┐  ┌────────────────────┐  │  │
│   │  (legacy DB) │  JDBC  │   │ PG Connector │  │ Iceberg Connector  │  │  │
│   │  5 tables    │        │   │ (reads rows) │  │ (writes Parquet)   │  │  │
│   │  ~755k rows  │        │   └──────────────┘  └────────┬───────────┘  │  │
│   └──────────────┘        └─────────────────────────────┼───────────────┘  │
│                                                          │                  │
│   ┌──────────────┐        ┌─────────────────────────────▼───────────────┐  │
│   │   NESSIE     │        │                  MinIO :9000                 │  │
│   │  :19120      │◄──────►│            S3-compatible object store        │  │
│   │  (Iceberg    │ REST   │            Parquet files in /warehouse/       │  │
│   │   catalog)   │        │                                               │  │
│   └──────────────┘        └───────────────────────────────────────────────┘  │
│                                                                             │
│   ┌──────────────┐        ┌──────────────────────────────────────────────┐ │
│   │  PROMETHEUS  │        │              GRAFANA :3000                   │ │
│   │  :9090       │───────►│   FinOps Dashboard: rows/sec, bytes/sec,     │ │
│   │  (metrics)   │        │   cost estimates, MinIO storage, errors      │ │
│   └──────────────┘        └──────────────────────────────────────────────┘ │
│                                                                             │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │                   Python Migration Engine (CLI)                    │   │
│   │   sqlglot transpiler • psycopg2 connector • trino-python-client    │   │
│   │   discover → transpile DDL → CREATE TABLE → INSERT SELECT           │   │
│   └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Zero-Copy Migration

```
PostgreSQL                    Trino                          MinIO / Iceberg
─────────                     ─────                          ───────────────
customers (50k rows)   ──►  INSERT INTO iceberg.warehouse.customers
products  (5k rows)    ──►  SELECT * FROM postgres.public.products    ──►  s3://warehouse/customers/*.parquet
orders    (200k rows)  ──►  (single federated query, no staging)      ──►  s3://warehouse/orders/YYYY-MM/*.parquet
...                                                                    ──►  Nessie catalogs metadata
```

The key insight: **Trino acts as a federation layer.** It reads from PostgreSQL (via JDBC) and writes to Iceberg (via the Nessie catalog + MinIO) in a single `INSERT INTO ... SELECT FROM` statement. No intermediate CSV files, no ETL staging tables, no proprietary migration tools.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| **Legacy Source** | PostgreSQL 15 | Widest SQL coverage; JDBC connector in Trino is battle-tested |
| **SQL Transpiler** | [sqlglot](https://github.com/tobymao/sqlglot) | Pure Python, 30+ dialects, parses and rewrites ASTs — not just regex |
| **Query Engine** | [Trino 480](https://trino.io) | Federated SQL over any catalog; reads Postgres + writes Iceberg in one query |
| **Table Format** | [Apache Iceberg](https://iceberg.apache.org) | Open standard; time-travel, schema evolution, partition pruning |
| **Iceberg Catalog** | [Project Nessie](https://projectnessie.org) | Git-like branching for tables — test migrations on a branch before merging |
| **Object Storage** | [MinIO](https://min.io) | S3-compatible, single binary, runs on any hardware |
| **Monitoring** | Prometheus + Grafana | OSS; Trino exposes JMX metrics; MinIO has a native Prometheus endpoint |
| **Orchestration** | Plain Python + Click | No Airflow/Prefect overhead; readable, auditable, zero extra services |
| **Deployment** | Docker Compose | One `make up` starts all 7 services; portable to any infrastructure |

---

## Architecture Deep-Dive & Tradeoffs

### Stage 1: Legacy Source — PostgreSQL

**Why PostgreSQL as the "legacy" stand-in?**

PostgreSQL is the world's most widely deployed open-source RDBMS and supports nearly every construct found in proprietary databases: SERIAL sequences, JSONB, arrays, window functions, CTEs, and TIMESTAMPTZ. It makes an excellent proxy for Oracle/SQL Server when demonstrating migration concepts.

**Tradeoff: PostgreSQL JDBC vs pg_dump**

| Approach | Pros | Cons |
|----------|------|------|
| **Trino JDBC (this project)** | Zero staging, live data, federated queries | Puts load on the source DB; limited by JDBC fetch size |
| **pg_dump → Parquet** | Doesn't touch live DB; faster for huge tables | Requires staging storage; two-step process |
| **Logical replication (CDC)** | Near-realtime, low impact | Complex setup (Debezium, Kafka); overkill for one-time migrations |

For one-time or low-frequency batch migrations, the JDBC approach is simpler and sufficient. For continuous sync, add Debezium + Kafka on top.

---

### Stage 2: SQL Transpilation — sqlglot

**What sqlglot does:**

sqlglot parses SQL into an AST (Abstract Syntax Tree) and regenerates it in the target dialect. This means it handles:
- `::integer` → `CAST(x AS INTEGER)` (PostgreSQL cast syntax)
- `NOW()` → `current_timestamp` (function name differences)
- `INTERVAL '30 days'` → Trino-compatible interval expressions
- Oracle `NVL()` → `COALESCE()`, `DECODE()` → `CASE WHEN`, `ROWNUM` → `LIMIT`

**What it doesn't handle (and we patch):**

| PostgreSQL Type | sqlglot result | Our patch |
|-----------------|----------------|-----------|
| `SERIAL` | `INT` | Map to `INTEGER`, strip auto-increment constraint |
| `TIMESTAMPTZ` | `TIMESTAMPTZ` | Map to `TIMESTAMP(6) WITH TIME ZONE` |
| `JSONB` | `JSONB` | Map to `VARCHAR` (no Iceberg JSON type) |
| `BYTEA` | `BLOB` | Map to `VARBINARY` |
| `MONEY` | left as-is | Map to `DECIMAL(19,4)` |

**Tradeoff: AST-based vs regex-based transpilation**

Regex-based translators fail on edge cases (nested quotes, CTEs, subqueries). AST-based tools like sqlglot parse the full grammar and rewrite nodes correctly, at the cost of slightly higher complexity. For production migrations, AST-based is the only correct approach.

---

### Stage 3: Iceberg Catalog — Project Nessie vs Hive Metastore

**Hive Metastore (HMS)** is the traditional choice but requires a running database, a Thrift server, and HDFS-style naming conventions. It has no branching, no multi-table transactions, and complex upgrade paths.

**Project Nessie** reimplements the Iceberg catalog spec with a Git-like model:

```
main branch    ──────────────────────────────────────►
                     │                 ▲
migration-test ──────►  test schema    │ merge if valid
                         evolution     │
```

- Create a branch: `nessie --endpoint http://localhost:19120/api/v2 create-branch migration-v2`
- Run migration on the branch
- Validate data quality
- Merge to `main` atomically — all tables updated in one commit

**For local dev** this project uses `NESSIE_VERSION_STORE_TYPE=IN_MEMORY` (zero dependencies). For production, switch to `JDBC` (backed by PostgreSQL) or `BIGTABLE` for massive scale.

**Tradeoff: Nessie vs AWS Glue REST Catalog**

| | Nessie | Glue REST Catalog |
|-|--------|-------------------|
| Branching | Yes (Git-like) | No |
| Cloud-native | Self-hosted | AWS-native |
| Local dev | Single container | Requires AWS credentials |
| Cost | Free | AWS pricing |

---

### Stage 4: Object Storage — MinIO

MinIO is byte-for-byte S3-compatible. The exact same Iceberg config that reads `s3://warehouse` on MinIO will work against AWS S3, GCS, or Azure ADLS with only an endpoint/credential change.

**Tradeoff: MinIO vs direct filesystem (local Iceberg)**

| | MinIO | Local filesystem |
|-|-------|------------------|
| S3-compatible | Yes | No |
| Multi-node scale-out | Yes | No |
| Parquet file visibility | Web console at :9001 | `ls` |
| Production path | Swap endpoint for S3 | Must rewrite |

MinIO ensures the storage layer is truly swappable without code changes.

---

### Stage 5: Query Engine — Trino

Trino's **federated query model** is what makes zero-copy migration possible. A single SQL statement can join tables from different catalogs:

```sql
-- This runs entirely inside Trino — no data exported, no staging files
INSERT INTO iceberg.warehouse.orders
SELECT * FROM postgres.public.orders

-- Cross-catalog join (legacy + lakehouse in one query):
SELECT c.tier, COUNT(o.id), SUM(t.amount)
FROM postgres.public.customers c
JOIN iceberg.warehouse.orders   o ON o.customer_id = c.id
JOIN iceberg.warehouse.transactions t ON t.order_id = o.id
WHERE t.status = 'success'
GROUP BY c.tier
```

**Tradeoff: Trino vs Apache Spark for migration**

| | Trino | Spark |
|-|-------|-------|
| Startup time | Seconds | Minutes (JVM warm-up) |
| SQL standard | ANSI SQL 2011 | SparkSQL (custom extensions) |
| Streaming CDC | No | Yes (Structured Streaming) |
| Interactive queries | Excellent (MPP) | Slower (batch-optimised) |
| Memory management | Spill-to-disk | Spill-to-disk |
| Deployment complexity | Lower | Higher |

For **one-time or scheduled batch migrations**, Trino is simpler and faster to operate. For streaming CDC, add Spark or Flink on top.

---

### Stage 6: Monitoring & FinOps

**Why FinOps monitoring matters for migrations:**

A migration that runs for 10 hours consuming 32 cores is not "free" even on-premises — it displaces other workloads and consumes energy. The FinOps dashboard answers:

- Which tables cost the most compute to migrate?
- What is the data transfer rate? Is MinIO a bottleneck?
- Are there query failures that indicate type mapping problems?
- What is the CPU-second cost proxy vs rows delivered (cost-to-value ratio)?

**Metrics exposed:**
- `migration_rows_inserted_total{table_name}` — rows written to Iceberg
- `migration_table_duration_seconds{table_name}` — wall-clock time per table
- `migration_errors_total` — failed migrations
- `migration_tables_validated_ok_total` — tables passing post-migration checks
- MinIO: `minio_cluster_capacity_usable_total_bytes`, `minio_s3_requests_total`

---

## Quick Start

**Prerequisites:** Docker, Docker Compose v2, Python 3.11+

```bash
# 1. Clone and enter the project
git clone <repo> && cd Legacy2LakehouseMigrationEngine

# 2. Copy environment file
cp .env.example .env

# 3. Start all 7 services (Postgres, MinIO, Nessie, Trino, Prometheus, Grafana)
make up

# 4. Wait for all services to be healthy (~2 minutes first time)
make wait

# 5. Install Python dependencies
make install

# 6. Verify connectivity
make status

# 7. Run the full migration pipeline
make migrate

# 8. Validate: compare row counts and checksums between source and target
make validate
```

### Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Trino Web UI | http://localhost:8080 | any username |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| Grafana FinOps | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Nessie API | http://localhost:19120/api/v2/config | — |

### Verify the migration in Trino

Open http://localhost:8080, choose **Query Editor**, and run:

```sql
-- Row count parity
SELECT 'customers' AS tbl,
  (SELECT COUNT(*) FROM postgres.public.customers) AS pg_rows,
  (SELECT COUNT(*) FROM iceberg.warehouse.customers) AS iceberg_rows;

-- Federated join: legacy source + migrated lakehouse in one query
SELECT c.tier, COUNT(o.id) AS orders, ROUND(SUM(t.amount), 2) AS revenue
FROM postgres.public.customers     c
JOIN iceberg.warehouse.orders       o  ON o.customer_id = c.id
JOIN iceberg.warehouse.transactions t  ON t.order_id    = o.id
WHERE t.status = 'success'
GROUP BY c.tier
ORDER BY revenue DESC;
```

### Run unit tests (no Docker required)

```bash
make test-unit
```

### Transpile Oracle SQL

```bash
python examples/transpile_only.py
```

---

## Project Structure

```
.
├── docker-compose.yml           # 7-service stack
├── Makefile                     # make up / migrate / validate / test
├── .env.example                 # Copy to .env and customise
│
├── config/
│   ├── trino/catalog/           # PostgreSQL + Iceberg connector properties
│   ├── prometheus/              # Prometheus scrape config
│   └── grafana/provisioning/    # Auto-provisioned datasource + FinOps dashboard
│
├── sql/
│   ├── postgres/                # Schema DDL + seed data (755k rows total)
│   └── trino/                   # Iceberg CREATE TABLE + validation queries
│
├── src/
│   ├── cli.py                   # Click CLI (discover/transpile/migrate/validate)
│   ├── config.py                # Pydantic settings from .env
│   ├── connectors/              # PostgreSQL (psycopg2) + Trino connectors
│   ├── transpiler/              # sqlglot engine + type mapping
│   ├── pipeline/                # discover → migrate → validate orchestration
│   └── metrics/                 # Prometheus counters/gauges
│
├── tests/
│   ├── unit/                    # 70+ transpiler and type-map tests (no Docker)
│   └── integration/             # End-to-end tests (requires stack)
│
└── examples/
    ├── transpile_only.py        # Standalone SQL transpilation demo
    └── incremental_migration.py # CDC-style incremental sync pattern
```

---

## Extending to Oracle

Change one setting in `.env`:

```bash
SOURCE_SCHEMA=your_schema
```

And pass `--source oracle` to the CLI:

```bash
python -m src.cli transpile legacy_procedures.sql --source oracle
```

The `SqlTranspiler` supports these source dialects via sqlglot:
`postgres`, `oracle`, `mysql`, `tsql` (SQL Server)

---

## FinOps Dashboard Walkthrough

After running `make migrate`, open Grafana at http://localhost:3000 → **Migration Engine** → **Legacy-to-Lakehouse FinOps Dashboard**.

| Panel | What it shows |
|-------|---------------|
| Tables Migrated | Count of completed table migrations |
| Rows Migrated | Total rows inserted into Iceberg |
| Data Transferred | Bytes written to MinIO |
| Migration Errors | Red if any table failed |
| Rows Migrated Over Time | Throughput time series (rows/sec) |
| Data Transfer Rate | MinIO write bandwidth |
| Rows per Table | Bar chart — identifies large tables |
| Duration per Table | Bar chart — identifies slow tables |
| Validation Pass Rate | Gauge — % of tables passing checksum |
| Estimated Compute Cost | CPU-sec consumed (cost proxy) |
| MinIO Storage Used | Total object store capacity |

---

## Production Considerations

| Concern | Recommendation |
|---------|----------------|
| **Large tables (>500M rows)** | Add `--batch-size` chunking and partition-level extraction |
| **Schema changes during migration** | Use Nessie branches; validate on branch before merging to `main` |
| **Network bandwidth** | Run Trino co-located with source DB or use `pg_dump` + parallel Parquet write |
| **Continuous sync** | Add Debezium (CDC) → Kafka → Trino streaming ingest |
| **Nessie persistence** | Switch `NESSIE_VERSION_STORE_TYPE=JDBC` in docker-compose.yml |
| **MinIO HA** | Replace with AWS S3, GCS, or MinIO distributed mode |
| **Trino HA** | Add worker nodes; use Trino on Kubernetes |
| **Security** | Add Trino LDAP auth, MinIO IAM policies, TLS on all endpoints |

---

## License

Apache 2.0 — see LICENSE file.
