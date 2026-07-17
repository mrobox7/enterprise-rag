from typing import cast
from uuid import NAMESPACE_URL, uuid5

import logfire

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config.settings import settings


class QdrantVectorStore:
    def __init__(self):
        with logfire.span("Initialize Qdrant client"):
            self.client: QdrantClient = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
            )
            self._known_collections: set[str] = set()

            logfire.info(
                "✅ Qdrant client initialized",
                url=settings.qdrant_url,
            )

    def delete_collection(self, collection_name: str) -> None:
        _ = self.client.delete_collection(collection_name=collection_name)
        self._known_collections.discard(collection_name)

        logfire.info(
            "🗑️ Collection deleted",
            collection=collection_name,
        )

    def delete_by_source(self, collection_name: str, source: str) -> None:
        with logfire.span(
            "Delete points by source",
            collection=collection_name,
            source=source,
        ):
            _ = self.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="source", match=MatchValue(value=source))]
                ),
            )

            logfire.info(
                "🗑️ Deleted existing points for source",
                collection=collection_name,
                source=source,
            )

    def create_collection(
        self,
        collection_name: str,
        vector_size: int,
    ) -> None:
        if collection_name in self._known_collections:
            return

        collections = self.client.get_collections().collections

        if any(c.name == collection_name for c in collections):
            self._known_collections.add(collection_name)
            logfire.info(
                "📁 Collection already exists",
                collection=collection_name,
            )
            return

        _ = self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )
        self._known_collections.add(collection_name)

        logfire.info(
            "✅ Collection created",
            collection=collection_name,
            dimension=vector_size,
        )

    def upsert(
        self,
        collection_name: str,
        chunks: list[Document],
        vectors: list[list[float]],
    ) -> None:
        with logfire.span(
            "Upsert vectors",
            collection=collection_name,
            count=len(vectors),
        ):
            points: list[PointStruct] = []

            for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
                source = cast(str, chunk.metadata.get("source", ""))
                point_id = str(uuid5(NAMESPACE_URL, f"{source}::{idx}"))

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "content": chunk.page_content,
                            **chunk.metadata,
                        },
                    )
                )

            _ = self.client.upsert(
                collection_name=collection_name,
                points=points,
            )

            logfire.info(
                "✅ Vectors upserted",
                count=len(points),
            )

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
    ):
        """Search similar vectors."""

        with logfire.span(
            "Vector search",
            collection=collection_name,
            limit=limit,
        ):
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
            )

            logfire.info(
                "✅ Search complete",
                results=len(results.points),
            )

            return results.points
