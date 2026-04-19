import os
import asyncio
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
from backend.config import settings
from backend.pipelines.ingest import process_document
from backend.db.sqlite import SessionLocal, UploadedFile

router = APIRouter(prefix="/api/sessions", tags=["upload"])

# simple in memory progress tracker
progress_tracker = {}

async def _ingest_background(session_id: str, file_path: str, filename: str):
    print(f"Background ingestion task started for {filename}...")
    if session_id not in progress_tracker:
        progress_tracker[session_id] = {}
        
    progress_tracker[session_id][filename] = "processing"
    
    try:
        results = await process_document(session_id, file_path, filename)
        progress_tracker[session_id][filename] = "completed"
        
        # update db
        db = SessionLocal()
        try:
            db_file = db.query(UploadedFile).filter(
                UploadedFile.session_id == session_id,
                UploadedFile.filename == filename
            ).first()
            if db_file:
                db_file.status = "completed"
                db_file.chunk_count = results.get("text_chunks", 0)
                db_file.table_count = results.get("tables_processed", 0)
                db.commit()
        finally:
            db.close()
            
    except Exception as e:
        progress_tracker[session_id][filename] = f"failed: {e}"
        print(f"Ingestion failed for {filename}: {e}")

@router.post("/{session_id}/upload")
async def upload_files(session_id: str, background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
    uploaded_info = []
    
    db = SessionLocal()
    try:
        for file in files:
            file_path = os.path.join(settings.UPLOAD_DIR, f"{session_id}_{file.filename}")
            
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
                
            db_file = UploadedFile(session_id=session_id, filename=file.filename, status="processing")
            db.add(db_file)
            db.commit()
            
            uploaded_info.append({"name": file.filename, "status": "processing"})
            
            # Queue ingestion
            background_tasks.add_task(_ingest_background, session_id, file_path, file.filename)
            
    finally:
        db.close()
        
    return {"session_id": session_id, "files": uploaded_info}

@router.get("/{session_id}/upload/progress")
async def get_upload_progress(session_id: str):
    async def event_generator():
        while True:
            if session_id in progress_tracker:
                yield {"data": str(progress_tracker[session_id])}
            
            # Stop condition if all are completed or failed
            if session_id in progress_tracker:
                all_done = all(v != "processing" for v in progress_tracker[session_id].values())
                if all_done:
                    yield {"data": str(progress_tracker[session_id])}
                    break
                    
            await asyncio.sleep(1)
            
    return EventSourceResponse(event_generator())

@router.get("/{session_id}/sources")
def get_sources(session_id: str):
    db = SessionLocal()
    try:
        files = db.query(UploadedFile).filter(UploadedFile.session_id == session_id).all()
        return [{
            "filename": f.filename,
            "status": f.status,
            "chunk_count": f.chunk_count,
            "table_count": f.table_count 
        } for f in files]
    finally:
        db.close()
