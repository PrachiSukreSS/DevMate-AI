"""HTTP endpoints for adding and searching project documentation."""

from pathlib import PurePosixPath
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.schemas.document import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentSearchResponse,
    RetrievedChunk,
    DocumentSummary,
    ProjectIndexResponse,
)
from app.rag.langchain_retriever import ProjectDocumentRetriever
from app.rag.vector_store import (
    VectorIndexError,
    VectorSearchConfigurationError,
    index_project_chunks,
    search_project_vectors,
)
from app.services.project_service import get_project
from app.services.document_service import (
    delete_project_document,
    ingest_document,
    list_project_documents,
    search_document_chunks,
)

router = APIRouter(prefix="/projects", tags=["documents"])


def _refresh_project_index(project_id: UUID, detail: str) -> int:
    """Refresh Chroma after a document change and return the indexed chunk count."""
    try:
        return index_project_chunks(project_id)
    except VectorIndexError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        ) from None


@router.post(
    "/{project_id}/documents",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_document(
    project_id: UUID,
    data: DocumentIngestRequest,
) -> DocumentIngestResponse:
    """Store text for an existing project and split it into chunks."""
    document = ingest_document(project_id, data)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    _refresh_project_index(
        project_id,
        "The document was saved, but its vector index could not be updated. "
        "Retry POST /projects/{project_id}/documents/index; do not upload it again.",
    )
    return document


@router.get(
    "/{project_id}/documents/search",
    response_model=DocumentSearchResponse,
)
def search_documents(
    project_id: UUID,
    query: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=10),
) -> DocumentSearchResponse:
    """Return chunks containing words related to the search query."""
    results = search_document_chunks(project_id, query.strip(), limit)
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return results


@router.get("/{project_id}/documents", response_model=list[DocumentSummary])
def get_project_documents(project_id: UUID) -> list[DocumentSummary]:
    """List documents stored for a project, including their chunk counts."""
    documents = list_project_documents(project_id)
    if documents is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return documents


@router.delete(
    "/{project_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_project_document(project_id: UUID, document_id: UUID) -> None:
    """Delete one document and its chunks from the selected project."""
    deleted = delete_project_document(project_id, document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this project.",
        )
    _refresh_project_index(
        project_id,
        "The document was deleted, but the vector index could not be refreshed. "
        "Retry POST /projects/{project_id}/documents/index.",
    )


MAX_TEXT_FILE_BYTES = 100_000


@router.post(
    "/{project_id}/documents/upload",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_text_document(
    project_id: UUID,
    file: Annotated[UploadFile, File(description="A UTF-8 plain text file")],
) -> DocumentIngestResponse:
    """Accept a small UTF-8 .txt file and store its chunked text."""
    filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .txt files are supported in this lesson.",
        )

    try:
        content_bytes = await file.read(MAX_TEXT_FILE_BYTES + 1)
    finally:
        await file.close()

    if len(content_bytes) > MAX_TEXT_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Text files must be 100 KB or smaller.",
        )

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The text file must use UTF-8 encoding.",
        )

    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The text file cannot be empty.",
        )

    document_data = DocumentIngestRequest(filename=filename, content=content)
    document = ingest_document(project_id, document_data)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    _refresh_project_index(
        project_id,
        "The document was saved, but its vector index could not be updated. "
        "Retry POST /projects/{project_id}/documents/index; do not upload it again.",
    )
    return document


@router.get(
    "/{project_id}/documents/langchain-search",
    response_model=DocumentSearchResponse,
)
def search_documents_with_langchain(
    project_id: UUID,
    query: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=10),
    filename: str | None = Query(default=None, min_length=1, max_length=255),
) -> DocumentSearchResponse:
    """Search using the LangChain retriever adapter and return the same API shape."""
    if get_project(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    retriever = ProjectDocumentRetriever(
        project_id=project_id, k=limit, filename=filename
    )
    try:
        documents = retriever.invoke(query.strip())
    except VectorSearchConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VECTOR_SEARCH_MIN_SCORE must be a number between -1 and 1.",
        ) from None
    results = [
        RetrievedChunk(
            document_id=document.metadata["document_id"],
            filename=document.metadata["filename"],
            chunk_index=document.metadata["chunk_index"],
            content=document.page_content,
            score=document.metadata["score"],
        )
        for document in documents
    ]
    return DocumentSearchResponse(query=query, results=results)


@router.post(
    "/{project_id}/documents/index",
    response_model=ProjectIndexResponse,
)
def index_project_documents(project_id: UUID) -> ProjectIndexResponse:
    """Create or refresh local embeddings for the project's saved chunks."""
    if get_project(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    chunks_indexed = _refresh_project_index(
        project_id,
        "The local vector index could not be updated. Check the server logs and retry.",
    )
    return ProjectIndexResponse(
        project_id=project_id,
        chunks_indexed=chunks_indexed,
    )


@router.get(
    "/{project_id}/documents/vector-search",
    response_model=DocumentSearchResponse,
)
def search_documents_by_vector(
    project_id: UUID,
    query: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=10),
    min_score: float | None = Query(default=None, ge=-1.0, le=1.0),
    filename: str | None = Query(default=None, min_length=1, max_length=255),
) -> DocumentSearchResponse:
    """Search indexed chunks by embedding similarity."""
    if get_project(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    normalized_query = query.strip()
    results = search_project_vectors(
        project_id, normalized_query, limit, min_score, filename
    )
    return DocumentSearchResponse(query=normalized_query, results=results)
