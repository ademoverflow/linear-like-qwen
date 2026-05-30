# ==============================================================================
# Ademoverflow Template - Development Makefile
# ==============================================================================
#
# Single entry point for all common development operations.
# Run `make` or `make help` to see available targets.
#

.DEFAULT_GOAL := help

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

COMPOSE := docker compose
CORE_CONTAINER := core
WEBAPP_CONTAINER := webapp
DB_CONTAINER := db

ALEMBIC := alembic -c core/src/core/alembic/alembic.ini

# ==============================================================================
# Help
# ==============================================================================

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "Ademoverflow Template - Development Commands"
	@echo "============================================="
	@awk 'BEGIN {FS = ":.*?## "} \
		/^# =+$$/ {next} \
		/^## / {printf "\n\033[1m%s\033[0m\n", substr($$0, 4); next} \
		/^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)
	@echo ""

# ==============================================================================
## Install
# ==============================================================================

.PHONY: install install-python install-js

install: install-python install-js ## Install all dependencies (Python + JS)

install-python: ## Install Python dependencies (UV)
	uv sync --all-packages

install-js: ## Install JS dependencies (pnpm)
	pnpm install

# ==============================================================================
## Docker
# ==============================================================================

.PHONY: up down build rebuild restart ps logs logs-core logs-webapp logs-db

up: ## Start all services in detached mode
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

build: ## Build all Docker images
	$(COMPOSE) build

rebuild: ## Rebuild and restart all services (no cache)
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

restart: ## Restart all services
	$(COMPOSE) restart

ps: ## Show running containers and their status
	$(COMPOSE) ps

logs: ## Tail logs for all services
	$(COMPOSE) logs -f

logs-core: ## Tail logs for the core (API) service
	$(COMPOSE) logs -f $(CORE_CONTAINER)

logs-webapp: ## Tail logs for the webapp service
	$(COMPOSE) logs -f $(WEBAPP_CONTAINER)

logs-db: ## Tail logs for the database service
	$(COMPOSE) logs -f $(DB_CONTAINER)

# ==============================================================================
## Code Quality - Python
# ==============================================================================

.PHONY: check-python check-format check-lint check-sort type-check fix-format fix-sort

check-python: check-format check-lint check-sort type-check ## Run all Python checks (format, lint, sort, types)

check-format: ## Check Python code formatting (ruff)
	uv run ruff format --check

check-lint: ## Check Python code linting (ruff)
	uv run ruff check

check-sort: ## Check Python import sorting (ruff)
	uv run ruff check --select I

type-check: ## Run Python type checking (mypy)
	uv run mypy core

fix-format: ## Fix Python code formatting (ruff)
	uv run ruff format

fix-sort: ## Fix Python import sorting (ruff)
	uv run ruff check --select I --fix

# ==============================================================================
## Code Quality - JavaScript
# ==============================================================================

.PHONY: check-webapp lint-webapp format-webapp

check-webapp: ## Run all webapp checks (Biome)
	pnpm --filter webapp run check

lint-webapp: ## Run webapp linting (Biome)
	pnpm --filter webapp run lint

format-webapp: ## Run webapp formatting (Biome)
	pnpm --filter webapp run format

# ==============================================================================
## Code Quality - All
# ==============================================================================

.PHONY: check fix

check: check-python check-webapp ## Run all code quality checks (Python + webapp)

fix: fix-format fix-sort ## Fix all auto-fixable Python issues

# ==============================================================================
## Database
# ==============================================================================

.PHONY: db-migrate db-upgrade db-downgrade db-history db-current db-shell

db-migrate: ## Create a new migration (usage: make db-migrate MSG="description")
ifndef MSG
	$(error MSG is required. Usage: make db-migrate MSG="add user table")
endif
	$(COMPOSE) exec $(CORE_CONTAINER) bash -c '$(ALEMBIC) revision --autogenerate -m "$(MSG)"'

db-upgrade: ## Apply all pending migrations
	$(COMPOSE) exec $(CORE_CONTAINER) bash -c '$(ALEMBIC) upgrade head'

db-downgrade: ## Revert the last migration
	$(COMPOSE) exec $(CORE_CONTAINER) bash -c '$(ALEMBIC) downgrade -1'

db-history: ## Show migration history
	$(COMPOSE) exec $(CORE_CONTAINER) bash -c '$(ALEMBIC) history --verbose'

db-current: ## Show current migration revision
	$(COMPOSE) exec $(CORE_CONTAINER) bash -c '$(ALEMBIC) current'

db-shell: ## Open a psql shell to the database
	$(COMPOSE) exec $(DB_CONTAINER) psql -U admin -d db

# ==============================================================================
## Testing
# ==============================================================================

.PHONY: test-core test-webapp

test-core: ## Run core tests (pytest)
	$(COMPOSE) exec $(CORE_CONTAINER) bash -c 'uv run pytest core/tests -v'

test-webapp: ## Run webapp tests (vitest)
	pnpm --filter webapp run test

# ==============================================================================
## Shell Access
# ==============================================================================

.PHONY: shell-core shell-webapp shell-db

shell-core: ## Open a bash shell in the core container
	$(COMPOSE) exec $(CORE_CONTAINER) bash

shell-webapp: ## Open a shell in the webapp container
	$(COMPOSE) exec $(WEBAPP_CONTAINER) sh

shell-db: ## Open a bash shell in the database container
	$(COMPOSE) exec $(DB_CONTAINER) bash

# ==============================================================================
## Utilities
# ==============================================================================

.PHONY: clean ip update-ip

clean: ## Remove Python caches, build artifacts, and node_modules
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage dist
	pnpm run clean

ip: ## Show local IP address and service URLs
	@IP=$$(ipconfig getifaddr $$(route -n get default 2>/dev/null | awk '/interface:/ {print $$2}')) && \
	echo "Local IP: $$IP" && \
	echo "" && \
	echo "Service URLs:" && \
	echo "  API:     http://$$IP:8999" && \
	echo "  Webapp:  http://$$IP:8998" && \
	echo "  Adminer: http://$$IP:8997"

update-ip: ## Update .env with current local network IP
	@IP=$$(ipconfig getifaddr $$(route -n get default 2>/dev/null | awk '/interface:/ {print $$2}')) && \
	sed -i '' "s|^WEBAPP_URL=.*|WEBAPP_URL=http://$$IP:8998|" .env && \
	sed -i '' "s|^COOKIE_DOMAIN=.*|COOKIE_DOMAIN=$$IP|" .env && \
	echo "Updated .env with IP: $$IP"
