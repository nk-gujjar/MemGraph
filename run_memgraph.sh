#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  run_memgraph.sh  —  Start the MemGraph (your approach) API
#  Port: 8000
#  WS:   ws://localhost:8000/ws/{session_id}
# ─────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       MEMGRAPH — Your RAG Approach       ║"
echo "║  Port 8000  |  WS: /ws/{session_id}      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

source .venv/bin/activate 2>/dev/null || true

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
