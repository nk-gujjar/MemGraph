import json
import time
import asyncio
import cohere
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.config import settings
from backend.chat.intent import intent_detector
from backend.retrieval.retriever import retrieve
from backend.chat.context_builder import context_builder
from backend.chat.chain import chat_chain
from backend.chat.post_processor import post_processor
from backend.retrieval.memory_store import memory_store
from backend.observability.langfuse_client import lf_client
from backend.observability.log_writer import QueryLogger
from backend.observability.confidence import compute_confidence_from_memgraph_result
from backend.observability.llm_judge import evaluate_async

class ConnectionManager:
    def __init__(self):
        # session_id -> list of websockets
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast_to_session(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                await connection.send_json(message)

manager = ConnectionManager()

router = APIRouter(tags=["websocket"])

@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    
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
                
            print(f"\n[WS] Received query: '{query}' (Session: {session_id})")
            start_time = time.time()

            # OBSERVE: Initialize Langfuse Trace
            trace = lf_client.start_trace(
                name="chat_turn",
                session_id=session_id,
                input_data=query,
                tags=["chat", "memgraph"]
            )

            # LOG: Initialize per-query logger
            qlog = QueryLogger(session_id=session_id, approach="memgraph", query=query)

            try:
                # 1. Intent Detection
                print("Detecting intent...")
                intent_span = qlog.start_span("intent_detection")
                intent = await asyncio.to_thread(intent_detector.detect, session_id, query, parent_trace=trace)
                print(f"Detected intent: {intent}")
                qlog.add_span(intent_span.finish(
                    model=settings.CHAT_MODEL_FAST,
                    result=intent
                ))

                # 2. Add to memory (short term)
                memory_store.add_message(session_id, "user", query)

                # 3. Retrieve
                print(f"Retrieving context for query: '{query}'...")
                retrieval_span = qlog.start_span("retrieval")
                retrieval_result = await retrieve(query, session_id, intent, parent_trace=trace)
                source_labels = [
                    f"{s.get('filename', '?')} p{s.get('page_number', '?')}"
                    for s in []
                ]

                # 4. Context Build
                context_str, sources = context_builder.build(retrieval_result)
                source_labels = [
                    f"{s.get('filename', '?')} p{s.get('page_number', '?')}"
                    for s in sources
                ]
                print(f"Total contextual items retrieved: {len(retrieval_result.items)}")
                print(f"Retrieved {len(sources)} sources (PDF/Table chunks).")

                # Confidence score — computed from retrieval, no LLM call
                confidence = compute_confidence_from_memgraph_result(retrieval_result.items)

                qlog.add_span(retrieval_span.finish(
                    chunks_returned=len(retrieval_result.items),
                    sources=source_labels,
                    confidence=confidence["combined"]
                ))

                # 5. Stream LLM
                print("Streaming response...")

                # Tiny delay to ensure frontend state is synced (prevents ghosting)
                await asyncio.sleep(0.05)

                full_response = ""
                llm_span = qlog.start_span("llm_generation")
                async for token in chat_chain.stream_response(query, context_str, parent_trace=trace):
                    full_response += token
                    await websocket.send_json({"type": "token", "content": token})

                # 6. Memory Store assistant response
                memory_store.add_message(session_id, "assistant", full_response)

                # 7. Trace and Token Stats
                latency_ms = (time.time() - start_time) * 1000

                # Get exact token counts for DB sync
                full_prompt = f"Context: {context_str}\nUser: {query}"
                try:
                    input_tokens_res = await asyncio.to_thread(
                        post_processor.cohere_client.tokenize,
                        text=full_prompt,
                        model=settings.CHAT_MODEL_QUALITY
                    )
                    input_tokens = len(input_tokens_res.tokens)

                    output_tokens_res = await asyncio.to_thread(
                        post_processor.cohere_client.tokenize,
                        text=full_response,
                        model=settings.CHAT_MODEL_QUALITY
                    )
                    output_tokens = len(output_tokens_res.tokens)
                except Exception as e:
                    print(f"Tokenization failed: {e}")
                    input_tokens = len(full_prompt) // 4
                    output_tokens = len(full_response) // 4

                qlog.add_span(llm_span.finish(
                    model=settings.CHAT_MODEL_QUALITY,
                    tokens={"input": input_tokens, "output": output_tokens}
                ))

                # OBSERVE: Finalize Langfuse Trace
                if trace:
                    trace.update(
                        output=full_response,
                        metadata={
                            "intent": intent,
                            "latency_ms": latency_ms,
                            "sources_count": len(sources)
                        },
                        usage={"input": input_tokens, "output": output_tokens}
                    )

                # LOG + LLM-as-Judge:
                # Response already streamed to user — now run judge concurrently
                # with post-processing. Await the score before writing the log
                # so everything lands in ONE record (no latency impact for user).
                judge_task = asyncio.create_task(
                    evaluate_async(
                        query_id=qlog.query_id,
                        session_id=session_id,
                        approach="memgraph",
                        query=query,
                        context=context_str,
                        response=full_response
                    )
                )

                # 8. Post Processing (fire and forget) + await judge together
                judge_scores, _ = await asyncio.gather(
                    judge_task,
                    post_processor.process(session_id, query, full_response, input_tokens, output_tokens),
                    return_exceptions=True
                )

                # Write single complete log record (response + judge in one line)
                qlog.write(
                    output=full_response,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    sources=source_labels,
                    confidence=confidence,
                    judge=judge_scores if isinstance(judge_scores, dict) else None
                )

                # 9. Send sources
                await websocket.send_json({"type": "source", "content": json.dumps(sources)})

                # 10. Done and Sync Stats
                print(f"Response completed in {(time.time() - start_time):.2f}s")
                await websocket.send_json({"type": "done", "content": ""})

                # Send updated stats to frontend for real-time UI sync
                await websocket.send_json({
                    "type": "stats",
                    "session_id": session_id,
                    "tokens_used": input_tokens + output_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                })

            except Exception as e:
                if trace:
                    trace.update(output=f"Error: {str(e)}")
                print(f"Chat error: {e}")
                await websocket.send_json({"type": "error", "content": f"An error occurred: {str(e)}"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        print(f"Client disconnected for session {session_id}")
