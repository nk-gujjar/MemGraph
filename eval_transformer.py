#!/usr/bin/env python3
"""
eval_transformer.py
───────────────────
Evaluation harness for 'Attention Is All You Need' (40 Queries)
  1. Traditional RAG: Create session -> Upload -> Wait -> 40 Queries
  2. MemGraph: Create session -> Upload -> Wait -> 40 Queries
  3. Save results to eval_results/
"""

import asyncio
import json
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

import httpx
import websockets

# ── Config ───────────────────────────────────────────────────────────────────

MEMGRAPH_BASE   = "http://localhost:8000"
TRAD_BASE       = "http://localhost:8001"
MEMGRAPH_WS     = "ws://localhost:8000"
TRAD_WS         = "ws://localhost:8001"

DEFAULT_PDF = Path(__file__).parent / "1706.03762v7.pdf"

QUERIES = [
    # Phase 1: Core Understanding (Context Setup)
    "What problem does this paper try to solve?",
    "What are the limitations of RNN-based models mentioned here?",
    "Why is sequential computation a bottleneck?",
    "How does attention help overcome this?",
    "Summarize the key idea of the Transformer in 2 lines.",

    # Phase 2: Reference Dependency Begins
    "In the architecture you just described, what replaces recurrence?",
    "How does this affect parallelization?",
    "Compare this with the RNN limitation you mentioned earlier.",
    "What trade-offs does this new approach introduce?",
    "Which part of the model handles long-range dependencies?",

    # Phase 3: Architecture Tracking
    "Explain the encoder structure in the Transformer.",
    "How many layers does it use?",
    "What are the sub-layers inside each encoder block?",
    "What role do residual connections play here?",
    "How does the decoder differ from the encoder?",

    # Phase 4: Cross-turn Linking (Hard for RAG)
    "In the decoder you explained earlier, why is masking needed?",
    "How does this relate to auto-regressive behavior?",
    "Can you connect this to sequence generation?",
    "What would happen if masking is removed?",
    "Summarize encoder vs decoder differences briefly.",

    # Phase 5: Deep Attention Understanding
    "Explain scaled dot-product attention.",
    "Why is scaling needed in attention?",
    "What issue occurs without scaling?",
    "How does multi-head attention improve over single-head?",
    "Based on earlier explanation, why multiple heads are useful?",

    # Phase 6: Memory + Mathematical Dependency
    "Write the attention formula used in the paper.",
    "Now explain each term in that formula.",
    "How does this connect to the query-key-value concept you explained earlier?",
    "What changes when we move to multi-head attention?",
    "Summarize attention mechanism in simple terms.",

    # Phase 7: Positional Encoding (Context Dependency)
    "Why does the Transformer need positional encoding?",
    "How is it different from RNN sequence handling?",
    "What type of positional encoding is used in the paper?",
    "Why are sine and cosine functions chosen?",
    "How does this help in generalization?",

    # Phase 8: Model Comparison & Reasoning
    "Compare Transformer vs RNN vs CNN based on parallelization, path length, and computation.",
    "Which model handles long dependencies best and why?",
    "How does self-attention reduce path length?",
    "Based on earlier discussion, why is this important?",

    # Phase 9: Training & Results (Long Context Recall)
    "What were the key results achieved by the Transformer in terms of BLEU scores and training efficiency?",
]

OUTPUT_DIR = Path(__file__).parent / "eval_results"

# ── Helpers ──────────────────────────────────────────────────────────────────

async def create_session(client: httpx.AsyncClient, base: str, label: str) -> str:
    r = await client.post(f"{base}/api/sessions")
    r.raise_for_status()
    sid = r.json()["session_id"]
    print(f"  [{label}] Session created: {sid}")
    return sid

