"""Request and response shapes for adding project documentation."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DocumentIngestRequest(BaseModel):
    """Plain text document content sent by an API client."""

    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=100000)

    @field_validator("filename")
    @classmethod
    def filename_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Filename cannot be blank.")
        return value

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Document content cannot be blank.")
        return value


class DocumentIngestResponse(BaseModel):
    """Summary of a document and the chunks created from it."""

    document_id: UUID
    project_id: UUID
    filename: str
    chunks_created: int

class RetrievedChunk(BaseModel):
    """One text chunk selected by the local keyword search."""

    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    score: float


class DocumentSearchResponse(BaseModel):
    """Search query and the most relevant matching chunks."""

    query: str
    results: list[RetrievedChunk]

class DocumentSummary(BaseModel):
    """Document metadata and the number of chunks stored for it."""

    document_id: UUID
    filename: str
    chunks_created: int



class ProjectIndexResponse(BaseModel):
    """Summary of a project's local vector index operation."""

    project_id: UUID
    chunks_indexed: int
