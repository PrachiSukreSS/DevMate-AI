"""Validated handoff schemas for investigation workflow roles."""

from pydantic import BaseModel, Field

from app.schemas.document import RetrievedChunk


class InvestigationPlan(BaseModel):
    """Bounded search instructions handed from the planner to the researcher."""

    search_query: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1)
    traceback_signals: list[str] = Field(default_factory=list, max_length=2)


class EvidenceReview(BaseModel):
    """Reviewer decision and the evidence allowed to reach report generation."""

    passed: bool
    notes: str
    accepted_chunks: list[RetrievedChunk]
