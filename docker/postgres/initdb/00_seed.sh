#!/bin/bash
# Runs on first container boot; loads SQL seed scripts in order.
set -e

PGUSER="${POSTGRES_USER:-postgres}"
PGDB="${POSTGRES_DB:-legacydb}"

echo "==> Loading schema..."
psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" -f /docker-entrypoint-initdb.d/../../../sql/postgres/01_schema.sql

echo "==> Seeding customers..."
psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" -f /docker-entrypoint-initdb.d/../../../sql/postgres/02_seed_customers.sql

echo "==> Seeding products..."
psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" -f /docker-entrypoint-initdb.d/../../../sql/postgres/03_seed_products.sql

echo "==> Seeding orders..."
psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" -f /docker-entrypoint-initdb.d/../../../sql/postgres/04_seed_orders.sql

echo "==> Seeding transactions..."
psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" -f /docker-entrypoint-initdb.d/../../../sql/postgres/05_seed_transactions.sql

echo "==> Seed complete."
