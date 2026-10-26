"""Read-only LangChain tools bound to one selected project."""

import json
from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool
from pydantic import Field

from app.rag.vector_store import get_vector_search_min_score, search_project_vectors
from app.services.project_service import get_project


def create_project_search_tool(project_id: UUID):
    """Create a read-only document search tool scoped to one existing project."""
    if get_project(project_id) is None:
        raise ValueError("Project not found.")

    @tool(
        "search_project_docs",
        description=(
            "Search the selected project's indexed documentation for relevant "
            "evidence. This tool is read-only and cannot change files or data."
        ),
    )
    def search_project_docs(
        query: Annotated[str, Field(min_length=1, max_length=200)],
    ) -> str:
        """Return up to three evidence chunks from this project's documents."""
        chunks = search_project_vectors(
            project_id,
            query.strip(),
            limit=3,
            min_score=get_vector_search_min_score(),
        )
        return json.dumps(
            {
                "query": query,
                "results": [
                    {
                        "document_id": str(chunk.document_id),
                        "filename": chunk.filename,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "score": chunk.score,
                    }
                    for chunk in chunks
                ],
            },
            ensure_ascii=False,
        )

    return search_project_docs
