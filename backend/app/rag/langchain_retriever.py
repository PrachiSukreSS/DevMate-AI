"""LangChain adapter for DevMate's local vector retrieval service."""

from uuid import UUID

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.rag.vector_store import get_vector_search_min_score, search_project_vectors


class ProjectDocumentRetriever(BaseRetriever):
    """Expose project vector search through LangChain's retriever interface."""

    project_id: UUID
    k: int = 5
    filename: str | None = None

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        """Return the top matching project chunks as LangChain Documents."""
        chunks = search_project_vectors(
            self.project_id,
            query,
            limit=self.k,
            min_score=get_vector_search_min_score(),
            filename=self.filename,
        )
        return [
            Document(
                page_content=chunk.content,
                metadata={
                    "document_id": str(chunk.document_id),
                    "filename": chunk.filename,
                    "chunk_index": chunk.chunk_index,
                    "score": chunk.score,
                },
            )
            for chunk in chunks
        ]
