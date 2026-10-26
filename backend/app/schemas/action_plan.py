"""Response shape for an approved project action plan."""

from uuid import UUID

from pydantic import BaseModel


class ActionPlanResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    title: str
    actions: list[str]
    created_at: str
