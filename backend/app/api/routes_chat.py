import json
import logging
from typing import List, Generator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.schemas.chat_schema import ChatRequest, ChatResponse, SourceCitation
from app.services.openai_service import get_embedding, stream_chat_completion, get_openai_client
from app.services.qdrant_service import search_relevant_chunks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])

def build_system_prompt(citations: List[SourceCitation]) -> str:
    """Construct an augmented system prompt containing retrieved context."""
    if not citations:
        return (
            "You are an intelligent RAG assistant modeled after ChatGPT. "
            "No specific document context was found for this query in the vector database. "
            "Please answer the user's question politely using your general knowledge, "
            "and inform the user that no specific indexed document references were found."
        )

    context_blocks = []
    for idx, c in enumerate(citations, start=1):
        context_blocks.append(
            f"--- SOURCE [{idx}] ---\n"
            f"Document: {c.filename}\n"
            f"Page: {c.page_number}\n"
            f"Content: {c.chunk_text}\n"
        )

    joined_context = "\n".join(context_blocks)

    return (
        "You are an expert AI assistant modeled after ChatGPT, powered by Retrieval-Augmented Generation (RAG).\n"
        "Use the following retrieved document excerpts to answer the user's question accurately.\n"
        "Guidelines:\n"
        "1. Prioritize facts from the provided sources.\n"
        "2. When stating facts from the context, reference the source document name and page number.\n"
        "3. If the context does not contain enough information to answer completely, acknowledge what is missing.\n"
        "4. Format your output cleanly with markdown, bullet points, and code blocks where helpful.\n\n"
        f"--- CONTEXT BEGIN ---\n{joined_context}\n--- CONTEXT END ---"
    )

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    RAG Chat endpoint with real-time token streaming via Server-Sent Events (SSE).
    Retrieves relevant PDF vectors from Qdrant and streams response tokens from OpenAI.
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured in .env"
        )

    try:
        # Step 1: Query embedding
        query_vector = get_embedding(request.message)

        # Step 2: Vector retrieval from Qdrant
        citations = search_relevant_chunks(
            query_vector=query_vector,
            top_k=settings.TOP_K_RETRIEVAL,
            doc_ids=request.doc_ids,
        )

        # Step 3: Build messages payload
        system_prompt = build_system_prompt(citations)
        messages = [{"role": "system", "content": system_prompt}]

        # Append previous conversation history (up to last 10 messages for context)
        for prev in request.conversation_history[-10:]:
            messages.append({"role": prev.role, "content": prev.content})

        # Append current user query
        messages.append({"role": "user", "content": request.message})

        def event_generator() -> Generator[str, None, None]:
            # First send sources metadata
            sources_data = [c.model_dump() for c in citations]
            yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

            # Stream LLM tokens
            for token in stream_chat_completion(messages):
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

            # Signal stream completion
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        logger.error(f"Chat streaming error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat generation failed: {str(e)}"
        )

@router.post("", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """
    Standard non-streaming RAG Chat endpoint.
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured in .env"
        )

    try:
        query_vector = get_embedding(request.message)
        citations = search_relevant_chunks(
            query_vector=query_vector,
            top_k=settings.TOP_K_RETRIEVAL,
            doc_ids=request.doc_ids,
        )

        system_prompt = build_system_prompt(citations)
        messages = [{"role": "system", "content": system_prompt}]

        for prev in request.conversation_history[-10:]:
            messages.append({"role": prev.role, "content": prev.content})

        messages.append({"role": "user", "content": request.message})

        client = get_openai_client()
        res = client.chat.completions.create(
            model=settings.CHAT_MODEL,
            messages=messages,
            temperature=0.3,
        )
        answer = res.choices[0].message.content or ""

        return ChatResponse(answer=answer, sources=citations)

    except Exception as e:
        logger.error(f"Synchronous chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}"
        )
