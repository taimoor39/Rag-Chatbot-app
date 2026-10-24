import logging
from pathlib import Path
from app.core.valkey_conn import update_task_status
from app.services.pdf_parser import extract_documents_from_pdf
from app.services.qdrant_service import upsert_langchain_documents

logger = logging.getLogger(__name__)

def process_indexing_task(task_id: str, document_id: str, filename: str, file_path: str) -> bool:
    """
    Executes the PDF ingestion pipeline using LangChain:
      1. Parse PDF pages and split with LangChain RecursiveCharacterTextSplitter
      2. Generate vector embeddings and upsert into Qdrant using QdrantVectorStore
      3. Track progress and status in Valkey
    """
    try:
        logger.info(f"Starting task {task_id}: Parsing PDF {filename} via LangChain")
        update_task_status(task_id, {
            "status": "PARSING",
            "progress": 20,
            "error": "",
        })

        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Step 1: LangChain extraction and chunking
        documents = extract_documents_from_pdf(
            file_path=file_path,
            document_id=document_id,
            filename=filename,
        )
        if not documents:
            raise ValueError("No extractable text found in the uploaded PDF document.")

        total_chunks = len(documents)
        logger.info(f"Task {task_id}: Extracted {total_chunks} documents. Embedding & indexing with LangChain...")

        # Step 2: LangChain QdrantVectorStore upsert (generates OpenAI embeddings + stores)
        update_task_status(task_id, {
            "status": "INDEXING",
            "progress": 70,
            "total_chunks": total_chunks,
        })

        upsert_langchain_documents(documents)

        # Step 3: Complete
        update_task_status(task_id, {
            "status": "COMPLETED",
            "progress": 100,
            "total_chunks": total_chunks,
        })
        logger.info(f"Task {task_id} COMPLETED successfully via LangChain for {filename}")
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Task {task_id} FAILED for {filename}: {error_msg}")
        update_task_status(task_id, {
            "status": "FAILED",
            "error": error_msg,
        })
        return False
