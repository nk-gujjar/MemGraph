"""
Traditional RAG — Settings
Uses a completely separate SQLite DB and FAISS index directory from MemGraph
so the two approaches are fully isolated for comparison.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TradSettings(BaseSettings):
    COHERE_API_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"

    # Separate DB and FAISS dirs — isolated from MemGraph
    TRAD_DB_PATH: str = "./traditional_rag.db"
    TRAD_FAISS_DIR: str = "./faiss_trad"
    UPLOAD_DIR: str = "./uploads"          # shared upload folder, read-only

    # Models (same as MemGraph for fair comparison)
    CHAT_MODEL_FAST: str = "command-r-08-2024"
    CHAT_MODEL_QUALITY: str = "command-r-plus-08-2024"
    EMBEDDING_MODEL: str = "embed-english-v3.0"

    MAX_UPLOAD_SIZE_MB: int = 50
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    TOP_K: int = 8                          # number of chunks to retrieve

    # Short-term memory window
    SHORT_TERM_WINDOW: int = 6              # last N messages kept verbatim
    SUMMARY_TRIGGER: int = 12              # summarize when history exceeds this

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore",   # silently ignore MemGraph-specific env vars
    )

    @model_validator(mode="after")
    def resolve_paths(self):
        for field in ("TRAD_DB_PATH", "TRAD_FAISS_DIR", "UPLOAD_DIR"):
            value = getattr(self, field)
            if not os.path.isabs(value):
                setattr(self, field, str(PROJECT_ROOT / value))
        return self


trad_settings = TradSettings()
