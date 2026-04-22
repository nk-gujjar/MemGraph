import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

# Project root is the parent of the backend/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    COHERE_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    
    SQLITE_DB_PATH: str = "./memgraph.db"
    FAISS_INDEX_DIR: str = "./faiss_indexes"
    UPLOAD_DIR: str = "./uploads"

    # Models
    CHAT_MODEL_FAST: str = "command-r-08-2024"
    CHAT_MODEL_QUALITY: str = "command-r-plus-08-2024"
    EMBEDDING_MODEL: str = "embed-english-v3.0"
    
    MAX_UPLOAD_SIZE_MB: int = 50
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    
    TOP_K_TEXT: int = 10
    TOP_K_TABLE: int = 5
    TOP_K_MEMORY: int = 5

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"))

    @model_validator(mode="after")
    def resolve_paths(self):
        """Resolve any relative paths against PROJECT_ROOT so they work
        regardless of the working directory uvicorn is launched from."""
        for field in ("SQLITE_DB_PATH", "FAISS_INDEX_DIR", "UPLOAD_DIR"):
            value = getattr(self, field)
            if not os.path.isabs(value):
                setattr(self, field, str(PROJECT_ROOT / value))
        return self

settings = Settings()
