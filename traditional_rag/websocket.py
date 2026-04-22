"""
Traditional RAG — WebSocket Chat Handler

Endpoint: /trad/ws/{session_id}

Pipeline per query:
  1. Vector retrieval (pure FAISS, no intent/rephrasing)
  2. Memory context (last N msgs + rolling summary)
  3. Build doc context string
  4. Stream LLM response
  5. Update memory (+ trigger summary compression if needed)
  6. Write JSONL log with all spans
  7. Send token stats to frontend (same wire protocol as MemGraph)
"""

import json
import time
import asyncio
import cohere

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from traditional_rag.config import trad_settings
from traditional_rag.retriever import trad_retrieve
from traditional_rag.memory import trad_memory
from traditional_rag.chain import trad_chain
from traditional_rag.db import TradSessionLocal, TradSession
from backend.observability.log_writer import QueryLogger  # shared log writer
from backend.observability.langfuse_client import lf_client  # shared Langfuse
from backend.observability.confidence import compute_confidence
from backend.observability.llm_judge import evaluate_async
from backend.llm_config import llm_client

router = APIRouter(tags=["trad-websocket"])
_cohere_client = llm_client.cohere


# ── Connection Manager (mirrors MemGraph's) ───────────────────────────────────

class TradConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, sid: str):
        await ws.accept()
        self.active.setdefault(sid, []).append(ws)

    def disconnect(self, ws: WebSocket, sid: str):
        if sid in self.active:
            self.active[sid].remove(ws)
            if not self.active[sid]:
                del self.active[sid]

    async def send(self, ws: WebSocket, msg: dict):
        await ws.send_json(msg)


trad_manager = TradConnectionManager()


# ── WebSocket Routes ──────────────────────────────────────────────────────────
# /ws/{session_id}       ← frontend-compatible (standalone port 8001)
# /trad/ws/{session_id}  ← namespaced (shared-server mode)

