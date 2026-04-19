import json
import time
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.chat.intent import intent_detector
from backend.retrieval.retriever import retrieve
from backend.chat.context_builder import context_builder
from backend.chat.chain import chat_chain
from backend.chat.post_processor import post_processor
from backend.retrieval.memory_store import memory_store
from backend.observability.langfuse_client import lf_client

router = APIRouter(tags=["websocket"])

@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
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
                
            try:
                # 1. Intent
                print("Detecting intent...")
                intent = await asyncio.to_thread(intent_detector.detect, session_id, query)
                print(f"Detected intent: {intent}")
                
                # 2. Add to memory (short term)
                memory_store.add_message(session_id, "user", query)
                
                # 3. Retrieve
                print(f"Retrieving context for query: '{query}'...")
                retrieval_result = await retrieve(query, session_id, intent)
                
                # 4. Context Build
                context_str, sources = context_builder.build(retrieval_result)
                print(f"Total contextual items retrieved: {len(retrieval_result.items)}")
                print(f"Retrieved {len(sources)} sources (PDF/Table chunks).")
                
                # 5. Stream LLM
                print("Streaming response...")
                full_response = ""
                async for token in chat_chain.stream_response(query, context_str):
                    full_response += token
                    await websocket.send_json({"type": "token", "content": token})
                    
                # 6. Memory Store assistant response
                memory_store.add_message(session_id, "assistant", full_response)
                
                # 7. Trace
                latency_ms = (time.time() - start_time) * 1000
                lf_client.trace_chat(session_id, query, intent, full_response, sources, latency_ms)
                
                # 8. Post Processing (fire and forget)
                tokens_used = len(full_response) // 4 + len(context_str) // 4 # rough estimate
                await post_processor.process(session_id, query, full_response, tokens_used)
                
                # 9. Send sources
                await websocket.send_json({"type": "source", "content": json.dumps(sources)})
                
                # 10. Done
                print(f"Response completed in {(time.time() - start_time):.2f}s")
                await websocket.send_json({"type": "done", "content": ""})
                
            except Exception as e:
                print(f"Chat error: {e}")
                await websocket.send_json({"type": "error", "content": f"An error occurred: {str(e)}"})
    except WebSocketDisconnect:
        print(f"Client disconnected for session {session_id}")
