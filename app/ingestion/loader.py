from pathlib import Path

import logfire

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPowerPointLoader,
)


class Loader:
    def load(self, file_path: Path) -> list[Document]:
        with logfire.span(
            "Load document",
            path=str(file_path),
            filename=file_path.name,
        ):
            if not file_path.exists():
                logfire.error(
                    "❌ File not found",
                    path=str(file_path),
                )
                raise FileNotFoundError(f"{file_path} does not exist")

            suffix = file_path.suffix.lower()

            match suffix:
                case ".pdf":
                    loader = PyPDFLoader(str(file_path))

                case ".txt":
                    loader = TextLoader(str(file_path))

                case ".docx":
                    loader = Docx2txtLoader(str(file_path))  # pyright: ignore[reportEmptyAbstractUsage]

                case ".html":
                    loader = UnstructuredHTMLLoader(str(file_path))

                case ".md":
                    loader = UnstructuredMarkdownLoader(str(file_path))

                case ".ppt" | ".pptx":
                    loader = UnstructuredPowerPointLoader(str(file_path))

                case _:
                    logfire.error(
                        "❌ Unsupported file type",
                        file_type=suffix,
                    )
                    raise ValueError(f"Unsupported file type: {suffix}")

            try:
                logfire.info(
                    "📄 Using loader",
                    loader=loader.__class__.__name__,
                    file_type=suffix,
                )

                documents = loader.load()

                empty_pages = sum(
                    1 for doc in documents if not doc.page_content.strip()
                )

                if documents and empty_pages == len(documents):
                    logfire.warning(
                        "⚠️ Loaded document has no extractable text",
                        path=str(file_path),
                        pages=len(documents),
                        file_type=suffix,
                    )
                elif empty_pages:
                    logfire.warning(
                        "⚠️ Some pages had no extractable text",
                        path=str(file_path),
                        empty_pages=empty_pages,
                        total_pages=len(documents),
                        file_type=suffix,
                    )

                logfire.info(
                    "✅ Document loaded",
                    pages=len(documents),
                    file_type=suffix,
                )

                return documents

            except Exception:
                logfire.exception(
                    "❌ Failed to load document",
                    path=str(file_path),
                )
                raise
