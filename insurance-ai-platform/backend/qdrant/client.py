"""Qdrant client factory and policy_knowledge collection setup."""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

from .models import COLLECTION_NAME, EMBEDDING_DIM


def get_client(url: str | None = None, path: str | None = None) -> QdrantClient:
    """Returns a QdrantClient.

    Pass `url` for a running Qdrant server, `path` for on-disk local
    storage, or neither for a transient in-memory instance (used in tests).
    """
    if url:
        return QdrantClient(url=url)
    if path:
        return QdrantClient(path=path)
    return QdrantClient(":memory:")


def ensure_collection(client: QdrantClient, collection_name: str = COLLECTION_NAME) -> None:
    """Creates the collection and its filterable payload indexes if missing."""
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    for field_name, schema in (
        ("plan_id", PayloadSchemaType.KEYWORD),
        ("state", PayloadSchemaType.KEYWORD),
        ("document_type", PayloadSchemaType.KEYWORD),
        ("effective_date_ts", PayloadSchemaType.INTEGER),
    ):
        client.create_payload_index(collection_name, field_name, field_schema=schema)
