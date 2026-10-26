"""HTTP endpoint for asking the configured language model a question."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import (
    LLMConfigurationError,
    LLMNotConfiguredError,
    LLMProviderError,
    generate_answer,
)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(data: ChatRequest) -> ChatResponse:
    """Ask the model one question and return its answer."""
    try:
        answer, model = generate_answer(data.question)
    except LLMConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM_MODE must be mock or openai.",
        )
    except LLMNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM is not configured. Set OPENAI_API_KEY in the server environment.",
        )
    except LLMProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM provider could not complete the request.",
        )

    return ChatResponse(answer=answer, model=model)

