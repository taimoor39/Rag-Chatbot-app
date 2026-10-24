import json
import logging
from typing import List, Generator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.schemas.chat_schema import ChatRequest, ChatResponse, SourceCitation
from app.services.openai_service import get_chat_model
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
        "You are an expert AI assistant modeled after ChatGPT, powered by LangChain and Retrieval-Augmented Generation (RAG).\n"
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
    RAG Chat endpoint with real-time token streaming using LangChain LCEL and Server-Sent Events (SSE).
    Retrieves relevant PDF vectors via LangChain QdrantVectorStore and streams response tokens from ChatOpenAI.
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured in .env"
        )

    try:
        # Step 1: LangChain Qdrant similarity search
        citations = search_relevant_chunks(
            query=request.message,
            top_k=settings.TOP_K_RETRIEVAL,
            doc_ids=request.doc_ids,
        )

        # Step 2: Build LangChain message history
        system_prompt = build_system_prompt(citations)
        langchain_history = []
        for prev in request.conversation_history[-10:]:
            if prev.role == "user":
                langchain_history.append(HumanMessage(content=prev.content))
            elif prev.role == "assistant":
                langchain_history.append(AIMessage(content=prev.content))

        # Step 3: Modern LangChain LCEL Chain
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ])

        llm = get_chat_model(streaming=True)
        chain = prompt | llm | StrOutputParser()

        def event_generator() -> Generator[str, None, None]:
            # First send sources metadata
            sources_data = [c.model_dump() for c in citations]
            yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

            # Stream tokens through LangChain chain
            for chunk in chain.stream({
                "system_prompt": system_prompt,
                "history": langchain_history,
                "question": request.message,
            }):
                yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"

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
        logger.error(f"LangChain chat streaming error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat generation failed: {str(e)}"
        )

@router.post("", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """
    Synchronous RAG Chat endpoint powered by LangChain LCEL.
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured in .env"
        )

    try:
        citations = search_relevant_chunks(
            query=request.message,
            top_k=settings.TOP_K_RETRIEVAL,
            doc_ids=request.doc_ids,
        )

        system_prompt = build_system_prompt(citations)
        langchain_history = []
        for prev in request.conversation_history[-10:]:
            if prev.role == "user":
                langchain_history.append(HumanMessage(content=prev.content))
            elif prev.role == "assistant":
                langchain_history.append(AIMessage(content=prev.content))

        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ])

        llm = get_chat_model(streaming=False)
        chain = prompt | llm | StrOutputParser()

        answer = chain.invoke({
            "system_prompt": system_prompt,
            "history": langchain_history,
            "question": request.message,
        })

        return ChatResponse(answer=answer, sources=citations)

    except Exception as e:
        logger.error(f"LangChain synchronous chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}"
        )
