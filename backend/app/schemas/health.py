"""Typed API response contracts."""

from pydantic import BaseModel  # for data validation and response structure.


class HealthResponse(BaseModel):  # inherited/extended from BaseModel class
    status: str
    service: str  # attributes
