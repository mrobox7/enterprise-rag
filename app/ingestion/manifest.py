from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

import logfire

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


class IngestionManifest:
    """Tracks which version (content hash) of each file has already been
    ingested, so unchanged files can be skipped without re-embedding.
    """

    def __init__(self, client: QdrantClient, collection_name: str):
        self.client: QdrantClient = client
        self.collection_name: str = collection_name
        self._ensured: bool = False

    def ensure_collection(self) -> None:
        if self._ensured:
            return

        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            _ = self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1, distance=Distance.COSINE),
            )
            logfire.info(
                "✅ Manifest collection created",
                collection=self.collection_name,
            )

        self._ensured = True

    @staticmethod
    def _point_id(file_path: str) -> str:
        return str(uuid5(NAMESPACE_URL, file_path))

    def get(self, file_path: str) -> str | None:
        """Return the last-ingested content hash for this file, or None
        if it's never been ingested (or the manifest has no record)."""

        self.ensure_collection()

        result = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[self._point_id(file_path)],
            with_payload=True,
        )

        if not result:
            return None

        file_hash = (result[0].payload or {}).get("file_hash")
        return file_hash if isinstance(file_hash, str) else None

    def set(self, file_path: str, file_hash: str, chunk_count: int) -> None:
        """Record that this file has been ingested at this content hash."""

        self.ensure_collection()

        _ = self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=self._point_id(file_path),
                    vector=[0.0],
                    payload={
                        "file_path": file_path,
                        "file_hash": file_hash,
                        "chunk_count": chunk_count,
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            ],
        )

        logfire.info(
            "📝 Manifest updated",
            file=file_path,
            chunks=chunk_count,
        )

    def delete(self, file_path: str) -> None:
        """Remove a file's manifest record (its vectors must be deleted
        separately via QdrantVectorStore.delete_by_source)."""

        self.ensure_collection()

        _ = self.client.delete(
            collection_name=self.collection_name,
            points_selector=[self._point_id(file_path)],
        )

    def list_paths(self) -> set[str]:
        """All file paths currently tracked in the manifest."""

        self.ensure_collection()

        paths: set[str] = set()
        next_offset = None

        while True:
            records, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                with_payload=True,
                with_vectors=False,
                limit=256,
                offset=next_offset,
            )
            for r in records:
                payload = r.payload or {}
                file_path = payload.get("file_path")
                if isinstance(file_path, str):
                    paths.add(file_path)

            if next_offset is None:
                break

        return paths

    def prune(self, current_paths: set[str]) -> list[str]:
        """Remove manifest records for files no longer present in
        current_paths. Returns the removed file paths so the caller can
        also delete their vectors via QdrantVectorStore.delete_by_source.

        CAUTION: current_paths must reflect the FULL set of files this
        manifest is responsible for. If you run this against a partial
        directory (e.g. one subfolder out of several sharing the same
        collection), everything outside that subset will look "removed"
        and get pruned incorrectly. Only call this after a full-corpus
        walk, not a scoped/partial run.
        """

        stale = self.list_paths() - current_paths

        for file_path in stale:
            self.delete(file_path)

        if stale:
            logfire.info("🧹 Pruned stale manifest entries", count=len(stale))

        return sorted(stale)
