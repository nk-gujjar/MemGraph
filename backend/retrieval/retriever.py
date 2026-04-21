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

async def get_global_knowledge():
    return await asyncio.to_thread(memory_store.get_all_global_knowledge)

def merge_and_rank(results, intent):
    # Order: [rag_docs, tables, kg_triples, last_msgs, lt_memory, events, global_kn]
    rag_docs, tables, kg_triples, last_msgs, lt_memory, events, global_kn = results
    
    ranked_items = []
    
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
            
    if not isinstance(global_kn, Exception):
        for kn in global_kn:
            add_result("global_memory", f"GLOBAL {kn['type']}: {kn['content']}", 0.35)
            
    seen = set()
    deduped = []
    for item in sorted(ranked_items, key=lambda x: x["score"], reverse=True):
        if item["content"] not in seen:
            seen.add(item["content"])
            deduped.append(item)
            
    return RetrievalResult(deduped[:12])

async def rephrase_query(query: str, session_id: str, parent_trace=None) -> str:
    """Uses LLM to turn a follow-up query into a standalone search query."""
    last_msgs = memory_store.get_last_messages(session_id)
    if not last_msgs:
        return query
        
    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in last_msgs[-3:]])
    rephrase_prompt = f"Given the conversation history and a new query, rephrase the new query to be a standalone search query that can be used for RAG retrieval. If it's already standalone, return it as is.\n\nHistory:\n{history_str}\n\nNew Query: {query}\n\nStandalone Query:"
    
    generation = lf_client.add_generation(
        parent=parent_trace,
        name="query_rephrasing",
        model=settings.CHAT_MODEL_FAST,
        input_data=rephrase_prompt
    ) if parent_trace else None

    try:
        # Optimization: Use existing cohere client from memory_store to avoid re-init
        response = await asyncio.to_thread(memory_store.cohere_client.chat, message=rephrase_prompt, model=settings.CHAT_MODEL_FAST)
        rephrased = response.text.strip().strip('"')
        
        if generation:
            usage = {}
            if hasattr(response, 'meta') and hasattr(response.meta, 'tokens'):
                tokens = response.meta.tokens
                usage = {
                    "input": tokens.input_tokens if hasattr(tokens, 'input_tokens') else 0,
                    "output": tokens.output_tokens if hasattr(tokens, 'output_tokens') else 0
                }
            generation.end(output=rephrased, usage=usage if usage.get("input") or usage.get("output") else None)
            
        print(f"Rephrased query: '{query}' -> '{rephrased}'")
        return rephrased
    except Exception as e:
        if generation:
            generation.end(output=f"Error: {e}")
        print(f"Error rephrasing query: {e}")
        return query

async def retrieve(query: str, session_id: str, intent: str, parent_trace=None) -> RetrievalResult:
    start_retrieval = time.time()
    
    # LATENCY OPTIMIZATION: Start static context retrieval immediately while rephrasing
    static_tasks = [
        get_last_messages(session_id),
        get_event_memory(session_id),
        get_global_knowledge(),
    ]
    static_results_future = asyncio.gather(*static_tasks, return_exceptions=True)

    # REPHRASING
    search_query = query
    if intent != "chat" and (intent in ("follow_up", "summarize") or len(query.split()) < 4):
        search_query = await rephrase_query(query, session_id, parent_trace)
    
    # DYNAMIC RETRIEVAL
    retrieval_span = lf_client.add_span(parent_trace, "retrieval", input_data=search_query) if parent_trace else None
    
    dynamic_tasks = []
    if intent == "chat":
        # For casual chat, minimal noise
        dynamic_tasks = [
            asyncio.to_thread(list), # rag_docs
            asyncio.to_thread(list), # tables
            asyncio.to_thread(list), # kg_triples
            asyncio.to_thread(list), # lt_memory
        ]
    else:
        dynamic_tasks = [
            search_rag_docs(search_query, session_id),
            search_tables(search_query, session_id),
            get_kg_triples(search_query, session_id),
            search_long_term_memory(search_query, session_id),
        ]

    # Additional Summarization task
    if intent == "summarize":
        print("[Retriever] Optimized summary fetch (12 chunks).")
        dynamic_tasks.append(asyncio.to_thread(vstore.get_all_session_chunks, session_id, limit=12))

    dynamic_results = await asyncio.gather(*dynamic_tasks, return_exceptions=True)
    static_results = await static_results_future
    
    # RE-ASSEMBLE: [rag_docs, tables, kg_triples, last_msgs, lt_memory, events, global_kn]
    # Current dynamic_results: [rag_docs, tables, kg_triples, lt_memory, (optional) summarize_chunks]
    # Current static_results: [last_msgs, event_memory, global_kn]
    
    rag_docs = dynamic_results[0]
    if intent == "summarize" and len(dynamic_results) > 4:
        summary_chunks = dynamic_results[4]
        if not isinstance(summary_chunks, Exception) and not isinstance(rag_docs, Exception):
            rag_docs.extend(summary_chunks)
    
    final_results = [
        rag_docs,            # 0
        dynamic_results[1],  # 1 (tables)
        dynamic_results[2],  # 2 (kg_triples)
        static_results[0],   # 3 (last_msgs)
        dynamic_results[3],  # 4 (lt_memory)
        static_results[1],   # 5 (events)
        static_results[2],   # 6 (global_kn)
    ]
    
    merged = merge_and_rank(final_results, intent)
    
    if retrieval_span:
        retrieval_span.end(metadata={"result_count": len(merged.items)})
        
    latency_ms = (time.time() - start_retrieval) * 1000
    lf_client.trace_retrieval(session_id, query, len(merged.items), [], latency_ms)
    
    return merged
