.PHONY: help install install-dev lint format test test-all test-integration typecheck run-cli run-ui ui api serve docker-build docker-run clean

# -----------------------------------------------------------------------------
# Meta
# -----------------------------------------------------------------------------

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		sed 's/##/  /' | \
		while read -r cmd desc; do \
			printf "%-15s %s\n" "$$cmd" "$$desc"; \
		done

# -----------------------------------------------------------------------------
# Install
# -----------------------------------------------------------------------------

install:  ## Install dependencies
	uv sync

install-dev:  ## Install dependencies including dev tools
	uv sync

# -----------------------------------------------------------------------------
# Code quality
# -----------------------------------------------------------------------------

lint:  ## Auto-fix and check lint issues
	uv run ruff check src/ tests/ --fix

format:  ## Format code with ruff
	uv run ruff format src/ tests/

typecheck:  ## Run pyright type checker
	uv run pyright src/ tests/

# -----------------------------------------------------------------------------
# Test
# -----------------------------------------------------------------------------

test:  ## Run unit tests (fast, no Radicale)
	uv run pytest -v -m "not integration"

test-all:  ## Run all tests including integration
	uv run pytest -v

test-integration:  ## Run integration tests only
	uv run pytest -v -m integration

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------

run-cli:  ## Run the CLI app
	uv run gac

ui:  ## Start the Streamlit UI for the default user (GAC_UI_HOST/GAC_UI_PORT, default 0.0.0.0:3001)
	uv run gac-ui

run-ui: ui  ## Deprecated alias for `make ui`

api:  ## Start the FastAPI server for the default user (GAC_API_HOST/GAC_API_PORT, default 0.0.0.0:8766)
	uv run gac-api

# Run UI and API together. Uses Make's parallel-job mechanism
# (``-j 2``) so GNU Make itself handles signal propagation: when
# Ctrl+C arrives at the parent make, it forwards SIGTERM/SIGINT to
# every child process it spawned and waits for them to exit. This
# is the same pattern genesis-scaffolding/Makefile uses for its
# ``dev`` target and avoids any custom trap logic in the recipe.
serve:  ## Start UI and API together (Ctrl+C to stop both)
	@echo "Starting UI on $${GAC_UI_PORT:-3001} and API on $${GAC_API_PORT:-8766} (Ctrl+C to stop both)..."
	@$(MAKE) -j 2 ui api

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------

docker-build:  ## Build the container image locally
	docker build -t genesis-agent-context:local .

docker-run:  ## Run the container locally on :3001 (UI) and :8766 (API)
	docker run --rm -p 3001:3001 -p 8766:8766 \
		-e PUID=$$(id -u) -e PGID=$$(id -g) \
		-v $$(pwd)/.docker-data/config:/home/gac/.config \
		-v $$(pwd)/.docker-data/data:/home/gac/.local/share \
		-v $$(pwd)/.docker-data/state:/home/gac/.local/state \
		-v $$(pwd)/.docker-data/cache:/home/gac/.cache \
		genesis-agent-context:local

# -----------------------------------------------------------------------------
# Utility
# -----------------------------------------------------------------------------

clean:  ## Remove cached files and venv
	uv clean
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
