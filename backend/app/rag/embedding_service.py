"""Generate local text embeddings for DevMate retrieval."""

from functools import lru_cache

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model():
    """Load the embedding model once and reuse it within this process."""
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError(
            "FastEmbed is required. Install the backend dependencies with "
            "`python -m pip install -e .`."
        ) from exc

    return TextEmbedding(model_name=MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convert each input text into a numeric vector using a local model."""
    if not texts:
        return []

    model = _get_model()
    return [vector.tolist() for vector in model.embed(texts)]