async def _handle_chat(websocket: WebSocket, session_id: str):
    """Shared chat handler for both WS routes."""
    await trad_manager.connect(websocket, session_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                query = payload.get("query", "")
            except json.JSONDecodeError:
                continue

            if not query:
                continue

            print(f"\n[TradWS] Query: '{query}' (Session: {session_id})")

            # OBSERVE: Langfuse trace
            trace = lf_client.start_trace(
                name="trad_chat_turn",
                session_id=session_id,
                input_data=query,
                tags=["chat", "traditional_rag"],
            )

            # LOG: per-query span logger
            qlog = QueryLogger(
                session_id=session_id,
                approach="traditional_rag",
                query=query,
            )

            try:
                # ── 1. Vector Retrieval ──────────────────────────────────────
                retrieval_span = qlog.start_span("retrieval")
                lf_retrieval = lf_client.add_span(trace, "retrieval", input_data=query)

                chunks = await trad_retrieve(query, session_id)
                source_labels = [
                    f"{c['filename']} p{c.get('page_number', '?')}"
                    for c in chunks
                ]
                print(f"[TradWS] Retrieved {len(chunks)} chunks.")

                # Confidence score — computed from FAISS similarity scores
                confidence = compute_confidence(chunks)

                qlog.add_span(retrieval_span.finish(
                    chunks_returned=len(chunks),
                    sources=source_labels,
                    confidence=confidence["combined"]
                ))
                if lf_retrieval:
                    lf_retrieval.end(metadata={"chunks": len(chunks)})

                # ── 2. Memory Context ────────────────────────────────────────
                memory_span = qlog.start_span("memory_fetch")
                memory_context, last_msgs = await asyncio.to_thread(
                    trad_memory.build_memory_context, session_id
                )
                qlog.add_span(memory_span.finish(
                    messages_in_window=len(last_msgs)
                ))

                # ── 3. Build Doc Context ─────────────────────────────────────
                if chunks:
                    doc_context = "\n\n".join([
                        f"[Source: {c['filename']}, page {c.get('page_number', 'N/A')}]\n{c['text']}"
                        for c in chunks
                    ])
                else:
                    doc_context = "No relevant document context found."

                # ── 4. Store user message ────────────────────────────────────
                await asyncio.to_thread(
                    trad_memory.add_message, session_id, "user", query
                )

                # ── 5. Stream LLM ────────────────────────────────────────────
                await asyncio.sleep(0.05)  # frontend sync
                llm_span = qlog.start_span("llm_generation")
                lf_gen = lf_client.add_generation(
                    parent=trace,
                    name="trad_generation",
                    model=trad_settings.CHAT_MODEL_QUALITY,
                    input_data=trad_chain.build_full_prompt(query, memory_context, doc_context),
                )

                full_response = ""
                async for token in trad_chain.stream_response(query, memory_context, doc_context):
                    full_response += token
                    await websocket.send_json({"type": "token", "content": token})

                # ── 6. Store assistant response ──────────────────────────────
                await asyncio.to_thread(
                    trad_memory.add_message, session_id, "assistant", full_response
                )

                # ── 7. Token Counting ────────────────────────────────────────
                full_prompt = trad_chain.build_full_prompt(query, memory_context, doc_context)
                try:
                    in_res = await asyncio.to_thread(
                        _cohere_client.tokenize,
                        text=full_prompt,
                        model=trad_settings.CHAT_MODEL_QUALITY,
                    )
                    input_tokens = len(in_res.tokens)

                    out_res = await asyncio.to_thread(
                        _cohere_client.tokenize,
                        text=full_response,
                        model=trad_settings.CHAT_MODEL_QUALITY,
                    )
                    output_tokens = len(out_res.tokens)
                except Exception as e:
                    print(f"[TradWS] Tokenization failed: {e}")
                    input_tokens = len(full_prompt) // 4
                    output_tokens = len(full_response) // 4

                qlog.add_span(llm_span.finish(
                    model=trad_settings.CHAT_MODEL_QUALITY,
                    tokens={"input": input_tokens, "output": output_tokens},
                ))

                if lf_gen:
                    lf_gen.end(
                        output=full_response,
                        usage={"input": input_tokens, "output": output_tokens},
                    )

                # ── 8. Finalize Langfuse trace ───────────────────────────────
                if trace:
                    trace.update(
                        output=full_response,
                        metadata={"chunks_retrieved": len(chunks)},
                        usage={"input": input_tokens, "output": output_tokens},
                    )

                # ── 9. Write JSONL log ───────────────────────────────────────
                # Start the judge concurrently with memory summarization
                # (user already got response, we run both and await together)
                judge_task = asyncio.create_task(evaluate_async(
                    query_id=qlog.query_id,
                    session_id=session_id,
                    approach="traditional_rag",
                    query=query,
                    context=doc_context,
                    response=full_response
                ))

                # ── 10. Update session stats + memory summarization + judge ────
                asyncio.create_task(_update_stats(session_id, input_tokens, output_tokens))

                # Await judge so we can embed it in the log record
                judge_scores = await judge_task

                # Write single complete log record
                qlog.write(
                    output=full_response,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    sources=source_labels,
                    confidence=confidence,
                    judge=judge_scores if isinstance(judge_scores, dict) else None
                )

                # ── 11. Trigger memory summarization (fire & forget) ──────────
                asyncio.create_task(
                    asyncio.to_thread(trad_memory.maybe_summarize, session_id)
                )

                # ── 12. Wire protocol (same as MemGraph for easy comparison) ─
                await websocket.send_json({
                    "type": "source",
                    "content": json.dumps([
                        {"filename": c["filename"], "page_number": c.get("page_number")}
                        for c in chunks
                    ]),
                })
                await websocket.send_json({"type": "done", "content": ""})
                await websocket.send_json({
                    "type": "stats",
                    "session_id": session_id,
                    "tokens_used": input_tokens + output_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                })

                print(f"[TradWS] Done — {input_tokens + output_tokens} tokens total")

            except Exception as e:
                if trace:
                    trace.update(output=f"Error: {str(e)}")
                print(f"[TradWS] Error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "content": f"An error occurred: {str(e)}",
                })

    except WebSocketDisconnect:
        trad_manager.disconnect(websocket, session_id)
        print(f"[TradWS] Client disconnected: {session_id}")


# ── Register both WS paths ────────────────────────────────────────────────────

@router.websocket("/ws/{session_id}")
async def trad_websocket_chat_compat(websocket: WebSocket, session_id: str):
    """Frontend-compatible endpoint (standalone mode on port 8001)."""
    await _handle_chat(websocket, session_id)


@router.websocket("/trad/ws/{session_id}")
async def trad_websocket_chat_prefixed(websocket: WebSocket, session_id: str):
    """Namespaced endpoint (shared-server mode)."""
    await _handle_chat(websocket, session_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _update_stats(session_id: str, input_tokens: int, output_tokens: int):
    db = TradSessionLocal()
    try:
        sess = db.query(TradSession).filter(TradSession.id == session_id).first()
        if sess:
            sess.message_count += 2
            sess.input_tokens += input_tokens
            sess.output_tokens += output_tokens
            sess.tokens_used += input_tokens + output_tokens
            db.commit()
    finally:
        db.close()
