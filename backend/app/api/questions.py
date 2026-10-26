"""HTTP endpoint for asking questions using a project's documents."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.agents.investigation_graph import InvestigationWorkflowNotPendingError
from app.rag.vector_store import VectorSearchConfigurationError
from app.schemas.question import (
    ApprovalDecision,
    IssueInvestigationRequest,
    ProjectAnswerResponse,
    PendingInvestigationSummary,
    ProjectQuestionRequest,
    QuestionHistoryItem,
)
from app.services.llm_service import (
    LLMConfigurationError,
    LLMNotConfiguredError,
    LLMProviderError,
)
from app.services.qa_service import (
    answer_project_question,
    investigate_project_issue,
    resume_project_investigation,
    list_question_history,
    list_pending_investigations,
)

router = APIRouter(prefix="/projects", tags=["project questions"])


@router.post("/{project_id}/ask", response_model=ProjectAnswerResponse)
def ask_project(
    project_id: UUID,
    data: ProjectQuestionRequest,
) -> ProjectAnswerResponse:
    """Return a document-grounded answer with source excerpts."""
    try:
        result = answer_project_question(project_id, data.question)
    except LLMConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM_MODE must be mock or openai.",
        )
    except VectorSearchConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VECTOR_SEARCH_MIN_SCORE must be a number between -1 and 1.",
        )
    except LLMNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set OPENAI_API_KEY to use OpenAI mode.",
        )
    except LLMProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM provider could not complete the request.",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return result


@router.get("/{project_id}/history", response_model=list[QuestionHistoryItem])
def get_project_history(project_id: UUID) -> list[QuestionHistoryItem]:
    """Return saved questions and answers for a project."""
    history = list_question_history(project_id)
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return history


@router.get(
    "/{project_id}/investigations/pending",
    response_model=list[PendingInvestigationSummary],
)
def get_pending_project_investigations(
    project_id: UUID,
) -> list[PendingInvestigationSummary]:
    """List saved investigations that are waiting for an approval decision."""
    pending = list_pending_investigations(project_id)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return pending


@router.post("/{project_id}/investigate", response_model=ProjectAnswerResponse)
def investigate_issue(
    project_id: UUID,
    data: IssueInvestigationRequest,
) -> ProjectAnswerResponse:
    """Investigate an issue using the project's bounded document search tool."""
    try:
        result = investigate_project_issue(project_id, data)
    except LLMConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM_MODE must be mock or openai.",
        )
    except VectorSearchConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VECTOR_SEARCH_MIN_SCORE must be a number between -1 and 1.",
        )
    except LLMNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set OPENAI_API_KEY to use OpenAI mode.",
        )
    except LLMProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM provider could not complete the request.",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return result


@router.post(
    "/{project_id}/investigations/{workflow_id}/approval",
    response_model=ProjectAnswerResponse,
)
def approve_investigation_action_plan(
    project_id: UUID,
    workflow_id: UUID,
    data: ApprovalDecision,
) -> ProjectAnswerResponse:
    """Approve or reject saving the suggested project action plan."""

    try:
        result = resume_project_investigation(
            project_id,
            workflow_id,
            data.approved,
        )
    except InvestigationWorkflowNotPendingError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workflow is not waiting for approval.",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return result