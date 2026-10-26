"""Small deterministic planner and reviewer roles used by the local workflow."""

import re

from app.schemas.agent import EvidenceReview, InvestigationPlan
from app.schemas.document import RetrievedChunk

_EXCEPTION_PATTERN = re.compile(r"\b([A-Za-z_]\w*(?:Error|Exception))\s*:")
_STATUS_PATTERN = re.compile(
    r"\bHTTP(?:/\d(?:\.\d)?)?\s*(\d{3})\b|\bstatus(?:_code)?\s*[:=]\s*(\d{3})\b",
    re.IGNORECASE,
)


def _safe_traceback_signals(traceback: str | None) -> list[str]:
    """Extract only exception class names and HTTP codes, never raw trace text."""
    if not traceback:
        return []

    signals: list[str] = []
    for line in reversed(traceback.splitlines()):
        exception_match = _EXCEPTION_PATTERN.search(line)
        status_match = _STATUS_PATTERN.search(line)
        if exception_match and exception_match.group(1) not in signals:
            signals.append(exception_match.group(1))
        if status_match:
            status_signal = f"HTTP {status_match.group(1) or status_match.group(2)}"
            if status_signal not in signals:
                signals.append(status_signal)
        if len(signals) == 2:
            break
    return signals

def plan_document_search(
    title: str,
    description: str,
    traceback: str | None = None,
) -> InvestigationPlan:
    """Build a bounded query from the issue plus safe traceback clues."""
    issue_question = f"Issue title: {title}\nDescription: {description}"
    signals = _safe_traceback_signals(traceback)
    # Keep specific title and error clues before less-specific description text.
    query_parts = [title, *signals, description]
    search_query = " ".join(" ".join(query_parts).split())[:200]
    return InvestigationPlan(
        search_query=search_query,
        question=issue_question,
        traceback_signals=signals,
    )


def review_retrieved_evidence(
    chunks: list[RetrievedChunk],
    minimum_score: float,
    maximum_chunks: int = 3,
) -> EvidenceReview:
    """Reject empty, below-threshold, or duplicate evidence before reporting."""
    if not chunks:
        return EvidenceReview(
            passed=True,
            notes="No matching evidence was found; the report must say so.",
            accepted_chunks=[],
        )
    if len(chunks) > maximum_chunks:
        return EvidenceReview(
            passed=False,
            notes="The researcher returned more chunks than the allowed limit.",
            accepted_chunks=[],
        )

    seen: set[tuple[str, int]] = set()
    for chunk in chunks:
        chunk_key = (str(chunk.document_id), chunk.chunk_index)
        if chunk_key in seen:
            return EvidenceReview(
                passed=False,
                notes="The researcher returned duplicate evidence chunks.",
                accepted_chunks=[],
            )
        seen.add(chunk_key)
        if not chunk.content.strip():
            return EvidenceReview(
                passed=False,
                notes="A retrieved chunk has no source text.",
                accepted_chunks=[],
            )
        if chunk.score < minimum_score:
            return EvidenceReview(
                passed=False,
                notes="A retrieved chunk is below the configured relevance threshold.",
                accepted_chunks=[],
            )
    return EvidenceReview(
        passed=True,
        notes="All retrieved chunks passed the evidence checks.",
        accepted_chunks=chunks,
    )
