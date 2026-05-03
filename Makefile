.DEFAULT_GOAL := help
COMPOSE       := docker compose
PYTHON        := python3

.PHONY: help up down wait logs ps migrate validate transpile discover test test-unit test-int install clean reset

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\n\033[1mUsage:\033[0m\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ── Infrastructure ─────────────────────────────────────────────────────────────

up: ## Start all services (PostgreSQL, MinIO, Nessie, Trino, Prometheus, Grafana)
	$(COMPOSE) up -d
	@echo ""
	@echo "Services starting... run 'make wait' to wait for readiness."
	@echo ""
	@echo "  Trino UI:       http://localhost:8080"
	@echo "  MinIO Console:  http://localhost:9001  (minioadmin / minioadmin)"
	@echo "  Grafana:        http://localhost:3000  (admin / admin)"
	@echo "  Prometheus:     http://localhost:9090"
	@echo "  Nessie:         http://localhost:19120"

down: ## Stop and remove all containers and volumes
	$(COMPOSE) down -v

wait: ## Wait for all services to report healthy
	@bash scripts/wait-for-services.sh

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Tail logs from all containers
	$(COMPOSE) logs -f

logs-trino: ## Tail Trino logs only
	$(COMPOSE) logs -f trino

# ── Migration workflow ─────────────────────────────────────────────────────────

discover: ## Introspect and print the source schema summary
	$(PYTHON) -m src.cli discover

migrate: ## Run the full migration pipeline (Postgres → Iceberg)
	$(PYTHON) -m src.cli migrate

validate: ## Post-migration row-count and checksum validation
	$(PYTHON) -m src.cli validate

transpile: ## Transpile a SQL file (usage: make transpile FILE=path/to/query.sql)
	$(PYTHON) -m src.cli transpile $(FILE)

status: ## Check connectivity to all services
	$(PYTHON) -m src.cli status

# ── Quick workflow (up → wait → migrate → validate) ───────────────────────────

run-all: up wait migrate validate ## Full end-to-end: start stack, wait, migrate, validate

# ── Examples ───────────────────────────────────────────────────────────────────

demo-transpile: ## Run the transpilation demo (no Docker required)
	$(PYTHON) examples/transpile_only.py

# ── Python dev ─────────────────────────────────────────────────────────────────

install: ## Install Python dependencies into a virtualenv
	$(PYTHON) -m venv .venv && \
	.venv/bin/pip install --upgrade pip && \
	.venv/bin/pip install -e ".[dev]"

test: test-unit ## Run all tests (unit by default; use test-int for integration)

test-unit: ## Run unit tests (no Docker required)
	$(PYTHON) -m pytest tests/unit -v

test-int: ## Run integration tests (requires 'make up && make wait')
	RUN_INTEGRATION_TESTS=1 $(PYTHON) -m pytest tests/integration -v -m integration

lint: ## Lint Python code with ruff and black
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m black --check src tests

format: ## Auto-format Python code
	$(PYTHON) -m black src tests examples

# ── Maintenance ────────────────────────────────────────────────────────────────

clean: ## Remove Python cache and build artefacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache dist build *.egg-info

reset: down up wait ## Full reset: tear down, restart, and wait for readiness
