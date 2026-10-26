"""HTTP routes for reading project action plans."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.action_plan import ActionPlanResponse
from app.services.action_plan_service import list_action_plans

router = APIRouter(prefix="/projects", tags=["action plans"])


@router.get("/{project_id}/action-plans", response_model=list[ActionPlanResponse])
def get_project_action_plans(project_id: UUID) -> list[ActionPlanResponse]:
    """List action plans saved after a human approved them."""
    plans = list_action_plans(project_id)
    if plans is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return plans
