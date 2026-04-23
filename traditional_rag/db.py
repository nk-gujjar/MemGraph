"""
Traditional RAG — Database Models
Own SQLite database (traditional_rag.db) separate from MemGraph's memgraph.db.

Tables:
  trad_sessions          → session-level stats
  trad_chunk_metadata    → FAISS index → chunk text mapping
  trad_chat_messages     → chat history (used for sliding-window memory)
  trad_uploaded_files    → ingestion status tracking
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

from traditional_rag.config import trad_settings

Base = declarative_base()


class TradSession(Base):
    __tablename__ = "trad_sessions"
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    message_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)


class TradChunkMetadata(Base):
    __tablename__ = "trad_chunk_metadata"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    filename = Column(String)
    page_number = Column(Integer, nullable=True)
    chunk_index = Column(Integer)
    text = Column(Text)


class TradChatMessage(Base):
    __tablename__ = "trad_chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    role = Column(String)   # "user" | "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


class TradChatSummary(Base):
    """Stores the rolling summary of older messages that were compressed."""
    __tablename__ = "trad_chat_summaries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, unique=True)
    summary = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)


class TradUploadedFile(Base):
    __tablename__ = "trad_uploaded_files"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    filename = Column(String)
    status = Column(String)
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


# ── Engine & helpers ──────────────────────────────────────────────────────────

engine = create_engine(
    f"sqlite:///{trad_settings.TRAD_DB_PATH}",
    connect_args={"check_same_thread": False},
)
TradSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_trad_db():
    Base.metadata.create_all(bind=engine)


def get_trad_db():
    db = TradSessionLocal()
    try:
        yield db
    finally:
        db.close()
