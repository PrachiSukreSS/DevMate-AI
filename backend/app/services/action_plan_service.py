"""Read approved action plans saved for a project."""

import json
from uuid import UUID

from app.db.database import get_connection
from app.schemas.action_plan import ActionPlanResponse


def list_action_plans(project_id: UUID) -> list[ActionPlanResponse] | None:
    """Return a project's saved plans, or None when the project is unknown."""
    with get_connection() as connection:
        project = connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (str(project_id),),
        ).fetchone()
        if project is None:
            return None

        rows = connection.execute(
            """
            SELECT id, workflow_id, title, actions_json, created_at
            FROM project_action_plans
            WHERE project_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (str(project_id),),
        ).fetchall()

    return [
        ActionPlanResponse(
            id=row["id"],
            workflow_id=row["workflow_id"],
            title=row["title"],
            actions=json.loads(row["actions_json"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]
