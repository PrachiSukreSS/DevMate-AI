"""HTTP endpoints for registering projects."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def register_project(data: ProjectCreate) -> ProjectResponse:
    """Validate project details, create a record, and return it to the client."""
    return create_project(data)


@router.get("", response_model=list[ProjectResponse])
def get_projects() -> list[ProjectResponse]:
    """Return all projects currently stored by the service."""
    return list_projects()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_by_id(project_id: UUID) -> ProjectResponse:
    """Return one project or a 404 response when it does not exist."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project(project_id: UUID) -> None:
    """Delete one project, or return 404 when its ID is unknown."""
    deleted = delete_project(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )


@router.patch("/{project_id}", response_model=ProjectResponse)
def edit_project(project_id: UUID, changes: ProjectUpdate) -> ProjectResponse:
    """Update supplied project fields, or return 404 when missing."""
    project = update_project(project_id, changes)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project

