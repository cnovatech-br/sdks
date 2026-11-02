.DEFAULT_GOAL := help
PACKAGES := core datamarket-python
# Words that must not appear under core/src: the core knows no product.
PRODUCT_TERMS := ean|eans|market|pharma|datamarket|assortment|competitor|retailer

.PHONY: help install lint format boundary typecheck test cov check live build clean

help:  ## List the targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install:  ## Create the workspace virtualenv with every package and the dev tools
	uv sync --all-packages

lint:  ## ruff check and format check
	uv run ruff check .
	uv run ruff format --check .

format:  ## Apply ruff format and the fixes ruff knows are safe
	uv run ruff format .
	uv run ruff check --fix .

boundary:  ## Fail if the shared core mentions a product concept
	@if grep -rEinw --include='*.py' '$(PRODUCT_TERMS)' core/src; then \
		echo "core/src must stay product-agnostic"; exit 1; \
	fi

typecheck:  ## mypy --strict, one package at a time
	@for package in $(PACKAGES); do \
		echo "== $$package"; (cd $$package && uv run mypy) || exit 1; \
	done

test:  ## Offline test suite
	@for package in $(PACKAGES); do \
		echo "== $$package"; (cd $$package && uv run pytest) || exit 1; \
	done

cov:  ## Test suite with coverage; fails below each package's threshold
	@for package in $(PACKAGES); do \
		echo "== $$package"; (cd $$package && uv run pytest --cov --cov-report=term-missing) || exit 1; \
	done

check: lint boundary typecheck cov  ## Everything CI runs

live:  ## Smoke test against the real API; free endpoints only
	cd datamarket-python && uv run pytest tests/test_live.py --live

build:  ## Build sdist and wheel of every package into dist/
	uv build --package cnovatech-sdk-core
	uv build --package cnovatech-datamarket

clean:  ## Remove build output and tool caches
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find . -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.coverage' | xargs rm -rf
