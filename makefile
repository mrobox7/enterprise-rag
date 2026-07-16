.PHONY: install dev lint format check

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload

lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run basedpyright