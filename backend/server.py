import sys
from pathlib import Path
import uvicorn

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Ponytail Self-Healing: Auto-delegate to backend virtual environment if run with unactivated system Python
venv_py_win = backend_dir / "venv" / "Scripts" / "python.exe"
venv_py_posix = backend_dir / "venv" / "bin" / "python"
target_venv = venv_py_win if venv_py_win.exists() else (venv_py_posix if venv_py_posix.exists() else None)

if target_venv and Path(sys.executable).resolve() != target_venv.resolve():
    try:
        import pydantic_settings
        import uvicorn
    except ImportError:
        import subprocess
        sys.exit(subprocess.call([str(target_venv)] + sys.argv))

import uvicorn
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
