"""Persist project chunk embeddings in a local Chroma collection."""

import logging
import os
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from app.db.database import get_connection
from app.rag.embedding_service import embed_texts
from app.schemas.document import RetrievedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "project_document_chunks"
VECTOR_STORE_PATH = Path(__file__).resolve().parents[2] / "vector_store"
DEFAULT_VECTOR_SEARCH_MIN_SCORE = 0.20


class VectorSearchConfigurationError(Exception):
    """Raised when the configured vector relevance threshold is invalid."""


class VectorIndexError(Exception):
    """Raised when the local vector index cannot be synchronized."""


def get_vector_search_min_score() -> float:
    """Read and validate the minimum cosine similarity accepted as evidence."""
    raw_score = os.getenv(
        "VECTOR_SEARCH_MIN_SCORE",
        str(DEFAULT_VECTOR_SEARCH_MIN_SCORE),
    )
    try:
        score = float(raw_score)
    except ValueError as exc:
        raise VectorSearchConfigurationError from exc

    if not -1.0 <= score <= 1.0:
        raise VectorSearchConfigurationError
    return score


@lru_cache(maxsize=1)
def _get_collection():
    """Open the persistent collection, creating it on the first use."""
    import chromadb

    client = chromadb.PersistentClient(path=str(VECTOR_STORE_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def index_project_chunks(project_id: UUID) -> int:
    """Embed and synchronize saved project chunks; return the total chunk count."""
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT document_chunks.id AS chunk_id,
                       documents.id AS document_id,
                       documents.filename AS filename,
                       document_chunks.chunk_index AS chunk_index,
                       document_chunks.content AS content
                FROM document_chunks
                JOIN documents ON documents.id = document_chunks.document_id
                WHERE documents.project_id = ?
                ORDER BY documents.filename, document_chunks.chunk_index
                """,
                (str(project_id),),
            ).fetchall()

        collection = _get_collection()
        existing = collection.get(
            where={"project_id": str(project_id)},
            include=["documents"],
        )
        existing_content = dict(zip(existing["ids"], existing["documents"]))
        chunk_ids = [row["chunk_id"] for row in rows]
        changed_rows = [
            row for row in rows
            if existing_content.get(row["chunk_id"]) != row["content"]
        ]

        if changed_rows:
            embeddings = embed_texts([row["content"] for row in changed_rows])
            collection.upsert(
                ids=[row["chunk_id"] for row in changed_rows],
                embeddings=embeddings,
                documents=[row["content"] for row in changed_rows],
                metadatas=[
                    {
                        "project_id": str(project_id),
                        "document_id": row["document_id"],
                        "filename": row["filename"],
                        "chunk_index": row["chunk_index"],
                    }
                    for row in changed_rows
                ],
            )

        stale_chunk_ids = set(existing["ids"]) - set(chunk_ids)
        if stale_chunk_ids:
            collection.delete(ids=list(stale_chunk_ids))

        return len(rows)
    except Exception as exc:
        logger.exception("Could not synchronize the local vector index.")
        raise VectorIndexError from exc


def search_project_vectors(
    project_id: UUID,
    query: str,
    limit: int = 5,
    min_score: float | None = None,
    filename: str | None = None,
) -> list[RetrievedChunk]:
    """Search project chunks, optionally filtering by filename and score."""
    collection = _get_collection()
    where_filter: dict[str, object] = {"project_id": str(project_id)}
    if filename is not None:
        where_filter = {
            "$and": [
                {"project_id": str(project_id)},
                {"filename": filename},
            ]
        }

    project_chunk_ids = collection.get(where=where_filter)["ids"]
    if not project_chunk_ids:
        return []

    query_embedding = embed_texts([query])[0]
    matches = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    chunk_ids = matches["ids"][0]
    documents = matches["documents"][0]
    metadatas = matches["metadatas"][0]
    distances = matches["distances"][0]
    with get_connection() as connection:
        current_rows = connection.execute(
            """
            SELECT document_chunks.id
            FROM document_chunks
            JOIN documents ON documents.id = document_chunks.document_id
            WHERE documents.project_id = ?
            """,
            (str(project_id),),
        ).fetchall()
    current_chunk_ids = {row["id"] for row in current_rows}

    retrieved_chunks = [
        RetrievedChunk(
            document_id=metadata["document_id"],
            filename=metadata["filename"],
            chunk_index=metadata["chunk_index"],
            content=content,
            score=1.0 - distance,
        )
        for chunk_id, content, metadata, distance in zip(
            chunk_ids, documents, metadatas, distances
        )
        if chunk_id in current_chunk_ids
    ]
    if min_score is None:
        return retrieved_chunks

    return [chunk for chunk in retrieved_chunks if chunk.score >= min_score]
