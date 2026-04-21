"""
Traditional RAG — Vector Store
Separate FAISS index (faiss_trad/trad_text.index) from MemGraph.
Only a single text index — no table index, no memory namespace.
"""

import os
import faiss
import numpy as np
import cohere

from traditional_rag.config import trad_settings
from traditional_rag.db import TradSessionLocal, TradChunkMetadata


class TradVectorStore:
    def __init__(self):
        self.cohere_client = cohere.Client(api_key=trad_settings.COHERE_API_KEY)
        os.makedirs(trad_settings.TRAD_FAISS_DIR, exist_ok=True)
        self.index_path = os.path.join(trad_settings.TRAD_FAISS_DIR, "trad_text.index")
        self.dimension = 1024  # embed-english-v3.0
        self.index = self._load_or_create()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load_or_create(self):
        if os.path.exists(self.index_path):
            return faiss.read_index(self.index_path)
        return faiss.IndexFlatIP(self.dimension)

    def _save(self):
        faiss.write_index(self.index, self.index_path)

    def _embed(self, texts: list[str], input_type: str) -> np.ndarray:
        if not texts:
            return np.array([])
        response = self.cohere_client.embed(
            texts=texts,
            model=trad_settings.EMBEDDING_MODEL,
            input_type=input_type,
        )
        embeddings = np.array(response.embeddings).astype("float32")
        faiss.normalize_L2(embeddings)
        return embeddings

    # ── Public API ────────────────────────────────────────────────────────────

    def add_texts(self, session_id: str, texts: list[str], metadatas: list[dict]):
        if not texts:
            return
        embeddings = self._embed(texts, "search_document")
        db = TradSessionLocal()
        try:
            start_id = self.index.ntotal
            self.index.add(embeddings)
            for i, (text, meta) in enumerate(zip(texts, metadatas)):
                db.add(
                    TradChunkMetadata(
                        id=start_id + i,
                        session_id=session_id,
                        filename=meta.get("filename", ""),
                        page_number=meta.get("page_number"),
                        chunk_index=meta.get("chunk_index", i),
                        text=text,
                    )
                )
            db.commit()
            self._save()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def search(self, session_id: str, query: str, top_k: int = None) -> list[dict]:
        """Return top-K chunks for this session sorted by cosine similarity."""
        top_k = top_k or trad_settings.TOP_K
        if self.index.ntotal == 0:
            return []

        q_emb = self._embed([query], "search_query")
        search_k = min(self.index.ntotal, max(top_k * 20, 500))
        distances, indices = self.index.search(q_emb, search_k)

        results = []
        db = TradSessionLocal()
        try:
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    continue
                chunk = (
                    db.query(TradChunkMetadata)
                    .filter(
                        TradChunkMetadata.id == int(idx),
                        TradChunkMetadata.session_id == session_id,
                    )
                    .first()
                )
                if chunk:
                    results.append(
                        {
                            "text": chunk.text,
                            "filename": chunk.filename,
                            "page_number": chunk.page_number,
                            "score": float(dist),
                        }
                    )
                if len(results) >= top_k:
                    break
        finally:
            db.close()

        return results


trad_vstore = TradVectorStore()
