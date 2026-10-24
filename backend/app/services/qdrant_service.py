import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from qdrant_client.http.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    FilterSelector,
)
from app.core.config import settings
from app.core.qdrant_conn import qdrant_client, ensure_collection_exists
from app.schemas.chat_schema import SourceCitation
from app.schemas.document_schema import DocumentItem

logger = logging.getLogger(__name__)

def upsert_document_chunks(
    document_id: str,
    filename: str,
    chunks: List[Dict[str, Any]],
    vectors: List[List[float]],
    batch_size: int = 100,
) -> int:
    """Upsert chunk vectors and their metadata into Qdrant."""
    ensure_collection_exists()

    points: List[PointStruct] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        point_id = str(uuid.uuid4())
        payload = {
            "document_id": document_id,
            "filename": filename,
            "page_number": chunk["page_number"],
            "chunk_index": chunk["chunk_index"],
            "text": chunk["text"],
            "created_at": timestamp,
        }
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    # Batch upsert
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        qdrant_client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=batch,
            wait=True,
        )

    logger.info(f"Upserted {len(points)} points for document {filename} (ID: {document_id})")
    return len(points)

def search_relevant_chunks(
    query_vector: List[float],
    top_k: int = settings.TOP_K_RETRIEVAL,
    doc_ids: Optional[List[str]] = None,
) -> List[SourceCitation]:
    """Search for the most relevant document chunks given a query vector."""
    ensure_collection_exists()

    query_filter = None
    if doc_ids and len(doc_ids) > 0:
        if len(doc_ids) == 1:
            query_filter = Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=doc_ids[0]))]
            )
        else:
            query_filter = Filter(
                must=[FieldCondition(key="document_id", match=MatchAny(any=doc_ids))]
            )

    try:
        # qdrant-client >= 1.10 provides query_points
        if hasattr(qdrant_client, "query_points"):
            results = qdrant_client.query_points(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            ).points
        else:
            results = qdrant_client.search(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
    except Exception as e:
        logger.error(f"Error querying Qdrant: {e}")
        return []

    citations: List[SourceCitation] = []
    for hit in results:
        payload = hit.payload or {}
        citations.append(
            SourceCitation(
                doc_id=str(payload.get("document_id", "")),
                filename=str(payload.get("filename", "Unknown Document")),
                page_number=int(payload.get("page_number", 1)),
                score=round(float(hit.score), 4),
                chunk_text=str(payload.get("text", "")),
            )
        )

    return citations

def list_indexed_documents() -> List[DocumentItem]:
    """Retrieve all unique documents currently indexed in the vector database."""
    ensure_collection_exists()

    docs_map: Dict[str, Dict[str, Any]] = {}
    offset = None

    while True:
        records, next_offset = qdrant_client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            scroll_filter=None,
            limit=250,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for record in records:
            payload = record.payload or {}
            doc_id = payload.get("document_id")
            if not doc_id:
                continue

            if doc_id not in docs_map:
                docs_map[doc_id] = {
                    "document_id": doc_id,
                    "filename": payload.get("filename", "Unknown"),
                    "chunk_count": 0,
                    "created_at": payload.get("created_at"),
                }
            docs_map[doc_id]["chunk_count"] += 1

        if next_offset is None:
            break
        offset = next_offset

    return [DocumentItem(**item) for item in docs_map.values()]

def delete_document_points(document_id: str) -> None:
    """Delete all chunks belonging to a document from Qdrant."""
    ensure_collection_exists()
    selector = FilterSelector(
        filter=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        )
    )
    qdrant_client.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=selector,
        wait=True,
    )
    logger.info(f"Deleted points for document_id: {document_id}")
