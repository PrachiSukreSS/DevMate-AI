"""Request, answer, source, and history response shapes."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProjectQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank.")
        return value


class IssueInvestigationRequest(BaseModel):
    """Issue details submitted for a project-grounded investigation."""

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=4000)
    traceback: str | None = Field(default=None, max_length=12000)

    @field_validator("title", "description")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class AnswerSource(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    excerpt: str


class StructuredProjectAnswer(BaseModel):
    """Predictable analysis fields returned with a project-grounded answer."""

    answer: str
    suspected_cause: str | None = None
    evidence_summary: str
    confidence: Literal["low", "medium", "high"]
    suggested_next_steps: list[str]


class ApprovalDecision(BaseModel):
    """Human decision to store the suggested project action plan."""

    approved: bool


class ProjectAnswerResponse(BaseModel):
    interaction_id: UUID
    workflow_id: UUID | None = None
    planner_query: str | None = None
    approval_status: Literal["pending", "approved", "rejected"] | None = None
    action_plan_id: UUID | None = None
    answer: str
    model: str
    sources: list[AnswerSource]
    structured_answer: StructuredProjectAnswer | None = None


class QuestionHistoryItem(ProjectAnswerResponse):
    question: str
    created_at: str


class PendingInvestigationSummary(BaseModel):
    """A saved investigation currently waiting for a human decision."""

    workflow_id: UUID
    title: str
    response: ProjectAnswerResponse
    created_at: str
