import os
import uuid
import shutil
import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.core.config import settings
from app.core.valkey_conn import ValkeyQueueManager
from app.services.qdrant_service import list_indexed_documents, delete_document_points
from app.schemas.document_schema import (
    DocumentUploadResponse,
    TaskStatusResponse,
    DocumentListResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docs", tags=["Documents"])

@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF document.
    Saves the file to local staging and delegates text extraction, embedding,
    and vector database indexing to the Valkey background queue.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF (.pdf) documents are supported."
        )

    # Check Valkey connectivity
    if not ValkeyQueueManager.check_health():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Valkey background queue service is currently unreachable. Make sure the Valkey docker container is running."
        )

    document_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    sanitized_filename = os.path.basename(file.filename)
    saved_file_name = f"{document_id}_{sanitized_filename}"
    file_path = settings.UPLOAD_DIR / saved_file_name

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save uploaded file: {str(e)}"
        )
    finally:
        await file.close()

    # Enqueue task in Valkey
    ValkeyQueueManager.enqueue_indexing_task(
        task_id=task_id,
        document_id=document_id,
        filename=sanitized_filename,
        file_path=str(file_path),
    )

    return DocumentUploadResponse(
        task_id=task_id,
        document_id=document_id,
        filename=sanitized_filename,
        status="QUEUED",
        message="Document uploaded successfully. Processing queued in Valkey."
    )

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Poll the status of an asynchronous PDF indexing task from Valkey.
    """
    status_data = ValkeyQueueManager.get_task_status(task_id)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task ID '{task_id}' not found."
        )

    return TaskStatusResponse(
        task_id=task_id,
        document_id=status_data.get("document_id"),
        filename=status_data.get("filename"),
        status=status_data.get("status", "UNKNOWN"),
        progress=int(status_data.get("progress", 0)),
        total_chunks=int(status_data.get("total_chunks", 0)),
        error=status_data.get("error", ""),
    )

@router.get("", response_model=DocumentListResponse)
async def get_documents():
    """
    List all documents currently indexed in the Qdrant vector database.
    """
    try:
        docs = list_indexed_documents()
        return DocumentListResponse(documents=docs)
    except Exception as e:
        logger.error(f"Error fetching document list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying vector database: {str(e)}"
        )

@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """
    Delete all vector points and metadata for a specific document from Qdrant.
    """
    try:
        delete_document_points(document_id)
        # Clean up files matching document_id in uploads directory
        for f in settings.UPLOAD_DIR.glob(f"{document_id}_*"):
            try:
                os.remove(f)
            except OSError:
                pass
        return {"message": f"Document '{document_id}' successfully deleted."}
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )
