"""Document text chunking and persistence."""

from collections import Counter
import math
import re
from uuid import UUID, uuid4

from app.db.database import get_connection
from app.schemas.document import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentSearchResponse,
    DocumentSummary,
    RetrievedChunk,
)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping character-based chunks."""
    chunks: list[str] = []
    step = CHUNK_SIZE - CHUNK_OVERLAP

    for start in range(0, len(text), step):
        chunk = text[start : start + CHUNK_SIZE]
        if chunk:
            chunks.append(chunk)

    return chunks


def ingest_document(
    project_id: UUID,
    data: DocumentIngestRequest,
) -> DocumentIngestResponse | None:
    """Save a document and its chunks; return None if its project is missing."""
    document_id = uuid4()
    chunks = chunk_text(data.content)

    with get_connection() as connection:
        project = connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (str(project_id),),
        ).fetchone()
        if project is None:
            return None

        connection.execute(
            "INSERT INTO documents (id, project_id, filename) VALUES (?, ?, ?)",
            (str(document_id), str(project_id), data.filename),
        )
        connection.executemany(
            """
            INSERT INTO document_chunks (id, document_id, chunk_index, content)
            VALUES (?, ?, ?, ?)
            """,
            [
                (str(uuid4()), str(document_id), index, chunk)
                for index, chunk in enumerate(chunks)
            ],
        )

    return DocumentIngestResponse(
        document_id=document_id,
        project_id=project_id,
        filename=data.filename,
        chunks_created=len(chunks),
    )


def search_document_chunks(
    project_id: UUID,
    query: str,
    limit: int = 5,
) -> DocumentSearchResponse | None:
    """Find stored chunks with the most matching query words."""
    stop_words = {"a", "an", "and", "are", "can", "does", "do", "for", "how", "in", "is", "of", "the", "to", "what"}
    query_terms = re.findall(r"[a-zA-Z0-9_]+", query.lower())
    query_counts = Counter(term for term in query_terms if term not in stop_words)

    with get_connection() as connection:
        project = connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (str(project_id),),
        ).fetchone()
        if project is None:
            return None

        rows = connection.execute(
            """
            SELECT documents.id AS document_id,
                   documents.filename AS filename,
                   document_chunks.chunk_index AS chunk_index,
                   document_chunks.content AS content
            FROM document_chunks
            JOIN documents ON documents.id = document_chunks.document_id
            WHERE documents.project_id = ?
            """,
            (str(project_id),),
        ).fetchall()

    token_counts = [
        Counter(re.findall(r"[a-zA-Z0-9_]+", row["content"].lower()))
        for row in rows
    ]
    document_frequency = Counter(
        term
        for counts in token_counts
        for term in counts
    )
    total_documents = len(rows)
    inverse_document_frequency = {
        term: math.log((total_documents + 1) / (frequency + 1)) + 1
        for term, frequency in document_frequency.items()
    }

    query_vector = {
        term: (1 + math.log(count)) * inverse_document_frequency[term]
        for term, count in query_counts.items()
        if term in inverse_document_frequency
    }
    query_length = math.sqrt(sum(weight * weight for weight in query_vector.values()))

    matches: list[RetrievedChunk] = []
    for row, counts in zip(rows, token_counts):
        document_vector = {
            term: (1 + math.log(count)) * inverse_document_frequency[term]
            for term, count in counts.items()
        }
        document_length = math.sqrt(
            sum(weight * weight for weight in document_vector.values())
        )
        shared_terms = query_vector.keys() & document_vector.keys()
        dot_product = sum(
            query_vector[term] * document_vector[term]
            for term in shared_terms
        )
        if dot_product == 0 or query_length == 0 or document_length == 0:
            continue

        score = dot_product / (query_length * document_length)
        matches.append(
            RetrievedChunk(
                document_id=row["document_id"],
                filename=row["filename"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                score=score,
            )
        )

    matches.sort(key=lambda result: (-result.score, result.chunk_index))
    return DocumentSearchResponse(query=query, results=matches[:limit])




def list_project_documents(project_id: UUID) -> list[DocumentSummary] | None:
    """List a project's documents, or return None for an unknown project."""
    with get_connection() as connection:
        project = connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (str(project_id),),
        ).fetchone()
        if project is None:
            return None

        rows = connection.execute(
            """
            SELECT documents.id AS document_id,
                   documents.filename AS filename,
                   COUNT(document_chunks.id) AS chunks_created
            FROM documents
            LEFT JOIN document_chunks
                ON document_chunks.document_id = documents.id
            WHERE documents.project_id = ?
            GROUP BY documents.id, documents.filename
            ORDER BY documents.filename
            """,
            (str(project_id),),
        ).fetchall()

    return [
        DocumentSummary(
            document_id=row["document_id"],
            filename=row["filename"],
            chunks_created=row["chunks_created"],
        )
        for row in rows
    ]


def delete_project_document(project_id: UUID, document_id: UUID) -> bool:
    """Delete a document owned by a project and cascade-delete its chunks."""
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM documents WHERE id = ? AND project_id = ?",
            (str(document_id), str(project_id)),
        )
        return cursor.rowcount > 0

