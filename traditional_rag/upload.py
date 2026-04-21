"""
Traditional RAG — Upload Route

Exposes at BOTH:
  /api/sessions/{id}/upload         ← frontend-compatible (standalone port 8001)
  /trad/api/sessions/{id}/upload    ← namespaced (shared-server mode)

SSE-based progress polling matches the MemGraph frontend's EventSource client.
"""

import os
import asyncio
import json
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from sse_starlette.sse import EventSourceResponse

from traditional_rag.config import trad_settings
from traditional_rag.ingest import trad_ingest
from traditional_rag.db import TradSessionLocal, TradUploadedFile

# session_id -> {filename: status_str}
_progress: dict[str, dict] = {}


async def _ingest_bg(session_id: str, file_path: str, filename: str):
    _progress.setdefault(session_id, {})[filename] = "processing"
    try:
        result = await trad_ingest(session_id, file_path, filename)
        # Must be exactly "completed" for the frontend's status check
        _progress[session_id][filename] = "completed"
    except Exception as e:
        _progress.setdefault(session_id, {})[filename] = f"failed: {e}"
        print(f"[TradUpload] Ingestion failed for {filename}: {e}")


async def _upload_handler(
    session_id: str,
    background_tasks: BackgroundTasks,
    files,
):
    uploaded = []
    os.makedirs(trad_settings.UPLOAD_DIR, exist_ok=True)
    for file in files:
        file_path = os.path.join(
            trad_settings.UPLOAD_DIR, f"trad_{session_id}_{file.filename}"
        )
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        _progress.setdefault(session_id, {})[file.filename] = "processing"
        background_tasks.add_task(_ingest_bg, session_id, file_path, file.filename)
        uploaded.append({"filename": file.filename, "status": "processing"})
    return {"session_id": session_id, "files": uploaded}


def _sources_handler(session_id: str):
    db = TradSessionLocal()
    try:
        files = (
            db.query(TradUploadedFile)
            .filter(TradUploadedFile.session_id == session_id)
            .all()
        )
        return [
            {
                "filename": f.filename,
                "status": f.status,
                "chunk_count": f.chunk_count,
                "table_count": 0,  # Traditional RAG doesn't process tables separately
            }
            for f in files
        ]
    finally:
        db.close()


def _sse_progress_generator(session_id: str):
    """SSE generator — mirrors MemGraph's upload progress SSE."""
    async def event_generator():
        while True:
            progress = _progress.get(session_id, {})
            yield {"data": json.dumps(progress)}

            # Stop when all files are done (completed or failed)
            if progress:
                all_done = all(v != "processing" for v in progress.values())
                if all_done:
                    yield {"data": json.dumps(progress)}
                    break

            await asyncio.sleep(1)

    return event_generator


# ── /api/sessions — frontend-compatible (standalone port 8001) ────────────────
router = APIRouter(prefix="/api/sessions", tags=["trad-upload"])


@router.post("/{session_id}/upload")
async def trad_upload(
    session_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    return await _upload_handler(session_id, background_tasks, files)


@router.get("/{session_id}/upload/progress")
async def trad_upload_progress(session_id: str):
    return EventSourceResponse(_sse_progress_generator(session_id)())


@router.get("/{session_id}/sources")
def trad_sources(session_id: str):
    return _sources_handler(session_id)


# ── /trad/api/sessions — namespaced (shared-server mode) ─────────────────────
trad_router = APIRouter(prefix="/trad/api/sessions", tags=["trad-upload"])


@trad_router.post("/{session_id}/upload")
async def trad_upload_prefixed(
    session_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    return await _upload_handler(session_id, background_tasks, files)


@trad_router.get("/{session_id}/upload/progress")
async def trad_upload_progress_prefixed(session_id: str):
    return EventSourceResponse(_sse_progress_generator(session_id)())


@trad_router.get("/{session_id}/sources")
def trad_sources_prefixed(session_id: str):
    return _sources_handler(session_id)
