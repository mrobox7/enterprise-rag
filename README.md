# Enterprise RAG

A production-grade agentic RAG assistant for a technical domain (Kubernetes, Intel hardware, and enterprise networking by default). A LangGraph agent retrieves from a Qdrant vector store and answers with Groq, behind a guardrails gate, with an offline ingestion pipeline and a RAGAS-based evaluation harness to measure answer quality.

## Architecture

Two independent pipelines share the same Qdrant vector store and Gemini embedder, but never call each other directly:

- **Ingestion** (offline, CLI-driven) — loads documents, chunks them, embeds them, and upserts into Qdrant. Idempotent and incremental via a content-hash manifest.
- **Agent graph** (online, served by FastAPI) — a LangGraph `planner → retriever → responder` flow. The planner classifies each turn as conversational or a technical query and routes accordingly; the retriever embeds the query, pulls candidates from Qdrant, and reranks them with a local cross-encoder; the responder synthesizes the final answer from retrieved context and conversation history.

Every request first passes through a NeMo Guardrails gate (jailbreak/prompt-injection/off-topic protection) before reaching the graph. A Streamlit UI talks to the FastAPI backend over HTTP, the same way the eval harness does.

See [AGENTS.md](AGENTS.md) for the full architectural breakdown (module-by-module).

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency management — never use bare `pip`/`python`
- A [Qdrant](https://qdrant.tech/) instance (Qdrant Cloud or self-hosted)
- API keys: [Groq](https://console.groq.com/) (LLM) and [Google Gemini](https://ai.google.dev/) (embeddings)

## Setup

```bash
git clone <this-repo>
cd enterprise-rag
make install          # uv sync
cp .env.example .env  # fill in your keys/URLs below
```

### Configuration (`.env`)

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key, used for embeddings |
| `GROQ_API_KEY` | Groq API key, used for the LLM (planner/responder/guardrails) |
| `QDRANT_URL` | Qdrant instance URL |
| `QDRANT_API_KEY` | Qdrant API key (omit for a local/unauthenticated instance) |

Other tunables (embedding/LLM model names, retrieval `top_k`, reranking, collection name, project domain) have sane defaults in `app/config/settings.py` and can be overridden via `.env` as well.

## Usage

```bash
make dev     # start the FastAPI backend — http://localhost:8000
make ui      # start the Streamlit chat UI (run in a separate terminal, calls the backend over HTTP)
```

Ingest your own documents (pdf/txt/docx/html/md/ppt supported):

```bash
make ingest DIR=data ARGS="--wipe --recursive --prune"
```

Sub-folders under `DIR` are used as the `source_type` tag unless overridden with `-s`. See `app/ingestion/processor.py` for all flags.

### Other commands

| Command | Description |
|---|---|
| `make install` | Install dependencies (`uv sync`) |
| `make dev` | Run the FastAPI backend with reload |
| `make ui` | Run the Streamlit chat UI |
| `make ingest DIR=... ARGS=...` | Run the ingestion CLI |
| `make eval` | Run the RAGAS evaluation harness against the running backend |
| `make lint` | `ruff check .` |
| `make format` | `ruff format .` |
| `make check` | `basedpyright` type checking |

## Guardrails

Every `/query` request passes through a [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) gate (`app/guardrails/`) before it reaches the LangGraph agent — `guard()` either blocks the request and returns a canned response immediately, or lets it through unmodified. The gate itself runs on a small, fast Groq model (`llama-3.1-8b-instant`), separate from the responder model.

The ruleset is split into two layers, assembled in `rules.py`:

- **Core rules** (`core_rules.py`) — domain-independent protections: jailbreak attempts, system-prompt extraction, requests for sensitive data (credentials, PII, financial info), harmful-content requests, and abusive language. Not meant to be edited per-deployment — it's written to be reusable across projects.
- **Domain rules** (`domain_rules.py`) — deployment-specific scope: off-topic redirection, greetings, capability explanations, farewells, and gratitude, all templated on `settings.project_domain`. This is the layer to edit when re-scoping the assistant for a different subject area.

Both layers compile down to Colang flows plus a YAML config that restricts dialog matching to `embeddings_only` (similarity threshold `0.7`) — user input is matched against the example phrases in each `define user ...` block rather than requiring an exact string match. When a rail fires, `guard()` detects it by checking the response against `RAIL_INDICATORS` — a list of distinctive substrings from each canned `define bot ...` response. **Any time a bot response string changes, its matching entry in `RAIL_INDICATORS` has to change too**, or that rail's firing goes undetected.

To re-scope the assistant for a different domain, change `project_domain` in `.env` or `app/config/settings.py` and adjust the off-topic example phrases in `domain_rules.py` if domain-adjacent terms start causing false positives.

## Evaluation

`make eval` scores the live backend's answers against a hand-curated golden Q&A set (`app/evals/golden_dataset.py`) using [RAGAS](https://docs.ragas.io/) — faithfulness, answer relevancy, context precision, and context recall — with a Groq model as judge (deliberately different from the responder model, to draw from a separate quota) and Gemini for judge-side embeddings. Results are written to `eval_results.csv`.

Requires `make dev` running in another terminal, and the `eval` dependency group installed:

```bash
uv sync --group eval
```

Edit `app/evals/golden_dataset.py` with real questions/answers grounded in your own ingested corpus before running — the harness refuses to run against placeholder entries.

## Project layout

```
app/
├── agents/        # LangGraph agent: state, graph wiring, planner/retriever/responder nodes
├── config/        # Settings (pydantic-settings) and Logfire logging setup
├── evals/         # RAGAS evaluation harness and golden dataset
├── guardrails/    # NeMo Guardrails rules (domain-independent core + swappable domain layer)
├── ingestion/     # Offline ingestion pipeline: loader, splitter, manifest, CLI processor
├── models/        # Shared Pydantic request/response models
├── retrieval/     # Gemini embedder, FlashRank cross-encoder reranker
├── vectorstore/   # Qdrant client wrapper
└── main.py        # FastAPI app

ui/app.py          # Streamlit chat UI
```

## Status

There is no automated test suite yet (`tests/` is a placeholder). `app/api/` and `app/services/` are empty scaffolding not currently wired into anything.
