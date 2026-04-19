from backend.db.sqlite import SessionLocal, EventMemory
from backend.retrieval.vector_store import vstore
from backend.retrieval.kg_store import kg_store
import cohere
from backend.config import settings
import json

class MemoryStore:
    def __init__(self):
        # In-memory circular buffer for last 6 messages
        self.short_term_memory = {}
        self.cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)

    # --- Short Term Memory ---
    def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self.short_term_memory:
            self.short_term_memory[session_id] = []
        
        self.short_term_memory[session_id].append({"role": role, "content": content})
        
        # Keep last 6 messages max
        if len(self.short_term_memory[session_id]) > 6:
            self.short_term_memory[session_id] = self.short_term_memory[session_id][-6:]

    def get_last_messages(self, session_id: str) -> list:
        return self.short_term_memory.get(session_id, [])

    # --- Long Term Memory (using vstore with 'memory' namespace) ---
    def add_long_term_memory(self, session_id: str, content: str):
        # Reusing text index, marking filename as __memory__
        vstore.add_texts(
            session_id=session_id,
            texts=[content],
            metadatas=[{"filename": "__memory__"}]
        )

    def search_long_term_memory(self, session_id: str, query: str, top_k: int = 4):
        # Retrieve text chunks and filter for __memory__
        # Using top_k * 5 inside vstore gives us enough buffer, we just need to filter here.
        all_results = vstore.search_text(session_id, query, top_k=top_k*5)
        memory_results = [r for r in all_results if r["filename"] == "__memory__"]
        return memory_results[:top_k]

    # --- Event Memory ---
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
        # Extract named entities
        prompt = f"Extract named entities from the following text and return as a JSON array of strings: {query}"
        try:
            response = self.cohere_client.chat(
                message=prompt,
                model=settings.CHAT_MODEL_FAST
            )
            
            # Very basic extraction parsing
            import json
            import re
            
            # Find json array
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
