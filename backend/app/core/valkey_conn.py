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

class ValkeyQueueManager:
    """Helper service to enqueue jobs and track status in Valkey."""

    @staticmethod
    def enqueue_indexing_task(task_id: str, document_id: str, filename: str, file_path: str) -> None:
        client = get_valkey_client()
        task_payload = {
            "task_id": task_id,
            "document_id": document_id,
            "filename": filename,
            "file_path": file_path,
        }
        # Set initial status in hash
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
        # Push to task queue
        client.lpush(settings.VALKEY_QUEUE_NAME, json.dumps(task_payload))
        logger.info(f"Enqueued indexing task {task_id} for file {filename}")

    @staticmethod
    def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
        client = get_valkey_client()
        status_data = client.hgetall(f"{settings.VALKEY_TASK_PREFIX}{task_id}")
        if not status_data:
            return None
        return status_data

    @staticmethod
    def update_task_status(task_id: str, updates: Dict[str, Any]) -> None:
        client = get_valkey_client()
        client.hset(f"{settings.VALKEY_TASK_PREFIX}{task_id}", mapping=updates)

    @staticmethod
    def check_health() -> bool:
        try:
            client = get_valkey_client()
            return bool(client.ping())
        except Exception as e:
            logger.error(f"Valkey health check failed: {e}")
            return False
