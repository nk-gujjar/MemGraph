import os
import faiss
import numpy as np
import cohere
from backend.config import settings
from backend.db.sqlite import SessionLocal, ChunkMetadata, TableMetadata

class VectorStore:
    def __init__(self):
        self.cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)
        self.text_index_path = os.path.join(settings.FAISS_INDEX_DIR, "text.index")
        self.table_index_path = os.path.join(settings.FAISS_INDEX_DIR, "table.index")
        
        self.dimension = 1024 # embed-english-v3.0 dimension
        
        self.text_index = self._load_or_create_index(self.text_index_path)
        self.table_index = self._load_or_create_index(self.table_index_path)

    def _load_or_create_index(self, path):
        if os.path.exists(path):
            return faiss.read_index(path)
        else:
            return faiss.IndexFlatIP(self.dimension)

    def _save_indexes(self):
        faiss.write_index(self.text_index, self.text_index_path)
        faiss.write_index(self.table_index, self.table_index_path)

    def _get_embeddings(self, texts: list[str], input_type: str) -> np.ndarray:
        if not texts:
            return np.array([])
        # input_type is either "search_document" or "search_query"
        response = self.cohere_client.embed(
            texts=texts,
            model=settings.EMBEDDING_MODEL,
            input_type=input_type
        )
        embeddings = np.array(response.embeddings).astype('float32')
        # Normalize vectors for IP (which becomes Cosine Similarity)
        faiss.normalize_L2(embeddings)
        return embeddings

    def add_texts(self, session_id: str, texts: list[str], metadatas: list[dict]):
        if not texts:
            return
        embeddings = self._get_embeddings(texts, "search_document")
        
        db = SessionLocal()
        try:
            start_id = self.text_index.ntotal
            self.text_index.add(embeddings)
            
            for i, (text, meta) in enumerate(zip(texts, metadatas)):
                db_chunk = ChunkMetadata(
                    id=start_id + i,
                    session_id=session_id,
                    filename=meta.get("filename", ""),
                    page_number=meta.get("page_number"),
                    chunk_index=meta.get("chunk_index", getattr(meta, "chunk_index", 0)),
                    text=text
                )
                db.add(db_chunk)
            db.commit()
            self._save_indexes()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def add_table_summaries(self, session_id: str, summaries: list[str], raw_markdowns: list[str], metadatas: list[dict]):
        if not summaries:
            return
        embeddings = self._get_embeddings(summaries, "search_document")
        
        db = SessionLocal()
        try:
            start_id = self.table_index.ntotal
            self.table_index.add(embeddings)
            
            for i, (summary, raw_md, meta) in enumerate(zip(summaries, raw_markdowns, metadatas)):
                db_table = TableMetadata(
                    id=start_id + i,
                    session_id=session_id,
                    filename=meta.get("filename", ""),
                    page_number=meta.get("page_number"),
                    table_index=meta.get("table_index", 0),
                    raw_markdown=raw_md,
                    summary=summary
                )
                db.add(db_table)
            db.commit()
            self._save_indexes()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def search_text(self, session_id: str, query: str, top_k: int = 5):
        if self.text_index.ntotal == 0:
            return []
            
        q_emb = self._get_embeddings([query], "search_query")
        # To filter by session, we retrieve many more than top_k and filter locally
        # Since FAISS doesn't do native metadata filtering easily
        search_k = min(self.text_index.ntotal, max(top_k * 20, 1000))
        distances, indices = self.text_index.search(q_emb, search_k)
        
        print(f"[Search] Globally found {len(indices[0])} neighbors for text search.")
        
        results = []
        db = SessionLocal()
        try:
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    continue
                # Fetch metadata
                chunk = db.query(ChunkMetadata).filter(ChunkMetadata.id == int(idx), ChunkMetadata.session_id == session_id).first()
                if chunk:
                    results.append({
                        "id": chunk.id,
                        "text": chunk.text,
                        "filename": chunk.filename,
                        "page_number": chunk.page_number,
                        "score": float(dist)
                    })
                if len(results) >= top_k:
                    break
        finally:
            db.close()
            
        print(f"[Search] Filtered down to {len(results)} chunks for session {session_id}")
        return results

    def get_all_session_chunks(self, session_id: str, limit: int = 50):
        """Directly fetches chunks from SQLite for a session (bypassing FAISS). Good for summaries."""
        db = SessionLocal()
        try:
            chunks = db.query(ChunkMetadata).filter(ChunkMetadata.session_id == session_id).limit(limit).all()
            return [{
                "id": c.id,
                "text": c.text,
                "filename": c.filename,
                "page_number": c.page_number,
                "score": 1.0 # default score for non-semantic retrieval
            } for c in chunks]
        finally:
            db.close()

    def search_tables(self, session_id: str, query: str, top_k: int = 3):
        if self.table_index.ntotal == 0:
            return []
            
        q_emb = self._get_embeddings([query], "search_query")
        search_k = min(self.table_index.ntotal, max(top_k * 20, 500))
        distances, indices = self.table_index.search(q_emb, search_k)
        
        results = []
        db = SessionLocal()
        try:
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    continue
                tbl = db.query(TableMetadata).filter(TableMetadata.id == int(idx), TableMetadata.session_id == session_id).first()
                if tbl:
                    results.append({
                        "id": tbl.id,
                        "raw_markdown": tbl.raw_markdown,
                        "summary": tbl.summary,
                        "filename": tbl.filename,
                        "page_number": tbl.page_number,
                        "score": float(dist)
                    })
                if len(results) >= top_k:
                    break
        finally:
            db.close()
        return results

vstore = VectorStore()
