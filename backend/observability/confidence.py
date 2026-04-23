"""
confidence.py
─────────────
Computes a retrieval-based confidence score for a RAG response.
No LLM call required — purely computed from retrieval metadata.

Score components:
  retrieval_score  — average cosine similarity of retrieved chunks (FAISS Inner Product)
                     Range: 0.0 – 1.0 (higher = more semantically similar chunks)
  source_count     — number of unique chunks/sources retrieved
  combined         — weighted final confidence

combined formula:
  0.70 * retrieval_score + 0.30 * clamp(source_count / 8, 0, 1)
  (more sources slightly boosts confidence, capped at 8 sources = full weight)
"""

from __future__ import annotations


def compute_confidence(chunks: list[dict]) -> dict:
    """
    Args:
        chunks: list of dicts with at least a 'score' key (FAISS cosine similarity).
                For MemGraph: items from RetrievalResult with type='rag_doc' or 'table'
                For Trad RAG: direct list from trad_vstore.search()

    Returns:
        {
          "retrieval_score": float,   # avg similarity (0-1)
          "source_count": int,
          "combined": float           # weighted confidence (0-1)
        }
    """
    if not chunks:
        return {"retrieval_score": 0.0, "source_count": 0, "combined": 0.0}

    scores = [c.get("score", 0.0) for c in chunks if isinstance(c.get("score"), (int, float))]

    retrieval_score = round(sum(scores) / len(scores), 4) if scores else 0.0
    source_count = len(chunks)

    # Normalize source count contribution (max meaningful at 8 sources)
    source_weight = min(source_count / 8.0, 1.0)

    combined = round(0.70 * retrieval_score + 0.30 * source_weight, 4)

    return {
        "retrieval_score": retrieval_score,
        "source_count": source_count,
        "combined": combined,
    }


def compute_confidence_from_memgraph_result(retrieval_items: list[dict]) -> dict:
    """
    Wrapper for MemGraph's RetrievalResult.items format.
    Only counts doc/table chunks (excludes memory/KG items which have fixed scores).
    """
    doc_items = [
        item for item in retrieval_items
        if item.get("type") in ("rag_doc", "table")
    ]
    if not doc_items:
        # Fall back to all items if no doc-type items
        doc_items = retrieval_items

    return compute_confidence(doc_items)
