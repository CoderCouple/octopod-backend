import logging
from functools import lru_cache

from app.settings import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = settings.qdrant_collection
VECTOR_SIZE = settings.embedding_dimension


@lru_cache(maxsize=1)
def get_qdrant_client():
    from qdrant_client import QdrantClient

    if settings.qdrant_url:
        # Qdrant Cloud mode
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=30,
        )
        logger.info("Connected to Qdrant Cloud: %s", settings.qdrant_url)
    else:
        # Local mode
        client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=30,
        )
        logger.info("Connected to local Qdrant: %s:%s", settings.qdrant_host, settings.qdrant_port)
    return client


async def ensure_collection() -> None:
    from qdrant_client.models import (
        Distance,
        HnswConfigDiff,
        ScalarQuantization,
        ScalarQuantizationConfig,
        ScalarType,
        VectorParams,
    )

    client = get_qdrant_client()
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)

    if not exists:
        logger.info(f"Creating Qdrant collection: {COLLECTION_NAME}")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            ),
        )
        logger.info(f"Collection {COLLECTION_NAME} created with HNSW + INT8 quantization")
    else:
        logger.info(f"Qdrant collection {COLLECTION_NAME} already exists")

    # Ensure payload indexes exist for filterable fields
    _ensure_payload_indexes(client)


def _ensure_payload_indexes(client) -> None:
    from qdrant_client.models import PayloadSchemaType

    keyword_fields = ["languages", "skills", "topics", "location", "company"]
    integer_fields = [
        "total_stars",
        "years_of_experience",
        "total_contributions",
        "total_followers",
        "total_hf_downloads",
    ]

    for field in keyword_fields:
        try:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # Index may already exist

    for field in integer_fields:
        try:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.INTEGER,
            )
        except Exception:
            pass  # Index may already exist
