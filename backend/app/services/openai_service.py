import logging
from typing import List, Generator, Dict
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_embeddings_model() -> OpenAIEmbeddings:
    """Return LangChain OpenAIEmbeddings client."""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in .env")
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
    )

def get_chat_model(streaming: bool = True) -> ChatOpenAI:
    """Return LangChain ChatOpenAI client with streaming support."""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in .env")
    return ChatOpenAI(
        model=settings.CHAT_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
        temperature=0.3,
        streaming=streaming,
    )

def get_embedding(text: str) -> List[float]:
    """Generate a single text embedding vector using LangChain OpenAIEmbeddings."""
    model = get_embeddings_model()
    return model.embed_query(text)

def stream_chat_completion(messages: List[Dict[str, str]]) -> Generator[str, None, None]:
    """Stream response tokens using LangChain ChatOpenAI."""
    llm = get_chat_model(streaming=True)
    langchain_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))

    try:
        for chunk in llm.stream(langchain_messages):
            if chunk.content:
                yield str(chunk.content)
    except Exception as e:
        logger.error(f"LangChain chat stream error: {e}")
        yield f"\n[Error generating response: {str(e)}]"
