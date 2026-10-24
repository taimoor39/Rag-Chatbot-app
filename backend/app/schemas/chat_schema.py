from typing import List, Optional
from pydantic import BaseModel, Field

class MessageItem(BaseModel):
    role: str = Field(..., description="Role: 'user' or 'assistant' or 'system'")
    content: str = Field(..., description="Message text content")

class ChatRequest(BaseModel):
    message: str = Field(..., description="Current user query")
    conversation_history: List[MessageItem] = Field(default=[], description="Past messages in the conversation")
    doc_ids: Optional[List[str]] = Field(default=None, description="Optional document IDs to filter retrieval")

class SourceCitation(BaseModel):
    doc_id: str
    filename: str
    page_number: int
    score: float
    chunk_text: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceCitation] = []
