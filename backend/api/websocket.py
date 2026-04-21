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
            
            # OBSERVE: Initialize Trace
            trace = lf_client.start_trace(
                name="chat_turn", 
                session_id=session_id, 
                input_data=query,
                tags=["chat"]
            )
                
            try:
                # 1. Intent
                print("Detecting intent...")
                intent = await asyncio.to_thread(intent_detector.detect, session_id, query, parent_trace=trace)
                print(f"Detected intent: {intent}")
                
                # 2. Add to memory (short term)
                memory_store.add_message(session_id, "user", query)
                
                # 3. Retrieve
                print(f"Retrieving context for query: '{query}'...")
                retrieval_result = await retrieve(query, session_id, intent, parent_trace=trace)
                
                # 4. Context Build
                context_str, sources = context_builder.build(retrieval_result)
                print(f"Total contextual items retrieved: {len(retrieval_result.items)}")
                print(f"Retrieved {len(sources)} sources (PDF/Table chunks).")
                
                # 5. Stream LLM
                print("Streaming response...")
                
                # Tiny delay to ensure frontend state is synced (prevents ghosting)
                await asyncio.sleep(0.05)
                
                full_response = ""
                async for token in chat_chain.stream_response(query, context_str, parent_trace=trace):
                    full_response += token
                    await websocket.send_json({"type": "token", "content": token})
                    
                # 6. Memory Store assistant response
                memory_store.add_message(session_id, "assistant", full_response)
                
                # 7. Trace and Token Stats
                latency_ms = (time.time() - start_time) * 1000
                
                # Get exact token counts for DB sync
                try:
                    # Input tokens: system prompt + context + query
                    full_prompt = f"{chat_chain.llm.system_prompt if hasattr(chat_chain.llm, 'system_prompt') else ''}\nContext: {context_str}\nUser: {query}"
                    input_tokens_res = await asyncio.to_thread(post_processor.cohere_client.tokenize, text=full_prompt, model=settings.CHAT_MODEL_QUALITY)
                    input_tokens = len(input_tokens_res.tokens)
                    
                    # Output tokens
                    output_tokens_res = await asyncio.to_thread(post_processor.cohere_client.tokenize, text=full_response, model=settings.CHAT_MODEL_QUALITY)
                    output_tokens = len(output_tokens_res.tokens)
                except Exception as e:
                    print(f"Tokenization failed: {e}")
                    input_tokens = len(full_prompt) // 4
                    output_tokens = len(full_response) // 4

                # OBSERVE: Finalize Trace metadata
                if trace:
                    trace.update(
                        output=full_response,
                        metadata={
                            "intent": intent,
                            "latency_ms": latency_ms,
                            "sources_count": len(sources)
                        },
                        usage={
                            "input": input_tokens,
                            "output": output_tokens
                        }
                    )
                
                # 8. Post Processing (fire and forget)
                await post_processor.process(session_id, query, full_response, input_tokens, output_tokens)
                
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
