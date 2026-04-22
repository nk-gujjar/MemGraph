"""
Traditional RAG — Ingestion Pipeline

Strategy: Recursive chunking ONLY (RecursiveCharacterTextSplitter).
No strategy classification, no table index, no KG extraction.

Documents are stored in the Traditional RAG's own FAISS index and SQLite DB.
"""

import asyncio
import time
from pathlib import Path

from unstructured.partition.auto import partition
from unstructured.documents.elements import Table as UnstructuredTable
from langchain_text_splitters import RecursiveCharacterTextSplitter

from traditional_rag.config import trad_settings
from traditional_rag.vector_store import trad_vstore
from traditional_rag.db import TradSessionLocal, TradUploadedFile


async def trad_ingest(session_id: str, file_path: str, filename: str) -> dict:
    """
    Ingest a document for Traditional RAG:
      1. Partition with unstructured (fast strategy)
      2. Strip tables — text only for traditional RAG
      3. Recursive character splitting
      4. Embed + store in trad FAISS + trad SQLite (with rate-limiting)

    Returns: { "chunks": int, "latency_ms": float }
    """
    start = time.time()
    print(f"\n[TradIngest] Starting ingestion: {filename} (session={session_id})")

    try:
        # 1. Partition
        elements = await asyncio.to_thread(
            partition, file_path, strategy="fast"
        )
        print(f"[TradIngest] Partitioned into {len(elements)} elements.")

        # 2. Extract text elements only (skip tables for simplicity)
        text_elements = [
            el for el in elements
            if not isinstance(el, UnstructuredTable)
            and not (hasattr(el, "metadata") and getattr(el.metadata, "text_as_html", None))
        ]

        full_text = "\n\n".join([str(el) for el in text_elements if str(el).strip()])

        if not full_text.strip():
            print("[TradIngest] No text content found.")
            _update_status(session_id, filename, "no_content", 0)
            return {"chunks": 0, "latency_ms": 0}

        # 3. Recursive chunking
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=trad_settings.CHUNK_SIZE,
            chunk_overlap=trad_settings.CHUNK_OVERLAP,
        )
        chunks = splitter.split_text(full_text)
        print(f"[TradIngest] Created {len(chunks)} chunks via recursive splitting.")

        # 4. Build metadata
        texts = chunks
        metadatas = [
            {"filename": filename, "page_number": None, "chunk_index": i}
            for i in range(len(chunks))
        ]

        # 5. Embed + store (with rate-limiting)
        await asyncio.to_thread(trad_vstore.add_texts, session_id, texts, metadatas)

        latency_ms = (time.time() - start) * 1000
        print(f"[TradIngest] Done — {len(chunks)} chunks in {latency_ms:.1f}ms")

        _update_status(session_id, filename, "completed", len(chunks))
        return {"chunks": len(chunks), "latency_ms": round(latency_ms, 2)}

    except Exception as e:
        print(f"[TradIngest] CRITICAL FAILURE for {filename}: {e}")
        _update_status(session_id, filename, f"failed: {str(e)}", 0)
        raise e


def _update_status(session_id: str, filename: str, status: str, chunk_count: int):
    db = TradSessionLocal()
    try:
        row = (
            db.query(TradUploadedFile)
            .filter(
                TradUploadedFile.session_id == session_id,
                TradUploadedFile.filename == filename,
            )
            .first()
        )
        if row:
            row.status = status
            row.chunk_count = chunk_count
        else:
            db.add(
                TradUploadedFile(
                    session_id=session_id,
                    filename=filename,
                    status=status,
                    chunk_count=chunk_count,
                )
            )
        db.commit()
    finally:
        db.close()
