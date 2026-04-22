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
                # ITERATIVE RAG LOOP
                MAX_RETRIES = 2
                MIN_SCORE_THRESHOLD = 7
                
                final_full_response = ""
                final_context_str = ""
                final_sources = []
                final_intent = "rag"
                final_input_tokens = 0
                final_output_tokens = 0
                final_judge_scores = None

                for attempt in range(MAX_RETRIES + 1):
                    is_last_attempt = (attempt == MAX_RETRIES)
                    if attempt > 0:
                        print(f"[WS] Attempt {attempt+1} for session {session_id}...")
                        await websocket.send_json({"type": "token", "content": f"\n\n*(Self-Correction: Attempt {attempt+1} due to low quality score...)*\n\n"})

                    # 1. Intent Detection
                    print("Detecting intent...")
                    intent_span = qlog.start_span(f"intent_detection_a{attempt}")
                    intent = await asyncio.to_thread(intent_detector.detect, session_id, query, parent_trace=trace)
                    final_intent = intent
                    print(f"Detected intent: {intent}")
                    qlog.add_span(intent_span.finish(model=settings.CHAT_MODEL_FAST, result=intent))

                    # 2. Add to memory (only on first attempt to avoid duplication)
                    if attempt == 0:
                        memory_store.add_message(session_id, "user", query)

                    # 3. Retrieve
                    print(f"Retrieving context (Attempt {attempt+1})...")
                    retrieval_span = qlog.start_span(f"retrieval_a{attempt}")
                    retrieval_result = await retrieve(query, session_id, intent, parent_trace=trace)
                    
                    # 4. Context Build
                    context_str, sources = context_builder.build(retrieval_result)
                    final_context_str = context_str
                    final_sources = sources
                    source_labels = [f"{s.get('filename', '?')} p{s.get('page_number', '?')}" for s in sources]
                    
                    # Confidence score
                    confidence = compute_confidence_from_memgraph_result(retrieval_result.items)
                    qlog.add_span(retrieval_span.finish(
                        chunks_returned=len(retrieval_result.items),
                        sources=source_labels,
                        confidence=confidence["combined"]
                    ))

                    # 5. Generate Internal Response for Judging
                    if not is_last_attempt:
                        print(f"Evaluating quality for Attempt {attempt+1}...")
                        await websocket.send_json({"type": "token", "content": "*(Thinking and verifying quality...)* "})
                        
                        full_response = await chat_chain.generate_response(query, context_str, parent_trace=trace)
                        
                        # Judge it Synchronously (to decide whether to retry)
                        judge_scores = await evaluate_async(
                            query_id=qlog.query_id,
                            session_id=session_id,
                            approach="memgraph",
                            query=query,
                            context=context_str,
                            response=full_response
                        )
                        final_judge_scores = judge_scores
                        
                        if judge_scores.get("overall", 0) >= MIN_SCORE_THRESHOLD:
                            print(f"Quality threshold met ({judge_scores['overall']}/10). Proceeding to stream.")
                            final_full_response = full_response
                            break
                        else:
                            print(f"Quality too low ({judge_scores['overall']}/10). Retrying retrieval...")
                    else:
                        # Last attempt: Stream directly to user
                        print("Final attempt or threshold met. Streaming to user...")
                        
                        # Clear previous "Thinking..." tokens if any? 
                        # Actually just stream normally.
                        
                        full_response = ""
                        llm_span = qlog.start_span("llm_generation_final")
                        async for token in chat_chain.stream_response(query, context_str, parent_trace=trace):
                            full_response += token
                            await websocket.send_json({"type": "token", "content": token})
                        
                        final_full_response = full_response
                        
                        # Final Judge (async)
                        judge_task = asyncio.create_task(evaluate_async(
                            query_id=qlog.query_id,
                            session_id=session_id,
                            approach="memgraph",
                            query=query,
                            context=context_str,
                            response=full_response
                        ))
                        final_judge_scores = await judge_task
                        break

                # 6. Memory Store assistant response
                memory_store.add_message(session_id, "assistant", final_full_response)

                # 7. Trace and Token Stats
                latency_ms = (time.time() - start_time) * 1000
                full_prompt = f"Context: {final_context_str}\nUser: {query}"
                
                try:
                    input_tokens_res = await asyncio.to_thread(post_processor.cohere_client.tokenize, text=full_prompt, model=settings.CHAT_MODEL_QUALITY)
                    input_tokens = len(input_tokens_res.tokens)
                    output_tokens_res = await asyncio.to_thread(post_processor.cohere_client.tokenize, text=final_full_response, model=settings.CHAT_MODEL_QUALITY)
                    output_tokens = len(output_tokens_res.tokens)
                except Exception as e:
                    print(f"Tokenization failed: {e}")
                    input_tokens = len(full_prompt) // 4
                    output_tokens = len(final_full_response) // 4
                
                final_input_tokens = input_tokens
                final_output_tokens = output_tokens

                # OBSERVE: Finalize Langfuse Trace
                if trace:
                    trace.update(
                        output=final_full_response,
                        metadata={"intent": final_intent, "latency_ms": latency_ms, "sources_count": len(final_sources), "retries": attempt},
                        usage={"input": input_tokens, "output": output_tokens}
                    )

                # 8. Post Processing & Log Write
                await post_processor.process(session_id, query, final_full_response, input_tokens, output_tokens)
                
                source_labels = [f"{s.get('filename', '?')} p{s.get('page_number', '?')}" for s in final_sources]
                qlog.write(
                    output=final_full_response,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    sources=source_labels,
                    confidence=confidence,
                    judge=final_judge_scores
                )

                # 9. Send sources
                await websocket.send_json({"type": "source", "content": json.dumps(final_sources)})

                # 10. Done and Sync Stats
                print(f"Response completed in {(time.time() - start_time):.2f}s (Attempts: {attempt+1})")
                await websocket.send_json({"type": "done", "content": ""})

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
