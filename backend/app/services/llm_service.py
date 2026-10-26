"""Local mock and OpenAI-backed language model integrations."""

import logging
import os

from app.rag.prompts import RAG_OUTPUT_PARSER, RAG_PROMPT
from langchain_core.exceptions import OutputParserException
from app.schemas.question import StructuredProjectAnswer

logger = logging.getLogger(__name__)


class LLMNotConfiguredError(Exception):
    """Raised when OpenAI mode is selected without an API key."""


class LLMConfigurationError(Exception):
    """Raised when an unsupported LLM mode is configured."""


class LLMProviderError(Exception):
    """Raised when the model provider cannot complete the request."""


def _mock_answer(question: str) -> str:
    """Return a predictable local answer without calling an external API."""
    normalized_question = question.lower()
    if "404" in normalized_question:
        return (
            "HTTP 404 Not Found means the server could not find the requested "
            "URL or resource. Check the URL, API route, or project ID. "
            "This is a local mock response; no external AI was called."
        )

    return (
        f"DevMate received your question: {question!r}. "
        "Local mock mode is active, so this is a fixed demo response; "
        "no external AI was called."
    )


def generate_answer(
    question: str,
    context: str | None = None,
) -> tuple[str, str]:
    """Generate a local demo answer or call OpenAI, depending on configuration."""
    mode = os.getenv("LLM_MODE", "mock").strip().lower()
    if mode == "mock":
        if context is not None:
            return (
                "Local mock mode retrieved project evidence, but it does not "
                "generate an AI answer. Review the source excerpts returned "
                "with this response.",
                "mock-llm",
            )
        return _mock_answer(question), "mock-llm"
    if mode != "openai":
        raise LLMConfigurationError

    try:
        from openai import OpenAI, OpenAIError
    except ImportError as exc:
        raise LLMProviderError from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMNotConfiguredError

    model = os.getenv("OPENAI_MODEL", "gpt-6-astra")
    client = OpenAI(api_key=api_key)
    try:
        if context is None:
            response = client.responses.create(model=model, input=question)
        else:
            prompt_messages = RAG_PROMPT.format_messages(
                question=question,
                context=context,
                format_instructions=RAG_OUTPUT_PARSER.get_format_instructions(),
            )
            response = client.responses.create(
                model=model,
                instructions=str(prompt_messages[0].content),
                input=str(prompt_messages[1].content),
            )
    except OpenAIError as exc:
        status_code = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)
        # Log diagnostic metadata only; never log the API key or question.
        logger.error(
            "OpenAI request failed: %s; status=%s; request_id=%s",
            type(exc).__name__,
            status_code,
            request_id,
        )
        raise LLMProviderError from exc

    return response.output_text, model


def generate_structured_project_answer(
    question: str,
    context: str,
) -> tuple[StructuredProjectAnswer, str]:
    """Return a validated structured answer for retrieved project evidence."""
    mode = os.getenv("LLM_MODE", "mock").strip().lower()
    if mode == "mock":
        return (
            StructuredProjectAnswer(
                answer=(
                    "Local mock mode retrieved project evidence. Review the cited "
                    "sources; no AI explanation was generated."
                ),
                suspected_cause=None,
                evidence_summary=(
                    "Matching project excerpts were retrieved, but mock mode does "
                    "not interpret them."
                ),
                confidence="low",
                suggested_next_steps=["Review the cited source excerpts."],
            ),
            "mock-llm",
        )
    if mode != "openai":
        raise LLMConfigurationError

    try:
        from openai import OpenAI, OpenAIError
    except ImportError as exc:
        raise LLMProviderError from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMNotConfiguredError

    model = os.getenv("OPENAI_MODEL", "gpt-6-astra")
    prompt_messages = RAG_PROMPT.format_messages(
        question=question,
        context=context,
        format_instructions=RAG_OUTPUT_PARSER.get_format_instructions(),
    )
    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model,
            instructions=str(prompt_messages[0].content),
            input=str(prompt_messages[1].content),
        )
    except OpenAIError as exc:
        status_code = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)
        logger.error(
            "OpenAI request failed: %s; status=%s; request_id=%s",
            type(exc).__name__,
            status_code,
            request_id,
        )
        raise LLMProviderError from exc

    try:
        structured_answer = RAG_OUTPUT_PARSER.parse(response.output_text)
    except OutputParserException as exc:
        logger.error("OpenAI response did not match the structured answer schema.")
        raise LLMProviderError from exc

    return structured_answer, model
