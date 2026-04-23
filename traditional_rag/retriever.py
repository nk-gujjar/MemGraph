"""
Traditional RAG — Retriever
Pure FAISS cosine-similarity search. No intent detection, no query
rephrasing, no KG, no event memory, no re-ranking.
"""

import asyncio
from traditional_rag.vector_store import trad_vstore
from traditional_rag.config import trad_settings


async def trad_retrieve(
    query: str,
    session_id: str,
    top_k: int = None,
) -> list[dict]:
    """
    Retrieve top-K document chunks via FAISS vector search.

    Returns a list of dicts:
      [{ "text": ..., "filename": ..., "page_number": ..., "score": ... }, ...]
    """
    top_k = top_k or trad_settings.TOP_K
    results = await asyncio.to_thread(
        trad_vstore.search,
        session_id,
        query,
        top_k,
    )
    return results
