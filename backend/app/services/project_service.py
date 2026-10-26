"""Project operations backed by SQLite."""

from uuid import UUID, uuid4

import sqlite3

from app.db.database import get_connection
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate


def _to_project(row: sqlite3.Row) -> ProjectResponse:
    """Convert one database row into the API's response model."""
    return ProjectResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
    )


def create_project(data: ProjectCreate) -> ProjectResponse:
    """Save a new project row and return it."""
    project = ProjectResponse(
        id=uuid4(),
        name=data.name,
        description=data.description,
    )
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO projects (id, name, description) VALUES (?, ?, ?)",
            (str(project.id), project.name, project.description),
        )
    return project


def list_projects() -> list[ProjectResponse]:
    """Return all project rows, ordered by name."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, description FROM projects ORDER BY name"
        ).fetchall()
    return [_to_project(row) for row in rows]


def get_project(project_id: UUID) -> ProjectResponse | None:
    """Return one project, or None when the ID is not in the database."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name, description FROM projects WHERE id = ?",
            (str(project_id),),
        ).fetchone()
    return _to_project(row) if row is not None else None


def delete_project(project_id: UUID) -> bool:
    """Delete a project row; return False when no row matched the ID."""
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM projects WHERE id = ?",
            (str(project_id),),
        )
        return cursor.rowcount > 0


def update_project(project_id: UUID, changes: ProjectUpdate) -> ProjectResponse | None:
    """Update supplied fields; return None when the project does not exist."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name, description FROM projects WHERE id = ?",
            (str(project_id),),
        ).fetchone()
        if row is None:
            return None

        project = _to_project(row)
        updated_project = project.model_copy(
            update=changes.model_dump(exclude_unset=True)
        )
        connection.execute(
            "UPDATE projects SET name = ?, description = ? WHERE id = ?",
            (
                updated_project.name,
                updated_project.description,
                str(project_id),
            ),
        )
    return updated_project

