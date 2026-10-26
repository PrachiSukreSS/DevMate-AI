"""Show how local embeddings compare related and unrelated text."""

import math

from app.rag.embedding_service import embed_texts


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Measure the angle-based similarity between two numeric vectors."""
    dot_product = sum(a * b for a, b in zip(left, right))
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    if left_length == 0 or right_length == 0:
        return 0.0
    return dot_product / (left_length * right_length)


texts = [
    "The server returned HTTP 404 because the requested page was not found.",
    "The requested URL does not exist on the server.",
    "To bake bread, mix flour with water and yeast.",
]
vectors = embed_texts(texts)

print(f"Embedding dimensions: {len(vectors[0])}")
print(
    "Related-text similarity: "
    f"{cosine_similarity(vectors[0], vectors[1]):.3f}"
)
print(
    "Unrelated-text similarity: "
    f"{cosine_similarity(vectors[0], vectors[2]):.3f}"
)
