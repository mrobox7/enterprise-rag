from pathlib import Path
from typing import TypedDict

import logfire

from langchain_core.documents import Document

from app.ingestion.loader import Loader
from app.ingestion.splitter import Splitter
from app.retrieval.embedder import Embedder
from app.vectorstore.qdrant import QdrantVectorStore


class IngestResult(TypedDict):
    file: str
    documents: int
    chunks: int
    vectors: int
    collection: str


class IngestionPipeline:
    def __init__(self):
        self.loader: Loader = Loader()
        self.splitter: Splitter = Splitter()
        self.embedder: Embedder = Embedder()
        self.vectorstore: QdrantVectorStore = QdrantVectorStore()

    def ingest(
        self,
        file_path: Path,
        collection_name: str,
        extra_metadata: dict[str, object] | None = None,
    ) -> IngestResult:
        with logfire.span(
            "Ingest document",
            file=file_path.name,
            collection=collection_name,
        ):
            source = str(file_path)

            # 1. Load
            documents = self.loader.load(file_path)

            # 2. Split
            chunks: list[Document] = self.splitter.split(documents)

            # Canonical identity for this file's chunks — used for
            # deterministic point ids and delete-by-source cleanup.
            # Set unconditionally so it can't be missing or inconsistent
            # across loaders, and applied before extra_metadata so a
            # caller can never accidentally override it.
            for chunk in chunks:
                chunk.metadata["source"] = source
                if extra_metadata:
                    chunk.metadata.update(extra_metadata)
                    chunk.metadata["source"] = source

            # Remove any previously stored points for this exact file.
            # Always runs — even if the new version has zero chunks — so
            # a file that shrank, got emptied, or was re-ingested doesn't
            # leave stale/orphaned vectors behind. Cheap no-op if none exist.
            self.vectorstore.delete_by_source(collection_name, source)

            if not chunks:
                logfire.warning(
                    "⚠️ No chunks produced, skipping embed/store",
                    file=file_path.name,
                    documents=len(documents),
                )
                return {
                    "file": file_path.name,
                    "documents": len(documents),
                    "chunks": 0,
                    "vectors": 0,
                    "collection": collection_name,
                }

            # 3. Embed
            vectors = self.embedder.embed_documents(chunks)

            # 4. Store vectors (collection is assumed to already exist —
            #    the caller ensures it once before processing any files)
            self.vectorstore.upsert(
                collection_name=collection_name,
                chunks=chunks,
                vectors=vectors,
            )

            logfire.info(
                "✅ Ingestion completed",
                file=file_path.name,
                documents=len(documents),
                chunks=len(chunks),
                vectors=len(vectors),
            )

            return {
                "file": file_path.name,
                "documents": len(documents),
                "chunks": len(chunks),
                "vectors": len(vectors),
                "collection": collection_name,
            }
