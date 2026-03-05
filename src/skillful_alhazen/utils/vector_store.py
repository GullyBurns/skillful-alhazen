"""
Qdrant vector store utility for Alhazen semantic search.

Manages the 'alhazen_papers' collection with cosine similarity.
Point IDs are stable UUIDs derived from TypeDB paper IDs.
"""

import os
import uuid

QDRANT_COLLECTION = "alhazen_papers"
from skillful_alhazen.utils.embeddings import VECTOR_DIM  # single source of truth


def get_qdrant_client():
    """Connect to Qdrant using QDRANT_HOST / QDRANT_PORT env vars."""
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        raise ImportError("qdrant-client not installed. Run: uv sync --all-extras")

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)


def ensure_collection(client, dim: int = VECTOR_DIM) -> None:
    """Create the alhazen_papers collection if it does not exist."""
    from qdrant_client.models import Distance, VectorParams

    existing = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def paper_id_to_uuid(paper_id: str) -> str:
    """Derive a stable UUID from a TypeDB paper ID string."""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
    return str(uuid.uuid5(namespace, paper_id))


def upsert_papers(client, papers: list[dict]) -> int:
    """
    Upsert paper vectors into Qdrant.

    Each paper dict must have:
        paper_id (str), vector (list[float]),
        title (str), collection_ids (list[str]),
        doi (str, optional), year (int, optional)

    Returns number of points upserted.
    """
    from qdrant_client.models import PointStruct

    points = []
    for p in papers:
        point_id = paper_id_to_uuid(p["paper_id"])
        payload = {
            "paper_id": p["paper_id"],
            "collection_ids": p.get("collection_ids", []),
            "title": p.get("title", ""),
            "doi": p.get("doi", ""),
            "year": p.get("year"),
        }
        points.append(PointStruct(id=point_id, vector=p["vector"], payload=payload))

    if points:
        client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    return len(points)


def get_existing_paper_ids(client, paper_ids: list[str]) -> set[str]:
    """Return the subset of paper_ids that already have points in Qdrant."""
    point_ids = [paper_id_to_uuid(pid) for pid in paper_ids]
    results = client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=point_ids,
        with_payload=True,
    )
    return {r.payload["paper_id"] for r in results}


def search_similar(
    client,
    query_vector: list[float],
    collection_id: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search for similar papers by vector similarity.

    Args:
        client: Qdrant client
        query_vector: Embedding of the search query
        collection_id: Optional TypeDB collection ID to filter results
        limit: Maximum number of results

    Returns:
        List of dicts with paper_id, title, doi, year, score
    """
    from qdrant_client.models import FieldCondition, Filter, MatchAny

    query_filter = None
    if collection_id:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="collection_ids",
                    match=MatchAny(any=[collection_id]),
                )
            ]
        )

    response = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )

    return [
        {
            "paper_id": r.payload.get("paper_id", ""),
            "title": r.payload.get("title", ""),
            "doi": r.payload.get("doi", ""),
            "year": r.payload.get("year"),
            "score": round(r.score, 4),
        }
        for r in response.points
    ]


def get_collection_vectors(client, collection_id: str) -> list[dict]:
    """
    Retrieve all points belonging to a TypeDB collection.

    Returns list of dicts with paper_id, title, vector (list[float]).
    Scrolls through all pages automatically.
    """
    from qdrant_client.models import FieldCondition, Filter, MatchAny

    query_filter = Filter(
        must=[
            FieldCondition(
                key="collection_ids",
                match=MatchAny(any=[collection_id]),
            )
        ]
    )

    all_points = []
    offset = None

    while True:
        results, next_offset = client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=query_filter,
            limit=256,
            offset=offset,
            with_vectors=True,
            with_payload=True,
        )
        all_points.extend(results)
        if next_offset is None:
            break
        offset = next_offset

    return [
        {
            "paper_id": p.payload.get("paper_id", ""),
            "title": p.payload.get("title", ""),
            "doi": p.payload.get("doi", ""),
            "year": p.payload.get("year"),
            "vector": p.vector,
        }
        for p in all_points
    ]
