"""Routes used to check whether the API process is responding."""  # docstring

from fastapi import APIRouter  # to create seperate route files for diff modules

from app.schemas.health import HealthResponse  # import models like pydantic

router = APIRouter(tags=["health"])  # create router's instance


# its decorator (when GET req send on /health run following fn )
@router.get("/health", response_model=HealthResponse)
# schema strictly follows define format of HealthResponse model, if not it will throw error
def get_health() -> HealthResponse:  # type hinting, return type is HealthResponse model
    """Return a small, predictable status response."""  # endpoint description in swagger ui
    return HealthResponse(status="ok", service="devmate-api")  # return a HealthResponse object with the specified status and service
