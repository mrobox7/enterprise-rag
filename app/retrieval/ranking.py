import time
import logfire
from flashrank import Ranker, RerankRequest

from app.config.settings import settings


class Reranker:
    """
    Cross-encoder reranker using FlashRank's local ONNX models
    (default: ms-marco-MiniLM-L-6-v2).

    Vector search (cosine similarity) is fast but approximate.
    Cross-encoders score (query, doc) pairs jointly — much more
    precise, normally slow.
    """

    def __init__(self, cache_dir: str = "/tmp/flashrank"):
        self._cache_dir = cache_dir
        self._ranker: Ranker | None = None  # lazy-loaded on first use

    def _get_ranker(self) -> Ranker:
        if self._ranker is None:
            logfire.info("🧠 Initializing FlashRank Model locally...")
            try:
                self._ranker = Ranker(
                    model_name=settings.reranker_model, cache_dir=self._cache_dir
                )
            except Exception:
                self._ranker = Ranker()
        return self._ranker

    def rerank(self, query: str, documents: list[str], top_n: int = 5) -> list[str]:
        if not documents:
            return []

        start_time = time.time()
        logfire.info(f"📡 [Reranker] Sending {len(documents)} docs to FlashRank...")

        try:
            ranker = self._get_ranker()
            passages = [{"id": i, "text": doc} for i, doc in enumerate(documents)]
            request = RerankRequest(query=query, passages=passages)
            results = ranker.rerank(request)

            reranked_docs = [res["text"] for res in results[:top_n]]

            duration = time.time() - start_time
            top_score = results[0]["score"] if results else "N/A"
            logfire.info(
                f"✅ [Reranker] Done in {duration:.2f}s. Top score: {top_score}"
            )

            return reranked_docs
        except Exception as e:
            logfire.error(f"❌ [Reranker] Reranking failed: {e}")
            return documents[:top_n]
