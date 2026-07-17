import time
from typing import cast

import logfire

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config.settings import settings


class Embedder:
    def __init__(self):
        self._model: GoogleGenerativeAIEmbeddings | None = None
        self._dimension: int | None = None

    def _get_model(self) -> GoogleGenerativeAIEmbeddings:
        if self._model is None:
            with logfire.span("Initialize Gemini embedding model"):
                self._model = GoogleGenerativeAIEmbeddings(
                    model=settings.embedding_model, api_key=settings.gemini_api_key
                )

                # Detect embedding dimension automatically
                probe = self._model.embed_query("probe")
                self._dimension = len(probe)

                logfire.info(
                    "✅ Embedding model initialized",
                    model=settings.embedding_model,
                    dimension=self._dimension,
                )

        return self._model

    @property
    def dimension(self) -> int:
        """Embedding vector size. Guarantees the model is initialized
        (and therefore that a real int, never None, is returned) instead
        of relying on embed_documents/embed_query having run first."""
        if self._dimension is None:
            _ = self._get_model()
        assert self._dimension is not None
        return self._dimension

    def _is_retryable(self, error: Exception) -> bool:
        """Return True if the error is likely to succeed on retry."""

        err = str(error).lower()

        retryable_errors = (
            "429",
            "rate",
            "quota",
            "resource_exhausted",
            "timeout",
            "timed out",
            "connection",
            "503",
            "500",
            "internal",
            "unavailable",
        )

        return any(keyword in err for keyword in retryable_errors)

    def embed_documents(self, chunks: list[Document]) -> list[list[float]]:
        texts = [chunk.page_content for chunk in chunks]

        if not texts:
            logfire.warning("⚠️ No text to embed", chunks=len(chunks))
            return []

        model = self._get_model()
        all_vectors: list[list[float]] = []
        batch_size = settings.embedding_batch_size

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]

            with logfire.span(
                "Embed batch",
                model=settings.embedding_model,
                batch_start=start,
                batch_size=len(batch),
            ):
                for attempt in range(3):
                    try:
                        vectors = model.embed_documents(batch)
                        break

                    except Exception as e:
                        if not self._is_retryable(e):
                            logfire.error(
                                "❌ Non-retryable embedding error",
                                error=str(e),
                            )
                            raise

                        if attempt == 2:
                            logfire.error(
                                "❌ Embedding failed after maximum retries",
                                attempts=attempt + 1,
                                error=str(e),
                            )
                            raise

                        wait = cast(int, 2**attempt)

                        logfire.warning(
                            "⚠️ Retryable embedding error",
                            attempt=attempt + 1,
                            retry_in_seconds=wait,
                            error=str(e),
                        )

                        time.sleep(wait)
                else:
                    raise RuntimeError("Embedding retry loop exhausted without raising")

                all_vectors.extend(vectors)

        logfire.info(
            "✅ Batch embedded",
            vectors=len(all_vectors),
            dimension=self.dimension,
        )

        return all_vectors

    def embed_query(self, query: str) -> list[float]:
        model = self._get_model()

        with logfire.span("Embed query"):
            vector = model.embed_query(query)

            logfire.info(
                "✅ Query embedded",
                dimension=len(vector),
            )

            return vector
