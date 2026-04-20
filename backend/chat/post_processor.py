import asyncio
import copy
import re
import json
import cohere
from backend.config import settings
from backend.db.sqlite import SessionLocal, Session
from backend.retrieval.memory_store import memory_store
from backend.retrieval.kg_store import kg_store

class PostProcessor:
    def __init__(self):
        self.cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)

    async def process(self, session_id: str, query: str, response: str, input_tokens: int = 0, output_tokens: int = 0):
        # Fire and forget tasks
        asyncio.create_task(self._importance_filter(session_id, response))
        asyncio.create_task(self._event_extraction(session_id, query, response))
        asyncio.create_task(self._extract_kg_triples(session_id, response))
        asyncio.create_task(self._update_session_stats(session_id, input_tokens, output_tokens))

    async def _importance_filter(self, session_id: str, response: str):
        if len(response.split()) > 50: # roughly > 50 words ~ 60-70 tokens
            # Just default rule: store as LT memory if it feels substantial
            await asyncio.to_thread(memory_store.add_long_term_memory, session_id, response)

    async def _event_extraction(self, session_id: str, query: str, response: str):
        prompt = f"Extract user preferences, goals, or important facts from this conversation turn. Return JSON array: [{{\"type\": \"user_preference|user_goal|important_fact\", \"content\": \"...\"}}] or [].\n\nUser: {query}\nAssistant: {response}"
        try:
            res = await asyncio.to_thread(self.cohere_client.chat, message=prompt, model=settings.CHAT_MODEL_FAST)
            text = res.text
            match = re.search(r'\[(.*?)\]', text, re.DOTALL)
            if match:
                events = json.loads(f"[{match.group(1)}]")
                for ev in events:
                    if "type" in ev and "content" in ev:
                        await asyncio.to_thread(memory_store.add_event_memory, session_id, ev["type"], ev["content"])
        except Exception as e:
            print(f"Event extraction skipped/failed: {e}")

    async def _extract_kg_triples(self, session_id: str, response: str):
        prompt = f"Extract factual (subject, predicate, object) triples from this text. Return only JSON array: [{{\"s\": \"...\", \"p\": \"...\", \"o\": \"...\"}}]. Text:\n\n{response}"
        try:
            res = await asyncio.to_thread(self.cohere_client.chat, message=prompt, model=settings.CHAT_MODEL_FAST)
            match = re.search(r'\[(.*?)\]', res.text, re.DOTALL)
            if match:
                triples = json.loads(f"[{match.group(1)}]")
                for t in triples:
                    if "s" in t and "p" in t and "o" in t:
                        await asyncio.to_thread(kg_store.add_triple, session_id, t["s"], t["p"], t["o"])
        except Exception as e:
            pass

    async def _update_session_stats(self, session_id: str, input_tokens: int, output_tokens: int):
        db = SessionLocal()
        try:
            sess = db.query(Session).filter(Session.id == session_id).first()
            if sess:
                sess.message_count += 2 # user + assistant
                sess.input_tokens += input_tokens
                sess.output_tokens += output_tokens
                sess.tokens_used += (input_tokens + output_tokens)
                db.commit()
        finally:
            db.close()

post_processor = PostProcessor()
