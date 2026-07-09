"""
Convenience launcher: `python run.py`
Starts the API on http://localhost:8000 and serves the dashboard at
http://localhost:8000/app
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, app_dir="backend")
