import sys
import json
import time
import signal
import logging
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Ponytail Self-Healing: Auto-delegate to backend virtual environment if run with unactivated system Python
venv_py_win = backend_root / "venv" / "Scripts" / "python.exe"
venv_py_posix = backend_root / "venv" / "bin" / "python"
target_venv = venv_py_win if venv_py_win.exists() else (venv_py_posix if venv_py_posix.exists() else None)

if target_venv and Path(sys.executable).resolve() != target_venv.resolve():
    try:
        import pydantic_settings
    except ImportError:
        import subprocess
        sys.exit(subprocess.call([str(target_venv)] + sys.argv))

from app.core.config import settings
from app.core.valkey_conn import get_valkey_client, check_valkey_health
from app.workers.tasks import process_indexing_task

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ValkeyWorker] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

running = True

def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received. Finishing active jobs and exiting worker...")
    running = False

def start_worker():
    global running
    try:
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
    except (ValueError, AttributeError):
        # Ignore if running in a background thread or non-main interpreter
        pass

    logger.info("==================================================")
    logger.info("  🚀 Valkey RAG Background Queue Worker Started   ")
    logger.info(f"  Connected to Valkey at: {settings.VALKEY_HOST}:{settings.VALKEY_PORT}")
    logger.info(f"  Listening on Queue: '{settings.VALKEY_QUEUE_NAME}'")
    logger.info("==================================================")

    # Verify Valkey connectivity
    if not check_valkey_health():
        logger.error("Could not connect to Valkey. Ensure the Valkey docker container is running!")
        sys.exit(1)

    client = get_valkey_client()

    while running:
        try:
            # BRPOP blocks for up to 2 seconds waiting for incoming jobs
            task_item = client.brpop(settings.VALKEY_QUEUE_NAME, timeout=2)
            if not task_item:
                continue

            _, task_json = task_item
            task_data = json.loads(task_json)

            task_id = task_data.get("task_id")
            document_id = task_data.get("document_id")
            filename = task_data.get("filename")
            file_path = task_data.get("file_path")

            logger.info(f"Received indexing job: {task_id} (Doc: {filename})")
            process_indexing_task(
                task_id=task_id,
                document_id=document_id,
                filename=filename,
                file_path=file_path
            )

        except json.JSONDecodeError as e:
            logger.error(f"Malformed job payload received: {e}")
        except Exception as e:
            if running:
                logger.error(f"Unexpected worker error: {e}")
                time.sleep(1)

    logger.info("Valkey Worker stopped cleanly.")

if __name__ == "__main__":
    start_worker()
