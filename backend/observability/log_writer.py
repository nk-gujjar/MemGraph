"""
log_writer.py
─────────────
Writes one JSONL line per query to logs/sessions/{session_id}.jsonl.

Each record schema:
{
  "session_id": "...",
  "approach": "memgraph" | "traditional_rag",
  "query_id": "uuid4",
  "timestamp": "ISO8601",
  "input": "user query",
  "output": "assistant response",
  "latency_total_ms": 1234.5,
  "tokens": { "input": 450, "output": 200, "total": 650 },
  "confidence": {
    "retrieval_score": 0.82,   # avg FAISS cosine similarity of retrieved chunks
    "source_count": 8,
    "combined": 0.78           # weighted confidence (0-1)
  },
  "spans": [
    { "name": "intent_detection", "latency_ms": 180, "model": "...", "result": "rag" },
    { "name": "retrieval",        "latency_ms": 350, "chunks_returned": 8, "sources": [...] },
    { "name": "llm_generation",   "latency_ms": 720, "model": "...", "tokens": {...} }
  ],
  "sources": ["file.pdf p3", ...]
}

Judge records (written async after response, correlated by query_id):
{
  "record_type": "judge",
  "session_id": "...",
  "query_id": "...",        ← same query_id as the main record
  "approach": "...",
  "timestamp": "ISO8601",
  "judge": {
    "faithfulness":  8,    # 0-10
    "relevance":     9,    # 0-10
    "completeness":  7,    # 0-10
    "coherence":     9,    # 0-10
    "overall":       8,    # 0-10
    "reasoning":     "...",
    "latency_ms":    430.2,
    "evaluated_at":  "ISO8601"
  }
}
"""

import os
import json
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

# Resolve log directory relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = _PROJECT_ROOT / "logs" / "sessions"


class SpanTimer:
    """Lightweight span tracker. Create one per pipeline step."""

    def __init__(self, name: str):
        self.name = name
        self._start = time.time()

    def finish(self, **kwargs) -> dict:
        """Stop the timer and return a span dict. Pass extra fields as kwargs."""
        latency_ms = (time.time() - self._start) * 1000
        span = {"name": self.name, "latency_ms": round(latency_ms, 2)}
        span.update(kwargs)
        return span


class QueryLogger:
    """
    Context object for a single query turn.
    Collect spans as you go, then call .write() at the end.
    """

    def __init__(self, session_id: str, approach: str, query: str):
        self.session_id = session_id
        self.approach = approach    # "memgraph" | "traditional_rag"
        self.query = query
        self.query_id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self._wall_start = time.time()
        self.spans: list[dict] = []

    def start_span(self, name: str) -> SpanTimer:
        return SpanTimer(name)

    def add_span(self, span: dict):
        self.spans.append(span)

    def write(
        self,
        output: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        sources: list = None,
        confidence: dict = None,
        judge: dict = None,
    ) -> dict:
        """Write the complete query record to JSONL (includes judge if provided)."""
        latency_total_ms = round((time.time() - self._wall_start) * 1000, 2)

        record = {
            "record_type": "response",
            "session_id": self.session_id,
            "approach": self.approach,
            "query_id": self.query_id,
            "timestamp": self.timestamp,
            "input": self.query,
            "output": output,
            "latency_total_ms": latency_total_ms,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            "confidence": confidence or {
                "retrieval_score": 0.0,
                "source_count": 0,
                "combined": 0.0,
            },
            "spans": self.spans,
            "sources": sources or [],
            "judge": judge,   # None if judge not yet available
        }

        _append_record(self.session_id, record)
        return record


def write_judge_update(
    session_id: str,
    query_id: str,
    approach: str,
    judge_scores: dict,
):
    """
    Write a judge evaluation record to the same session JSONL.
    Correlated to the original response via query_id.
    """
    record = {
        "record_type": "judge",
        "session_id": session_id,
        "query_id": query_id,
        "approach": approach,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "judge": judge_scores,
    }
    _append_record(session_id, record)


def _append_record(session_id: str, record: dict):
    """Appends one JSON line to logs/sessions/{session_id}.jsonl."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{session_id}.jsonl"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        print(f"[log_writer] Failed to write log: {e}")
