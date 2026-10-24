import logging
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from app.core.config import settings

logger = logging.getLogger(__name__)

qdrant_client = QdrantClient(
    host=settings.QDRANT_HOST,
    port=settings.QDRANT_PORT,
    api_key=settings.QDRANT_API_KEY,
    timeout=10,
)

def ensure_collection_exists() -> None:
    """Create the Qdrant collection for document chunks if it does not exist."""
    try:
        exists = qdrant_client.collection_exists(collection_name=settings.QDRANT_COLLECTION_NAME)
        if not exists:
            logger.info(f"Creating Qdrant collection '{settings.QDRANT_COLLECTION_NAME}'...")
            qdrant_client.create_collection(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Qdrant collection '{settings.QDRANT_COLLECTION_NAME}' created successfully.")
        else:
            logger.info(f"Qdrant collection '{settings.QDRANT_COLLECTION_NAME}' already exists.")
    except Exception as e:
        logger.error(f"Error ensuring Qdrant collection exists: {e}")
        raise e

def check_health() -> bool:
    try:
        collections = qdrant_client.get_collections()
        return collections is not None
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return False
