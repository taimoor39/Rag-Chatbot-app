import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.valkey_conn import ValkeyQueueManager
from app.core.qdrant_conn import ensure_collection_exists, check_health as check_qdrant_health
from app.api.routes_docs import router as docs_router
from app.api.routes_chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Initializing RAG Chatbot backend services...")
    
    # Check Valkey
    valkey_ok = ValkeyQueueManager.check_health()
    if valkey_ok:
        logger.info(f"✓ Valkey connected successfully at {settings.VALKEY_HOST}:{settings.VALKEY_PORT}")
    else:
        logger.warning(f"⚠ Could not connect to Valkey at {settings.VALKEY_HOST}:{settings.VALKEY_PORT}. Is Docker running?")

    # Check Qdrant and initialize collection
    qdrant_ok = check_qdrant_health()
    if qdrant_ok:
        logger.info(f"✓ Qdrant connected successfully at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        try:
            ensure_collection_exists()
        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collection: {e}")
    else:
        logger.warning(f"⚠ Could not connect to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}. Is Docker running?")

    yield

    logger.info("Shutting down RAG Chatbot backend services...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Full-stack ChatGPT with RAG, Valkey Background Queue, and Qdrant Vector DB",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(docs_router)
app.include_router(chat_router)

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check reporting status of Valkey and Qdrant services."""
    return {
        "status": "healthy",
        "valkey_connected": ValkeyQueueManager.check_health(),
        "qdrant_connected": check_qdrant_health(),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "collection": settings.QDRANT_COLLECTION_NAME,
        "embedding_model": settings.EMBEDDING_MODEL,
        "chat_model": settings.CHAT_MODEL,
    }

# Serve frontend static assets if available
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", tags=["Frontend"])
    async def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "Frontend index.html not yet built"}
