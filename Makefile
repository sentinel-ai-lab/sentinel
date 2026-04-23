# =============================================================
# Sentinel — Makefile
# =============================================================

.PHONY: help up down ps logs lint typecheck test ingest clean

COMPOSE_FILE := infra/docker-compose.dev.yml
ENV_FILE     := infra/.env

# Default target
help:
	@echo ""
	@echo "  Sentinel — Available Commands"
	@echo "  ─────────────────────────────────────────────"
	@echo "  make up              Boot the full local stack"
	@echo "  make down            Stop all services"
	@echo "  make ps              Check service health"
	@echo "  make logs            Tail all service logs"
	@echo "  make logs S=postgres Tail a specific service"
	@echo "  make lint            Run ruff check + format"
	@echo "  make typecheck       Run mypy"
	@echo "  make test            Run pytest with coverage"
	@echo "  make ingest T=TCS    Ingest a ticker (e.g. TCS)"
	@echo "  make clean           Remove all volumes (fresh start)"
	@echo "  ─────────────────────────────────────────────"
	@echo ""

# -----------------------------------------------------------
# Docker stack
# -----------------------------------------------------------
up:
	@echo "🚀 Starting Sentinel dev stack..."
	@[ -f $(ENV_FILE) ] || (echo "❌ infra/.env not found. Run: cp infra/.env.example infra/.env" && exit 1)
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d
	@echo "✅ Stack is up."
	@echo "   Postgres  → localhost:5432"
	@echo "   Redis     → localhost:6379"
	@echo "   Langfuse  → http://localhost:3000"

down:
	@echo "🛑 Stopping Sentinel dev stack..."
	docker compose -f $(COMPOSE_FILE) down
	@echo "✅ Stack stopped."

ps:
	docker compose -f $(COMPOSE_FILE) ps

logs:
ifdef S
	docker compose -f $(COMPOSE_FILE) logs -f $(S)
else
	docker compose -f $(COMPOSE_FILE) logs -f
endif

clean:
	@echo "⚠️  This will delete all local data volumes."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker compose -f $(COMPOSE_FILE) down -v
	@echo "✅ Volumes removed."

# -----------------------------------------------------------
# Code quality
# -----------------------------------------------------------
lint:
	@echo "🔍 Running ruff..."
	uv run ruff check .
	uv run ruff format --check .
	@echo "✅ Lint passed."

lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	@echo "🔍 Running mypy..."
	uv run mypy packages/ apps/ scripts/
	@echo "✅ Typecheck passed."

# -----------------------------------------------------------
# Tests
# -----------------------------------------------------------
test:
	@echo "🧪 Running tests..."
	uv run pytest -v --cov=packages --cov-report=term-missing
	@echo "✅ Tests passed."

test-fast:
	uv run pytest -v -x --ignore=tests/integration

# -----------------------------------------------------------
# Ingestion
# -----------------------------------------------------------
ingest:
ifndef T
	$(error Usage: make ingest T=TCS)
endif
	@echo "📥 Ingesting $(T)..."
	uv run python scripts/ingest.py $(T)
