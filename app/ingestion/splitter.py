import logfire

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class Splitter:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, documents: list[Document]) -> list[Document]:
        with logfire.span(
            "Split documents",
            documents=len(documents),
        ):
            chunks = self.splitter.split_documents(documents)

            logfire.info(
                "✂️ Documents split",
                chunks=len(chunks),
            )

            return chunks
