#!/usr/bin/env bash
# Wait for all Docker Compose services to become healthy before running the migration.
# Usage: ./scripts/wait-for-services.sh [timeout_seconds]
set -euo pipefail

TIMEOUT=${1:-300}
ELAPSED=0
INTERVAL=5

echo "Waiting for services to be healthy (timeout: ${TIMEOUT}s)..."

wait_for() {
    local name="$1"
    local url="$2"
    local max="${3:-$TIMEOUT}"
    local elapsed=0
    printf "  %-20s " "$name"
    until curl -sf "$url" >/dev/null 2>&1; do
        sleep $INTERVAL
        elapsed=$((elapsed + INTERVAL))
        if [ $elapsed -ge $max ]; then
            echo "TIMEOUT"
            return 1
        fi
        printf "."
    done
    echo " OK"
}

wait_for "PostgreSQL"  "http://localhost:5432"     || \
    until pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; do
        sleep $INTERVAL; ELAPSED=$((ELAPSED+INTERVAL))
        [ $ELAPSED -ge $TIMEOUT ] && echo "PostgreSQL timeout" && exit 1
    done && echo "  PostgreSQL           OK"

wait_for "MinIO"       "http://localhost:9000/minio/health/live"
wait_for "Nessie"      "http://localhost:19120/api/v2/config"
wait_for "Trino"       "http://localhost:8080/v1/info"
wait_for "Prometheus"  "http://localhost:9090/-/healthy"
wait_for "Grafana"     "http://localhost:3000/api/health"

echo ""
echo "All services ready."
