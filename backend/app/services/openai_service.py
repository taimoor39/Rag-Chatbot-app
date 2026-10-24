import logging
from typing import List, Generator, Dict, Any
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_openai_client() -> OpenAI:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set. Please set it in your .env file.")
    return OpenAI(api_key=settings.OPENAI_API_KEY)

def get_embedding(text: str) -> List[float]:
    """Generate a single text embedding vector using OpenAI."""
    client = get_openai_client()
    clean_input = text.replace("\n", " ")
    response = client.embeddings.create(
        input=[clean_input],
        model=settings.EMBEDDING_MODEL
    )
    return response.data[0].embedding

def get_embeddings_batch(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    """Generate embeddings for multiple texts in batches."""
    client = get_openai_client()
    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = [t.replace("\n", " ") for t in texts[i:i + batch_size]]
        response = client.embeddings.create(
            input=batch,
            model=settings.EMBEDDING_MODEL
        )
        # Preserve order of embeddings
        sorted_data = sorted(response.data, key=lambda x: x.index)
        all_embeddings.extend([item.embedding for item in sorted_data])

    return all_embeddings

def stream_chat_completion(messages: List[Dict[str, str]]) -> Generator[str, None, None]:
    """
    Stream tokens from OpenAI chat completion.
    Yields string deltas as they arrive.
    """
    client = get_openai_client()
    try:
        response = client.chat.completions.create(
            model=settings.CHAT_MODEL,
            messages=messages,
            stream=True,
            temperature=0.3,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        logger.error(f"OpenAI chat completion error: {e}")
        yield f"\n[Error generating response: {str(e)}]"
