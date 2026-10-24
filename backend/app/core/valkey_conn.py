import json
import logging
from typing import Any, Dict, Optional
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Valkey connection pool (Redis wire protocol compatible)
valkey_pool = redis.ConnectionPool(
    host=settings.VALKEY_HOST,
    port=settings.VALKEY_PORT,
    db=settings.VALKEY_DB,
    password=settings.VALKEY_PASSWORD,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
)

def get_valkey_client() -> redis.Redis:
    """Return a redis-py client connected to Valkey."""
    return redis.Redis(connection_pool=valkey_pool)

def enqueue_indexing_task(task_id: str, document_id: str, filename: str, file_path: str) -> None:
    """Enqueue indexing job and set initial status hash in Valkey."""
    client = get_valkey_client()
    task_payload = {
        "task_id": task_id,
        "document_id": document_id,
        "filename": filename,
        "file_path": file_path,
    }
    client.hset(
        f"{settings.VALKEY_TASK_PREFIX}{task_id}",
        mapping={
            "task_id": task_id,
            "document_id": document_id,
            "filename": filename,
            "status": "QUEUED",
            "progress": 0,
            "total_chunks": 0,
            "error": "",
        }
    )
    client.lpush(settings.VALKEY_QUEUE_NAME, json.dumps(task_payload))
    logger.info(f"Enqueued indexing task {task_id} for file {filename}")

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve indexing task status from Valkey hash."""
    client = get_valkey_client()
    status_data = client.hgetall(f"{settings.VALKEY_TASK_PREFIX}{task_id}")
    return status_data if status_data else None

def update_task_status(task_id: str, updates: Dict[str, Any]) -> None:
    """Update fields in Valkey task status hash."""
    client = get_valkey_client()
    client.hset(f"{settings.VALKEY_TASK_PREFIX}{task_id}", mapping=updates)

def check_valkey_health() -> bool:
    """Check Valkey connection health."""
    try:
        client = get_valkey_client()
        return bool(client.ping())
    except Exception as e:
        logger.error(f"Valkey health check failed: {e}")
        return False
