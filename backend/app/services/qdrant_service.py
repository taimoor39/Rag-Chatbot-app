import logging
from typing import List, Dict, Any, Optional
from qdrant_client.http.models import (
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from app.core.config import settings
from app.core.qdrant_conn import qdrant_client, ensure_collection_exists
from app.services.openai_service import get_embeddings_model
from app.schemas.chat_schema import SourceCitation
from app.schemas.document_schema import DocumentItem

logger = logging.getLogger(__name__)

def get_vector_store() -> QdrantVectorStore:
    """Return LangChain QdrantVectorStore instance."""
    ensure_collection_exists()
    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        embedding=get_embeddings_model(),
    )

def upsert_langchain_documents(documents: List[Document], batch_size: int = 100) -> int:
    """
    Upsert LangChain Document objects into Qdrant using QdrantVectorStore.
    Populates both 'page_content' and 'text' keys for universal backward compatibility.
    """
    if not documents:
        return 0

    vector_store = get_vector_store()
    total_added = 0

    # Ensure cross-compatibility keys exist in metadata
    for doc in documents:
        doc.metadata["text"] = doc.page_content
        doc.metadata["page_content"] = doc.page_content

    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        ids = vector_store.add_documents(batch)
        total_added += len(ids)

    logger.info(f"LangChain QdrantVectorStore upserted {total_added} documents")
    return total_added

def search_relevant_chunks(
    query: str,
    top_k: int = settings.TOP_K_RETRIEVAL,
    doc_ids: Optional[List[str]] = None,
) -> List[SourceCitation]:
    """
    Search relevant document chunks using vector similarity in Qdrant.
    Robustly extracts text and metadata across both LangChain and legacy payload schemas.
    """
    ensure_collection_exists()
    query_vector = get_embeddings_model().embed_query(query)

    query_filter = None
    if doc_ids and len(doc_ids) > 0:
        conditions = []
        for d in doc_ids:
            conditions.append(FieldCondition(key="document_id", match=MatchValue(value=d)))
            conditions.append(FieldCondition(key="metadata.document_id", match=MatchValue(value=d)))
        query_filter = Filter(should=conditions)

    try:
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
        logger.error(f"Vector search error: {e}")
        return []

    citations: List[SourceCitation] = []
    for hit in results:
        payload = hit.payload or {}
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

        # Universal extraction: handles 'text', 'page_content', and nested metadata
        chunk_text = (
            payload.get("text")
            or payload.get("page_content")
            or meta.get("text")
            or meta.get("page_content")
            or ""
        )
        if not chunk_text:
            continue

        filename = (
            payload.get("filename")
            or meta.get("filename")
            or "Unknown Document"
        )
        page_number = int(
            payload.get("page_number")
            or meta.get("page_number")
            or 1
        )
        doc_id = str(
            payload.get("document_id")
            or meta.get("document_id")
            or ""
        )

        citations.append(
            SourceCitation(
                doc_id=doc_id,
                filename=filename,
                page_number=page_number,
                score=round(float(hit.score), 4),
                chunk_text=chunk_text,
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
            meta = payload.get("metadata", {})
            doc_id = meta.get("document_id") or payload.get("document_id")
            if not doc_id:
                continue

            filename = meta.get("filename") or payload.get("filename", "Unknown")
            created_at = meta.get("created_at") or payload.get("created_at")

            if doc_id not in docs_map:
                docs_map[doc_id] = {
                    "document_id": doc_id,
                    "filename": filename,
                    "chunk_count": 0,
                    "created_at": created_at,
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
            should=[
                FieldCondition(key="metadata.document_id", match=MatchValue(value=document_id)),
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            ]
        )
    )
    qdrant_client.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=selector,
        wait=True,
    )
    logger.info(f"Deleted points for document_id: {document_id}")
