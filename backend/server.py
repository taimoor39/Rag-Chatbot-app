import sys
from pathlib import Path
import uvicorn

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings

if __name__ == "__main__":
    print("==================================================")
    print(f"  🚀 Starting RAG FastAPI Server")
    print(f"  URL: http://localhost:{settings.APP_PORT}")
    print(f"  API Docs: http://localhost:{settings.APP_PORT}/docs")
    print("==================================================")
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
