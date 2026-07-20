.PHONY: install dev ui lint format check ingest

DIR ?= data

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload

ui:
	uv run streamlit run ui/app.py

lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run basedpyright

ingest:
	uv run python -m app.ingestion.processor -d $(DIR) $(ARGS)