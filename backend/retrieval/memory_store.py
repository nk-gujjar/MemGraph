from backend.db.sqlite import SessionLocal, EventMemory, ChatMessage, GlobalKnowledge
from backend.retrieval.vector_store import vstore
from backend.retrieval.kg_store import kg_store
import cohere
from backend.config import settings
import json

from backend.llm_config import llm_client

class MemoryStore:
    def __init__(self):
        self.cohere_client = llm_client.cohere

    # --- Persistent Chat History ---
    def add_message(self, session_id: str, role: str, content: str):
        db = SessionLocal()
        try:
            msg = ChatMessage(session_id=session_id, role=role, content=content)
            db.add(msg)
            db.commit()
        finally:
            db.close()

    def get_last_messages(self, session_id: str, limit: int = 10) -> list:
        db = SessionLocal()
        try:
            msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.desc()).limit(limit).all()
            # Return in chronological order
            return [{"role": m.role, "content": m.content} for m in reversed(msgs)]
        finally:
            db.close()

    # --- Global Knowledge (Cross-Session) ---
    def add_global_knowledge(self, knowledge_type: str, content: str):
        db = SessionLocal()
        try:
            kn = GlobalKnowledge(type=knowledge_type, content=content)
            db.add(kn)
            db.commit()
        finally:
            db.close()

    def get_all_global_knowledge(self) -> list[dict]:
        db = SessionLocal()
        try:
            kn = db.query(GlobalKnowledge).all()
            return [{"type": k.type, "content": k.content} for k in kn]
        finally:
            db.close()

    # --- Long Term Memory (using vstore with 'memory' namespace) ---
    def add_long_term_memory(self, session_id: str, content: str):
        # Reusing text index, marking filename as __memory__
        vstore.add_texts(
            session_id=session_id,
            texts=[content],
            metadatas=[{"filename": "__memory__"}]
        )

    def search_long_term_memory(self, session_id: str, query: str, top_k: int = 4):
        # Latency optimization: skip if no memory exists for this session
        db = SessionLocal()
        from backend.db.sqlite import ChunkMetadata
        try:
            has_mem = db.query(ChunkMetadata).filter(ChunkMetadata.session_id == session_id, ChunkMetadata.filename == "__memory__").first()
            if not has_mem:
                return []
        finally:
            db.close()
            
        # Retrieve text chunks and filter for __memory__
        all_results = vstore.search_text(session_id, query, top_k=top_k*5)
        memory_results = [r for r in all_results if r["filename"] == "__memory__"]
        return memory_results[:top_k]

    # --- Event Memory (Session Specific) ---
    def add_event_memory(self, session_id: str, event_type: str, content: str):
        db = SessionLocal()
        try:
            event = EventMemory(session_id=session_id, event_type=event_type, content=content)
            db.add(event)
            db.commit()
        finally:
            db.close()

    def get_event_memory(self, session_id: str) -> list[dict]:
        db = SessionLocal()
        try:
            events = db.query(EventMemory).filter(EventMemory.session_id == session_id).all()
            return [{"type": e.event_type, "content": e.content} for e in events]
        finally:
            db.close()

    # --- KG Triples Extraction & Query ---
    def extract_and_query_kg(self, session_id: str, query: str) -> list[dict]:
        # Extract named entities from the query to find relevant KG fragments
        prompt = f"Extract named entities (people, models, organizations, concepts) from the following query and return as a JSON array of strings: {query}"
        try:
            response = self.cohere_client.chat(
                message=prompt,
                model=settings.CHAT_MODEL_FAST
            )
            
            import re
            match = re.search(r'\[(.*?)\]', response.text, re.DOTALL)
            entities = []
            if match:
                try:
                    entities = json.loads(f"[{match.group(1)}]")
                except:
                    pass
            
            if not entities:
                return []
                
            return kg_store.query_triples(session_id, entities)
        except Exception as e:
            print(f"Failed to query KG: {e}")
            return []

memory_store = MemoryStore()
