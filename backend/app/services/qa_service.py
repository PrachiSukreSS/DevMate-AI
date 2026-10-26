"""Retrieve project evidence, answer questions, and save interaction history."""

import json
from uuid import UUID, uuid4

from app.db.database import get_connection
from app.schemas.document import RetrievedChunk
from app.schemas.question import (
    AnswerSource,
    IssueInvestigationRequest,
    ProjectAnswerResponse,
    PendingInvestigationSummary,
    QuestionHistoryItem,
    StructuredProjectAnswer,
)
from app.agents.investigation_graph import (
    resume_investigation_approval,
    run_investigation_graph,
)
from app.rag.langchain_retriever import ProjectDocumentRetriever
from app.services.llm_service import generate_structured_project_answer
from app.services.project_service import get_project


def _to_source(chunk: RetrievedChunk) -> AnswerSource:
    """Convert a retrieved chunk into a citation returned by the API."""
    return AnswerSource(
        document_id=chunk.document_id,
        filename=chunk.filename,
        chunk_index=chunk.chunk_index,
        excerpt=chunk.content,
    )


def _save_interaction(
    project_id: UUID,
    question: str,
    answer: str,
    model: str,
    sources: list[AnswerSource],
    structured_answer: StructuredProjectAnswer | None,
) -> ProjectAnswerResponse:
    """Persist one question and answer, including the evidence sources."""
    interaction_id = uuid4()
    sources_json = json.dumps(
        [source.model_dump(mode="json") for source in sources]
    )
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO project_questions
                (id, project_id, question, answer, model, sources_json,
                 structured_answer_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(interaction_id),
                str(project_id),
                question,
                answer,
                model,
                sources_json,
                (
                    json.dumps(structured_answer.model_dump(mode="json"))
                    if structured_answer is not None
                    else None
                ),
            ),
        )
    return ProjectAnswerResponse(
        interaction_id=interaction_id,
        answer=answer,
        model=model,
        sources=sources,
        structured_answer=structured_answer,
    )


def _answer_with_chunks(
    project_id: UUID,
    question: str,
    retrieved_chunks: list[RetrievedChunk],
    history_question: str | None = None,
    prepared_answer: tuple[StructuredProjectAnswer, str] | None = None,
) -> ProjectAnswerResponse:
    """Build and save a grounded response from already retrieved chunks."""
    sources = [_to_source(chunk) for chunk in retrieved_chunks]
    saved_question = history_question or question
    if not sources:
        no_evidence_answer = StructuredProjectAnswer(
            answer="I could not find matching evidence in this project's documents.",
            suspected_cause=None,
            evidence_summary="No project document passed the retrieval threshold.",
            confidence="low",
            suggested_next_steps=[
                "Add or index relevant project documentation, then try again."
            ],
        )
        return _save_interaction(
            project_id,
            saved_question,
            no_evidence_answer.answer,
            "no-context",
            [],
            no_evidence_answer,
        )

    context = "\n\n".join(
        f"[Source: {source.filename}, chunk {source.chunk_index}]\n{source.excerpt}"
        for source in sources
    )
    if prepared_answer is None:
        structured_answer, model = generate_structured_project_answer(
            question,
            context,
        )
    else:
        structured_answer, model = prepared_answer
    return _save_interaction(
        project_id,
        saved_question,
        structured_answer.answer,
        model,
        sources,
        structured_answer,
    )


def answer_project_question(
    project_id: UUID,
    question: str,
) -> ProjectAnswerResponse | None:
    """Answer from matching project chunks; return None for an unknown project."""
    if get_project(project_id) is None:
        return None

    retriever = ProjectDocumentRetriever(project_id=project_id, k=5)
    retrieved_documents = retriever.invoke(question)
    retrieved_chunks = [
        RetrievedChunk(
            document_id=document.metadata["document_id"],
            filename=document.metadata["filename"],
            chunk_index=document.metadata["chunk_index"],
            content=document.page_content,
            score=document.metadata["score"],
        )
        for document in retrieved_documents
    ]
    return _answer_with_chunks(project_id, question, retrieved_chunks)


def investigate_project_issue(
    project_id: UUID,
    issue: IssueInvestigationRequest,
) -> ProjectAnswerResponse | None:
    """Search project evidence for an issue, then return a grounded report."""
    if get_project(project_id) is None:
        return None

    return run_investigation_graph(project_id, issue)


def resume_project_investigation(
    project_id: UUID,
    workflow_id: UUID,
    approved: bool,
) -> ProjectAnswerResponse | None:
    """Resume a pending approval only if its project still exists."""
    if get_project(project_id) is None:
        return None
    return resume_investigation_approval(project_id, workflow_id, approved)


def list_question_history(project_id: UUID) -> list[QuestionHistoryItem] | None:
    """Return saved Q&A interactions, or None when the project is unknown."""
    with get_connection() as connection:
        project = connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (str(project_id),),
        ).fetchone()
        if project is None:
            return None

        rows = connection.execute(
            """
            SELECT id, question, answer, model, sources_json,
                   structured_answer_json, created_at
            FROM project_questions
            WHERE project_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (str(project_id),),
        ).fetchall()

    return [
        QuestionHistoryItem(
            interaction_id=row["id"],
            question=row["question"],
            answer=row["answer"],
            model=row["model"],
            sources=json.loads(row["sources_json"]),
            structured_answer=(
                StructuredProjectAnswer.model_validate(
                    json.loads(row["structured_answer_json"])
                )
                if row["structured_answer_json"]
                else None
            ),
            created_at=row["created_at"],
        )
        for row in rows
    ]



def list_pending_investigations(
    project_id: UUID,
) -> list[PendingInvestigationSummary] | None:
    """Return resumable approval requests for a project, or None if it is missing."""
    with get_connection() as connection:
        project = connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (str(project_id),),
        ).fetchone()
        if project is None:
            return None
        rows = connection.execute(
            """
            SELECT workflow_id, title, response_json, created_at
            FROM pending_investigations
            WHERE project_id = ?
            ORDER BY created_at DESC, workflow_id DESC
            """,
            (str(project_id),),
        ).fetchall()

    return [
        PendingInvestigationSummary(
            workflow_id=row["workflow_id"],
            title=row["title"],
            response=ProjectAnswerResponse.model_validate_json(row["response_json"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]
