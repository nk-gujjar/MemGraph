import os

# Fix for OpenMP Apple Mac duplicate lib initialized error
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.sqlite import init_db
from backend.api.routes import sessions, upload
from backend.api import websocket
from backend.config import settings

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.FAISS_INDEX_DIR, exist_ok=True)

# Initialize DB
init_db()

app = FastAPI(title="MemGraph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(upload.router)
app.include_router(websocket.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
