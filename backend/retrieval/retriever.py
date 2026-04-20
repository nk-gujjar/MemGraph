import asyncio
import cohere
import time
from backend.config import settings
from backend.retrieval.vector_store import vstore
from backend.retrieval.memory_store import memory_store
from backend.observability.langfuse_client import lf_client

class RetrievalResult:
    def __init__(self, items):
        self.items = items

async def search_rag_docs(query: str, session_id: str):
    return await asyncio.to_thread(vstore.search_text, session_id, query)

async def search_tables(query: str, session_id: str):
    return await asyncio.to_thread(vstore.search_tables, session_id, query)

async def get_kg_triples(query: str, session_id: str):
    return await asyncio.to_thread(memory_store.extract_and_query_kg, session_id, query)

async def get_last_messages(session_id: str):
    return await asyncio.to_thread(memory_store.get_last_messages, session_id)

async def search_long_term_memory(query: str, session_id: str):
    return await asyncio.to_thread(memory_store.search_long_term_memory, session_id, query)

async def get_event_memory(session_id: str):
    return await asyncio.to_thread(memory_store.get_event_memory, session_id)

def merge_and_rank(results, intent):
    rag_docs, tables, kg_triples, last_msgs, lt_memory, events = results
    
    ranked_items = []
    
    # helper for adding
    def add_result(item_type, content, score, meta=None):
        if isinstance(content, Exception):
            return
        ranked_items.append({
            "type": item_type,
            "content": content,
            "score": score,
            "meta": meta or {}
        })

    if not isinstance(rag_docs, Exception):
        for doc in rag_docs:
            if doc["filename"] != "__memory__":
                add_result("rag_doc", doc["text"], doc["score"] * 0.4, doc)
            
    if not isinstance(tables, Exception):
        for t in tables:
            add_result("table", t["raw_markdown"], t["score"] * 0.35, t)
            
    if not isinstance(kg_triples, Exception):
        for triple in kg_triples:
            add_result("kg_triple", f"{triple['subject']} -> {triple['predicate']} -> {triple['object']}", 0.3)
            
    if not isinstance(last_msgs, Exception):
        for i, msg in enumerate(reversed(last_msgs)):
            add_result("last_message", f"{msg['role']}: {msg['content']}", max(0.01, 0.25 - (i*0.05)))
            
    if not isinstance(lt_memory, Exception):
        for mem in lt_memory:
            add_result("lt_memory", mem["text"], mem["score"] * 0.2)
            
    if not isinstance(events, Exception):
        for ev in events:
            add_result("event_memory", f"{ev['type']}: {ev['content']}", 0.15)
            
    # Remove duplicates based on content
    seen = set()
    deduped = []
    for item in sorted(ranked_items, key=lambda x: x["score"], reverse=True):
        if item["content"] not in seen:
            seen.add(item["content"])
            deduped.append(item)
            
    return RetrievalResult(deduped[:12])

async def rephrase_query(query: str, session_id: str) -> str:
    """Uses LLM to turn a follow-up query into a standalone search query."""
    last_msgs = memory_store.get_last_messages(session_id)
    if not last_msgs:
        return query
        
    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in last_msgs[-3:]])
    prompt = f"Given the conversation history and a new query, rephrase the new query to be a standalone search query that can be used for RAG retrieval. If it's already standalone, return it as is.\n\nHistory:\n{history_str}\n\nNew Query: {query}\n\nStandalone Query:"
    
    try:
        co = cohere.Client(api_key=settings.COHERE_API_KEY)
        response = await asyncio.to_thread(co.chat, message=prompt, model=settings.CHAT_MODEL_FAST)
        rephrased = response.text.strip().strip('"')
        print(f"Rephrased query: '{query}' -> '{rephrased}'")
        return rephrased
    except Exception as e:
        print(f"Error rephrasing query: {e}")
        return query

async def retrieve(query: str, session_id: str, intent: str) -> RetrievalResult:
    start_retrieval = time.time()
    search_query = query
    # Only rephrase if it's a follow-up or summary and NOT a casual chat
    if intent != "chat" and (intent in ("follow_up", "summarize") or len(query.split()) < 4):
        search_query = await rephrase_query(query, session_id)
        
    if intent == "chat":
        # For casual chat, only bring in personal/history context, skip heavy doc search
        tasks = [
            asyncio.to_thread(list),                     # rag_docs
            asyncio.to_thread(list),                     # tables
            get_kg_triples(search_query, session_id),    # KG store (relevant for personal facts)
            get_last_messages(session_id),               # history
            asyncio.to_thread(list),                     # lt_memory
            get_event_memory(session_id),                # events
        ]
    else:
        tasks = [
            search_rag_docs(search_query, session_id),       # FAISS text index
            search_tables(search_query, session_id),          # FAISS table index
            get_kg_triples(search_query, session_id),                     # KG store
            get_last_messages(session_id),             # circular buffer
            search_long_term_memory(search_query, session_id),# FAISS memory namespace
            get_event_memory(session_id),              # SQLite events
        ]
    
    # If intent is summary, add a broad fetch task
    if intent == "summarize":
        print("[Retriever] Summary intent detected - adding broad document fetch.")
        tasks.append(asyncio.to_thread(vstore.get_all_session_chunks, session_id, limit=20))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle the extra result if present
    if intent == "summarize":
        summary_chunks = results.pop()
        semantic_rag = results[0]
        if not isinstance(summary_chunks, Exception) and not isinstance(semantic_rag, Exception):
            # Merge and deduplicate
            semantic_rag.extend(summary_chunks)
            results[0] = semantic_rag
            
    merged = merge_and_rank(results, intent)
    
    # Observe retrieval
    latency_ms = (time.time() - start_retrieval) * 1000
    # Estimate tokens for the search query
    input_tokens = len(search_query) // 4
    
    # Count returned sources (rag_doc or table)
    sources = [i for i in merged.items if i["type"] in ("rag_doc", "table")]
    scores = [i["score"] for i in merged.items]
    lf_client.trace_retrieval(session_id, query, len(sources), scores, latency_ms, input_tokens)
    
    return merged
