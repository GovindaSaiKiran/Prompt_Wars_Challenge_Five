import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path for robust absolute imports
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import FastAPI application instance
from app.main import app  # noqa: E402

if __name__ == "__main__":
    import uvicorn

    raw_port = os.environ.get("PORT", "10000").strip()
    try:
        port = int(raw_port)
    except ValueError:
        port = 10000

    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting EventPrice API on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
