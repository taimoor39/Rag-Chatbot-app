import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "RAG Chatbot with Valkey & Qdrant"
    DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # OpenAI Settings
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    CHAT_MODEL: str = "gpt-4o-mini"

    # Valkey (Redis-compatible) Settings
    VALKEY_HOST: str = "localhost"
    VALKEY_PORT: int = 6379
    VALKEY_DB: int = 0
    VALKEY_PASSWORD: str | None = None
    VALKEY_QUEUE_NAME: str = "rag_indexing_queue"
    VALKEY_TASK_PREFIX: str = "task:"

    # Qdrant Settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "rag_documents"

    # RAG Settings
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    TOP_K_RETRIEVAL: int = 4

    # File Storage
    UPLOAD_DIR: Path = BASE_DIR / "uploads"

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR.parent / ".env")),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure uploads directory exists
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
