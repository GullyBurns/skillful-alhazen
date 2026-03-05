"""
Voyage AI embedding utility for Alhazen semantic search.

Wraps the voyageai client with batching and standard defaults.
"""

import os

VOYAGE_MODEL = "voyage-4-large"
VOYAGE_BATCH_SIZE = 128
VECTOR_DIM = 1024  # voyage-4-large default


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """
    Embed a list of texts using Voyage AI voyage-3-lite.

    Args:
        texts: List of strings to embed.
        input_type: "document" for corpus texts, "query" for search queries.

    Returns:
        List of 1024-dim float vectors, one per input text.
    """
    try:
        import voyageai
    except ImportError:
        raise ImportError("voyageai not installed. Run: uv sync --all-extras")

    api_key = os.getenv("VOYAGE_API_KEY", "")
    if not api_key:
        raise ValueError("VOYAGE_API_KEY environment variable not set")

    client = voyageai.Client(api_key=api_key)
    all_embeddings = []

    for i in range(0, len(texts), VOYAGE_BATCH_SIZE):
        batch = texts[i : i + VOYAGE_BATCH_SIZE]
        result = client.embed(batch, model=VOYAGE_MODEL, input_type=input_type)
        all_embeddings.extend(result.embeddings)

    return all_embeddings
