"""RAGAS evaluation harness.

Hits the running FastAPI backend's `/query` endpoint for each question in
`golden_dataset.py` (same path the Streamlit UI uses), then scores the
answers with RAGAS. The judge LLM is Groq's `settings.eval_judge_model`
(a small model, deliberately different from the responder's `llm_model`):
Groq tracks token quota per model, so judging draws from its own daily
budget instead of competing with the responder's for the same one. Gemini
was tried first but its free tier doesn't have the request headroom for it.

Runs all 4 standard metrics (Faithfulness, AnswerRelevancy, ContextPrecision,
ContextRecall). Faithfulness and ContextPrecision are the expensive ones —
see the comment above the `evaluate()` call — so this only stays within a
free-tier Groq budget because golden_dataset.py is kept small (~6 questions)
and rerank_top_n is kept low. Growing either back up risks the same token
exhaustion this project hit before.

Requires `make dev` running in another terminal, and the `eval` dependency
group installed (`uv sync --group eval`).
"""

import app.evals._ragas_compat  # noqa: F401  (must run before ragas imports)

import argparse
import sys

import requests
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
from ragas.run_config import RunConfig

from app.config.settings import settings
from app.evals.golden_dataset import GOLDEN_DATASET


def fetch_answer(backend_url: str, question: str) -> tuple[str, list[str]]:
    response = requests.post(f"{backend_url}/query", json={"q": question}, timeout=120)
    response.raise_for_status()
    data = response.json()
    answer = data.get("answer") or ""
    contexts = [c.removeprefix("CONTENT: ") for c in (data.get("sources") or [])]
    return answer, contexts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAGAS evaluation against the RAG backend."
    )
    parser.add_argument("--backend-url", default=settings.backend_url)
    parser.add_argument("--output", default="eval_results.csv")
    args = parser.parse_args()

    if any(item["question"].startswith("REPLACE ME") for item in GOLDEN_DATASET):
        sys.exit(
            "app/evals/golden_dataset.py still has placeholder entries — "
            "replace them with real questions/answers from your ingested corpus first."
        )

    print(f"Querying {args.backend_url} for {len(GOLDEN_DATASET)} question(s)...")
    samples: list[SingleTurnSample] = []
    for item in GOLDEN_DATASET:
        answer, contexts = fetch_answer(args.backend_url, item["question"])
        samples.append(
            SingleTurnSample(
                user_input=item["question"],
                response=answer,
                retrieved_contexts=contexts,
                reference=item["ground_truth"],
            )
        )

    dataset = EvaluationDataset(samples=samples)  # pyright: ignore[reportArgumentType]
    judge_llm = LangchainLLMWrapper(
        ChatGroq(  # pyright: ignore[reportArgumentType]
            api_key=settings.groq_api_key,
            model=settings.eval_judge_model,
            temperature=0,
        )
    )
    judge_embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model, api_key=settings.gemini_api_key
        )
    )

    # Faithfulness makes 2 judge calls per sample (claim extraction +
    # verification) and ContextPrecision makes one call PER retrieved chunk —
    # both resend the full context every time, which is what blew through the
    # Groq daily token budget when the dataset was 18 questions. With the
    # dataset trimmed to ~6 and rerank_top_n lowered, this fits comfortably.
    #
    # RAGAS defaults to 16 concurrent judge calls with a 180s-per-call
    # timeout; keep concurrency modest so calls don't queue up and blow the
    # timeout on a single small Groq model.
    result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(),
            AnswerRelevancy(),
            ContextPrecision(),
            ContextRecall(),
        ],
        llm=judge_llm,
        embeddings=judge_embeddings,
        run_config=RunConfig(max_workers=3, timeout=300),
    )

    print(result)
    result.to_pandas().to_csv(args.output, index=False)
    print(f"Saved per-question scores to {args.output}")


if __name__ == "__main__":
    main()
