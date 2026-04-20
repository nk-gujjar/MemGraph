import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import settings

Base = declarative_base()

class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    message_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)

class ChunkMetadata(Base):
    __tablename__ = "chunk_metadata"
    # To map integer ID from FAISS text index back to metadata
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    filename = Column(String)
    page_number = Column(Integer, nullable=True)
    chunk_index = Column(Integer)
    text = Column(Text) # storing the chunk text

class TableMetadata(Base):
    __tablename__ = "table_metadata"
    # To map integer ID from FAISS table index to raw markdown
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    filename = Column(String)
    page_number = Column(Integer, nullable=True)
    table_index = Column(Integer)
    raw_markdown = Column(Text)
    summary = Column(Text)

class EventMemory(Base):
    __tablename__ = "event_memory"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    event_type = Column(String) # user_preference, user_goal, important_fact
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class KGTriple(Base):
    __tablename__ = "kg_triples"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    subject = Column(String, index=True)
    predicate = Column(String)
    object_ = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    filename = Column(String)
    description = Column(String, nullable=True)
    status = Column(String)
    chunk_count = Column(Integer, default=0)
    table_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

# Database Setup
engine = create_engine(
    f"sqlite:///{settings.SQLITE_DB_PATH}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
