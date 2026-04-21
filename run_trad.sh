#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  run_trad.sh  —  Start the Traditional RAG API
#  Port: 8001
#  WS:   ws://localhost:8001/trad/ws/{session_id}
# ─────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        TRADITIONAL RAG — Baseline        ║"
echo "║  Port 8001  |  WS: /trad/ws/{session_id} ║"
echo "╚══════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

source .venv/bin/activate 2>/dev/null || true

uvicorn traditional_rag.main:app --reload --host 0.0.0.0 --port 8001