async def upload_pdf(client: httpx.AsyncClient, base: str, session_id: str, pdf_path: Path, label: str):
    print(f"  [{label}] Uploading {pdf_path.name}...")
    with open(pdf_path, "rb") as f:
        r = await client.post(
            f"{base}/api/sessions/{session_id}/upload",
            files={"files": (pdf_path.name, f, "application/pdf")},
            timeout=120.0,
        )
    r.raise_for_status()
    print(f"  [{label}] Upload accepted. Waiting for indexing...")

async def wait_for_indexing(client: httpx.AsyncClient, base: str, session_id: str, label: str, timeout: int = 600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = await client.get(f"{base}/api/sessions/{session_id}/sources", timeout=10.0)
            if r.status_code == 200:
                sources = r.json()
                if sources:
                    statuses = [s.get("status", "") for s in sources]
                    if all(s == "completed" for s in statuses):
                        chunks = sum(s.get("chunk_count", 0) for s in sources)
                        print(f"  [{label}] Indexing complete: {chunks} chunks found.")
                        return True
                    elif any("failed" in s for s in statuses):
                        print(f"  [{label}] Indexing FAILED: {statuses}")
                        return False
        except Exception:
            pass
        await asyncio.sleep(5)
    print(f"  [{label}] Indexing timed out.")
    return False

async def run_queries(ws_base: str, session_id: str, label: str, delay: float = 1.2) -> list[dict]:
    results = []
    uri = f"{ws_base}/ws/{session_id}"
    print(f"\n  [{label}] Running {len(QUERIES)} queries...")
    
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=30) as ws:
            for i, query in enumerate(QUERIES, start=1):
                start = time.time()
                tokens = []
                
                await ws.send(json.dumps({"query": query}))
                
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=120)
                    msg = json.loads(raw)
                    if msg.get("type") == "token":
                        tokens.append(msg.get("content", ""))
                    elif msg.get("type") == "done":
                        break
                    elif msg.get("type") == "error":
                        tokens.append(f"[ERROR: {msg.get('content')}]")
                        break
                
                latency = round((time.time() - start) * 1000, 1)
                response = "".join(tokens)
                
                result = {
                    "q_num": i,
                    "query": query,
                    "response": response,
                    "latency_ms": latency,
                    "timestamp": datetime.utcnow().isoformat()
                }
                results.append(result)
                print(f"    Q{i:02d} ✓ ({latency:>7.0f}ms)")
                
                if delay > 0 and i < len(QUERIES):
                    await asyncio.sleep(delay)
    except Exception as e:
        print(f"  [{label}] Connection dropped: {e}")
    return results

def save_results(results: list[dict], label: str, session_id: str):
    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = OUTPUT_DIR / f"{label}_{session_id[:8]}.jsonl"
    with open(filename, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  [{label}] Saved to {filename}")

# ── Main ──────────────────────────────────────────────────────────────────────

async def main(pdf_path: Path):
    print(f"Starting Evaluation using {pdf_path.name}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Traditional RAG
        print("\n--- TRADITIONAL RAG ---")
        tr_sid = await create_session(client, TRAD_BASE, "TradRAG")
        await upload_pdf(client, TRAD_BASE, tr_sid, pdf_path, "TradRAG")
        if await wait_for_indexing(client, TRAD_BASE, tr_sid, "TradRAG"):
            tr_results = await run_queries(TRAD_WS, tr_sid, "TradRAG")
            save_results(tr_results, "trad_transformer", tr_sid)
        
        # 2. MemGraph
        print("\n--- MEMGRAPH ---")
        mg_sid = await create_session(client, MEMGRAPH_BASE, "MemGraph")
        await upload_pdf(client, MEMGRAPH_BASE, mg_sid, pdf_path, "MemGraph")
        if await wait_for_indexing(client, MEMGRAPH_BASE, mg_sid, "MemGraph"):
            mg_results = await run_queries(MEMGRAPH_WS, mg_sid, "MemGraph")
            save_results(mg_results, "memgraph_transformer", mg_sid)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    args = parser.parse_args()
    asyncio.run(main(args.pdf))
