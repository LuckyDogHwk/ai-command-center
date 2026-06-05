from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from .engine import KnowledgeEngine
    from .llm import deepseek_enabled, deepseek_model
    from .models import KnowledgeDocument, RunRequest, RunResponse
except ImportError:
    from engine import KnowledgeEngine
    from llm import deepseek_enabled, deepseek_model
    from models import KnowledgeDocument, RunRequest, RunResponse


FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(title="AI Command Center", version="1.0.0")
engine = KnowledgeEngine()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/status")
def status() -> dict[str, int | str | bool]:
    return {
        **engine.status(),
        "llm_enabled": deepseek_enabled(),
        "llm_model": deepseek_model(),
    }


@app.post("/api/knowledge")
def add_knowledge(document: KnowledgeDocument) -> dict[str, int | str]:
    engine.add_document(document)
    return {"message": "knowledge indexed", **engine.status()}


@app.post("/api/run", response_model=RunResponse)
def run(payload: RunRequest) -> RunResponse:
    return engine.run(payload)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8010,
        reload=True,
        app_dir=str(PROJECT_ROOT),
        reload_dirs=[str(PROJECT_ROOT)],
    )
