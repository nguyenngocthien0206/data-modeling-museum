# Thin wrapper over the CLI. The CLI (`uv run museum ...`) is the real entry point.
SCALE ?= small

.PHONY: lint format test all

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

all:
	uv run museum all --scale $(SCALE)
