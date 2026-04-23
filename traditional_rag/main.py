"""
Traditional RAG — Standalone FastAPI Application
Runs on port 8001 (MemGraph runs on 8000).

Start with:
    ./run_trad.sh
or:
    uvicorn traditional_rag.main:app --reload --port 8001

Routes mounted:
  /api/sessions/*     ← frontend-compatible (same paths as MemGraph)
  /ws/{session_id}    ← frontend-compatible WebSocket
  /trad/api/sessions/* ← namespaced (for when sharing server with MemGraph)
  /trad/ws/{session_id} ← namespaced WebSocket
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"   # macOS OpenMP fix

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from traditional_rag.config import trad_settings
from traditional_rag.db import init_trad_db
from traditional_rag.sessions import router as sessions_router, trad_router as trad_sessions_router
from traditional_rag.upload import router as upload_router, trad_router as trad_upload_router
from traditional_rag.websocket import router as ws_router

# Ensure directories exist
os.makedirs(trad_settings.TRAD_FAISS_DIR, exist_ok=True)
os.makedirs(trad_settings.UPLOAD_DIR, exist_ok=True)

# Init isolated DB
init_trad_db()

app = FastAPI(
    title="Traditional RAG API",
    description="Baseline traditional RAG for comparison with MemGraph architecture.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend-compatible routes (same paths as MemGraph → proxy works without changes)
app.include_router(sessions_router)
app.include_router(upload_router)

# Namespaced routes (for shared-server mode)
app.include_router(trad_sessions_router)
app.include_router(trad_upload_router)

# WebSocket — registers both /ws/{id} and /trad/ws/{id}
app.include_router(ws_router)


@app.get("/health")
def health():
    return {"status": "ok", "approach": "traditional_rag", "port": 8001}
