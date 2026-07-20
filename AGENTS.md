# AGENTS.md

This file provides guidance to AI coding agents working with code in this repository.

## Commands

Package manager is `uv` — never use bare `pip`/`python`. All commands go through the `makefile`:

```bash
make install   # uv sync
make dev       # uv run uvicorn app.main:app --reload   (FastAPI backend, http://localhost:8000)
make ui        # uv run streamlit run ui/app.py           (chat UI, calls the backend over HTTP)
make lint      # uv run ruff check .
make format    # uv run ruff format .
make check     # uv run basedpyright
make ingest DIR=data ARGS="--wipe --recursive --prune"   # run the ingestion CLI
```

`make ingest` invokes `app/ingestion/processor.py` directly; useful flags (`-d/--directory`, `-s/--source-type`, `-r/--recursive`, `--wipe`, `--prune`) are defined there via argparse.

There is no test suite yet — `tests/` is an empty placeholder. `app/api/` and `app/services/` are also empty scaffold directories not currently wired into anything.

Pre-commit (`.pre-commit-config.yaml`) runs `ruff check --fix`, `ruff format`, and `basedpyright` on every commit — the same checks as `make lint`/`make format`/`make check`. `pyproject.toml` carries one ruff exception: `app/main.py` is allowed `E402` because `configure_logging()` must execute before the rest of its imports (see below).

Config (Gemini/Groq/Qdrant keys, URLs) comes from `.env` (see `.env.example` for required keys) via `app/config/settings.py`.

## Architecture

Two independent pipelines share the same Qdrant vector store and Gemini embedder, but never call each other directly:

1. **Ingestion** (offline, CLI-driven via `app/ingestion/processor.py`) — populates Qdrant.
2. **Agent graph** (online, served by FastAPI) — answers queries by reading from Qdrant.

### Ingestion pipeline

`IngestionPipeline` (`app/ingestion/pipeline.py`) wires four stages in sequence: `Loader` → `Splitter` → `Embedder` → `QdrantVectorStore`. `Loader` dispatches on file extension (pdf/txt/docx/html/md/ppt) to the matching LangChain loader. Each chunk's `source` metadata (the file path) is set unconditionally, even when `extra_metadata` is supplied, so it can never be overwritten — it's the join key used everywhere else.

`processor.py` orchestrates this per-directory:
- `IngestionManifest` records a content hash per file in a Qdrant collection (`{collection}__manifest`), so re-running ingestion skips files whose hash hasn't changed. This is what makes ingestion idempotent/incremental.
- Every file is re-ingested by first calling `delete_by_source` (removes old points for that file) then re-embedding — so a shrunk or emptied file doesn't leave orphaned vectors behind.
- If the input directory has sub-folders, each sub-folder's name is used as the `source_type` tag (e.g. `data/true/`, `data/noisy/`) unless `-s` overrides it explicitly.
- `--wipe` drops both the content collection and its manifest collection together — dropping one without the other would make every file look "unchanged" forever even though its vectors are gone.
- `--prune` removes vectors/manifest entries for files no longer on disk, but only makes sense when `--directory` covers the *entire* corpus for that collection — a partial/scoped run would incorrectly prune everything outside it.
- Failures are per-file: `process_file` never raises, returning `"failed"` instead, so one bad document can't abort a whole directory batch.

### Agent graph

`app/agents/graph.py` builds a LangGraph `StateGraph` over `AgentState` (`app/agents/state.py`) with three nodes:

`planner` → (conditional) → `retriever` → `responder` → `END`, or `planner` → `responder` → `END` directly.

- **`planner_node`** (`app/agents/nodes/planner.py`) asks a Groq LLM to classify the latest message against the full conversation history as either `CONVERSATIONAL` (greetings, or answerable purely from history) or a refined technical search query. This decision is what `route_planner` in `graph.py` branches on — the retriever is skipped entirely for conversational turns.
- **`retrieve_node`** (`app/agents/nodes/retriever.py`) embeds the query, pulls `settings.retrieval_candidate_k` candidates from Qdrant, then reranks them down to `settings.rerank_top_n` with `Reranker` (`app/retrieval/ranking.py`) before formatting them into `state.documents`.
- **`generate_node`** (`app/agents/nodes/responder.py`) synthesizes the final answer with a second Groq call, using either conversation history alone (`CONVERSATIONAL` path) or the retrieved context plus history (technical path, capped at `max_context_chars` to stay under Groq TPM limits).

The graph has no checkpointer/memory yet — every `/query` call starts from a blank `AgentState`; conversation continuity depends entirely on the caller resending prior `messages`.

### Reranking

`Reranker` (`app/retrieval/ranking.py`) wraps FlashRank's local ONNX cross-encoder. It reads its model name straight from `settings.reranker_model` rather than taking it as a constructor argument — there's a single process-wide instance (`retriever.py` module scope), so there's no need to thread config through call sites. The underlying `Ranker` is lazily constructed on first use and falls back to FlashRank's own default model if construction with the configured model fails.

### FastAPI app

`app/main.py` calls `configure_logging()` (Logfire) as the very first statement, *before* importing `app.agents.graph` and friends — several modules construct process-wide singletons at import time (`embedder = Embedder()`, `vectorstore = QdrantVectorStore()`, `reranker = Reranker()` in `retriever.py`) that emit Logfire spans during `__init__`, so logging has to be live before those imports run. This is intentional, not an oversight — don't "fix" the import order.

Routes: `GET /` (health), `GET /graph` (renders the compiled LangGraph as a Mermaid PNG via `rag_agent.get_graph().draw_mermaid_png()`), `POST /query` (builds an `AgentState` from the request and invokes `rag_agent`).

### Streamlit UI

`ui/app.py` is a separate process from the backend — it never imports the agent graph, only calls `POST {settings.backend_url}/query` over HTTP and renders `QueryResponse` (`app/models/query.py`). Run backend and UI as two separate `make` targets (`make dev` + `make ui`).

### Settings

`app/config/settings.py` defines a single `Settings` (pydantic-settings) instance, cached via `lru_cache` and exported as the module-level `settings` singleton — imported directly (`from app.config.settings import settings`) rather than passed around. Env values come from `.env`; unknown keys are ignored (`extra="ignore"`).
