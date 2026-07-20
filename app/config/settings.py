from functools import lru_cache
from typing import ClassVar

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # application
    app_name: str = "Enterprise RAG"
    environment: str = "development"
    backend_url: str = "http://localhost:8000"

    # Embeddings
    embedding_model: str = "models/gemini-embedding-2"
    embedding_batch_size: int = 50

    # llm
    llm_model: str = "llama-3.3-70b-versatile"

    # gemini
    gemini_api_key: SecretStr | None = None

    # groq
    groq_api_key: SecretStr | None = None

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "enterprise_rag"

    # Retrieval / reranking
    retrieval_candidate_k: int = 20
    rerank_top_n: int = 5
    reranker_model: str = "ms-marco-MiniLM-L-6-v2"

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
