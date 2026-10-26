"""Typed request and response shapes for project endpoints."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ProjectCreate(BaseModel):
    """Fields a client must provide when registering a project."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank.")
        return value


class ProjectResponse(BaseModel):
    """Fields the API returns after a project is registered."""

    id: UUID
    name: str
    description: str | None

from pydantic import model_validator


class ProjectUpdate(BaseModel):
    """Fields a client may choose to change in a project."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank_or_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Project name cannot be null.")
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank.")
        return value

    @model_validator(mode="after")
    def at_least_one_field_must_be_provided(self) -> "ProjectUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


