from typing import Optional, List
from pydantic import BaseModel

class DocumentUploadResponse(BaseModel):
    task_id: str
    document_id: str
    filename: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    document_id: Optional[str] = None
    filename: Optional[str] = None
    status: str  # QUEUED, PARSING, EMBEDDING, INDEXING, COMPLETED, FAILED
    progress: int = 0
    total_chunks: int = 0
    error: Optional[str] = ""

class DocumentItem(BaseModel):
    document_id: str
    filename: str
    chunk_count: int
    created_at: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentItem]
