import os
import logging
from app.core.valkey_conn import ValkeyQueueManager
from app.services.pdf_parser import extract_chunks_from_pdf
from app.services.openai_service import get_embeddings_batch
from app.services.qdrant_service import upsert_document_chunks

logger = logging.getLogger(__name__)

def process_indexing_task(task_id: str, document_id: str, filename: str, file_path: str) -> bool:
    """
    Executes the PDF ingestion pipeline in the background:
      1. Parse PDF pages into text chunks
      2. Generate OpenAI vector embeddings
      3. Upsert embeddings into Qdrant vector database
      4. Update progress and status in Valkey
    """
    try:
        logger.info(f"Starting task {task_id}: Parsing PDF {filename}")
        ValkeyQueueManager.update_task_status(task_id, {
            "status": "PARSING",
            "progress": 20,
            "error": "",
        })

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Step 1: Parse chunks
        chunks = extract_chunks_from_pdf(file_path)
        if not chunks:
            raise ValueError("No extractable text found in the uploaded PDF document.")

        total_chunks = len(chunks)
        logger.info(f"Task {task_id}: Parsed {total_chunks} chunks. Generating embeddings...")

        # Step 2: Embeddings
        ValkeyQueueManager.update_task_status(task_id, {
            "status": "EMBEDDING",
            "progress": 50,
            "total_chunks": total_chunks,
        })

        texts = [chunk["text"] for chunk in chunks]
        embeddings = get_embeddings_batch(texts)

        # Step 3: Upsert into Qdrant
        logger.info(f"Task {task_id}: Upserting vectors into Qdrant collection...")
        ValkeyQueueManager.update_task_status(task_id, {
            "status": "INDEXING",
            "progress": 80,
        })

        upsert_document_chunks(
            document_id=document_id,
            filename=filename,
            chunks=chunks,
            vectors=embeddings,
        )

        # Step 4: Mark Complete
        ValkeyQueueManager.update_task_status(task_id, {
            "status": "COMPLETED",
            "progress": 100,
            "total_chunks": total_chunks,
        })
        logger.info(f"Task {task_id} COMPLETED successfully for {filename}")
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Task {task_id} FAILED for {filename}: {error_msg}")
        ValkeyQueueManager.update_task_status(task_id, {
            "status": "FAILED",
            "error": error_msg,
        })
        return False
