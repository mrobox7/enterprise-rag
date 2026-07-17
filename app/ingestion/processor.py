import argparse
import sys
from pathlib import Path
from typing import cast

import logfire

from app.ingestion.manifest import IngestionManifest
from app.ingestion.pipeline import IngestionPipeline
from app.utils.compute_file_hash import ComputeFileHash


def process_file(
    pipeline: IngestionPipeline,
    manifest: IngestionManifest,
    file_path: Path,
    collection_name: str,
    source_type: str | None = None,
) -> str:
    """Ingest a single file unless its content hash matches what's already
    in the manifest. Returns "succeeded", "failed", or "skipped" — never
    raises, so one bad file can't abort a directory batch."""

    source = str(file_path)

    with logfire.span(
        "Process file",
        file=file_path.name,
        collection=collection_name,
    ):
        file_hash = ComputeFileHash(file_path)
        previous_hash = manifest.get(source)

        if previous_hash == file_hash:
            logfire.info("⏭️ Unchanged — skipping", file=file_path.name)
            return "skipped"

        try:
            result = pipeline.ingest(
                file_path=file_path,
                collection_name=collection_name,
                extra_metadata={"source_type": source_type} if source_type else None,
            )
            manifest.set(source, file_hash, result["chunks"])
            return "succeeded"

        except Exception:
            logfire.exception(
                "❌ Failed to process file",
                file=file_path.name,
                collection=collection_name,
            )
            return "failed"


def process_directory(
    pipeline: IngestionPipeline,
    manifest: IngestionManifest,
    directory: Path,
    collection_name: str,
    source_type: str | None = None,
    recursive: bool = False,
) -> dict[str, list[Path]]:
    """Process every file in a directory.
    Returns {"succeeded": [...], "failed": [...], "skipped": [...]}."""

    if not directory.exists():
        raise FileNotFoundError(f"{directory} does not exist")

    walker = directory.rglob("*") if recursive else directory.iterdir()
    files = sorted(f for f in walker if f.is_file())

    results: dict[str, list[Path]] = {"succeeded": [], "failed": [], "skipped": []}

    with logfire.span(
        "Process directory",
        directory=str(directory),
        collection=collection_name,
        files=len(files),
    ):
        logfire.info("📂 Files discovered", count=len(files))

        for file in files:
            status = process_file(
                pipeline, manifest, file, collection_name, source_type
            )
            results[status].append(file)

        logfire.info(
            "✅ Directory processed",
            succeeded=len(results["succeeded"]),
            failed=len(results["failed"]),
            skipped=len(results["skipped"]),
        )

    return results


def infer_source_type(name: str) -> str:
    lowered = name.lower()
    if "true" in lowered:
        return "true"
    if "noisy" in lowered:
        return "noisy"
    return name


def run_ingestion(
    pipeline: IngestionPipeline,
    base_dir: Path,
    collection_name: str,
    explicit_source_type: str | None = None,
    wipe: bool = False,
    recursive: bool = False,
    prune: bool = False,
) -> dict[str, list[Path]]:

    manifest_collection = f"{collection_name}__manifest"

    with logfire.span(
        "Ingestion run",
        base_directory=str(base_dir),
        collection=collection_name,
    ):
        if wipe:
            with logfire.span("Wipe collection", collection=collection_name):
                pipeline.vectorstore.delete_collection(collection_name)
                # Manifest must be wiped alongside the collection — otherwise
                # every file would still show as "unchanged" and be skipped
                # forever, even though its vectors were just deleted.
                try:
                    pipeline.vectorstore.delete_collection(manifest_collection)
                except Exception:
                    pass  # manifest collection may not exist yet
                logfire.info(
                    "🗑️ Collection and manifest wiped", collection=collection_name
                )

        pipeline.vectorstore.create_collection(
            collection_name=collection_name,
            vector_size=pipeline.embedder.dimension,
        )

        manifest = IngestionManifest(
            client=pipeline.vectorstore.client,
            collection_name=manifest_collection,
        )

        subdirs = [d for d in base_dir.iterdir() if d.is_dir()]

        if not subdirs:
            source_type = explicit_source_type or infer_source_type(base_dir.name)
            logfire.info(f"No sub-folders found — tagging as '{source_type}'.")
            results = process_directory(
                pipeline, manifest, base_dir, collection_name, source_type, recursive
            )
        else:
            results: dict[str, list[Path]] = {
                "succeeded": [],
                "failed": [],
                "skipped": [],
            }
            for subdir in subdirs:
                source_type = explicit_source_type or infer_source_type(subdir.name)
                sub_result = process_directory(
                    pipeline, manifest, subdir, collection_name, source_type, recursive
                )
                for key in results:
                    results[key].extend(sub_result[key])

        if prune:
            with logfire.span("Prune stale manifest entries"):
                all_seen = results["succeeded"] + results["failed"] + results["skipped"]
                current_paths = {str(p) for p in all_seen}
                removed = manifest.prune(current_paths)
                for file_path in removed:
                    pipeline.vectorstore.delete_by_source(collection_name, file_path)
                    results["pruned"] = [Path(p) for p in removed]
                logfire.info("🧹 Pruned files removed from disk", count=len(removed))

        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise RAG Ingestion Processor")

    _ = parser.add_argument(
        "-d",
        "--directory",
        type=Path,
        required=True,
        help="Directory containing documents (may contain sub-folders per source type)",
    )
    _ = parser.add_argument(
        "-c",
        "--collection",
        required=True,
        help="Qdrant collection name",
    )
    _ = parser.add_argument(
        "-s",
        "--source-type",
        default=None,
        help="Explicit source type tag (overrides sub-folder name inference)",
    )
    _ = parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recurse into nested sub-directories within each source folder",
    )
    _ = parser.add_argument(
        "--wipe",
        action="store_true",
        help="Drop and recreate the collection (and its manifest) before ingesting",
    )
    _ = parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove vectors for files no longer present on disk. "
        + "Only use when --directory covers the FULL corpus for this collection.",
    )

    args = parser.parse_args()

    directory = cast(Path, args.directory)
    collection = cast(str, args.collection)
    source_type = cast(str | None, args.source_type)
    recursive = cast(bool, args.recursive)
    wipe = cast(bool, args.wipe)
    prune = cast(bool, args.prune)

    if not directory.exists():
        print(f"Error: path '{directory}' does not exist.")
        sys.exit(1)

    pipeline = IngestionPipeline()

    results = run_ingestion(
        pipeline=pipeline,
        base_dir=directory,
        collection_name=collection,
        explicit_source_type=source_type,
        wipe=wipe,
        recursive=recursive,
        prune=prune,
    )

    logfire.info("Ingestion job completed.")

    summary = (
        f"{len(results['succeeded'])} succeeded, "
        f"{len(results['skipped'])} skipped (unchanged), "
        f"{len(results['failed'])} failed"
    )
    if "pruned" in results:
        summary += f", {len(results['pruned'])} pruned"

    if results["failed"]:
        print(f"Completed with failures: {summary}.")
        sys.exit(1)

    print(f"Done: {summary}.")


if __name__ == "__main__":
    main()
