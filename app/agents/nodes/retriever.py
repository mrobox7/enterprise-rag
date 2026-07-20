from typing import cast

import logfire

from app.agents.state import AgentState
from app.config.settings import settings
from app.retrieval.embedder import Embedder
from app.retrieval.ranking import Reranker
from app.vectorstore.qdrant import QdrantVectorStore

embedder = Embedder()
vectorstore = QdrantVectorStore()
reranker = Reranker()


def retrieve_node(state: AgentState) -> dict[str, object]:
    """
    Performs vector search for technical queries, then reranks the
    candidates with a cross-encoder for more precise ordering.
    """
    query = state.current_query

    with logfire.span("🔍 Knowledge Retrieval"):
        logfire.info(f"Searching Qdrant for: {query}")

        query_vector = embedder.embed_query(query)
        raw_results = vectorstore.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_vector,
            limit=settings.retrieval_candidate_k,
        )

        logfire.info(f"Retrieved {len(raw_results)} candidates from Vector DB")

        contents = [
            cast(str, (point.payload or {}).get("content", "")) for point in raw_results
        ]
        reranked_contents = reranker.rerank(
            query=query, documents=contents, top_n=settings.rerank_top_n
        )

        formatted_docs = [f"CONTENT: {content}" for content in reranked_contents]

    return {
        "documents": formatted_docs,
        "status": "Found technical context.",
        "plan": state.plan + ["Context Retrieved"],
    }
