# MemGraph File Structure

This document outlines the high-level file and directory structure of the MemGraph project.

---

## Root Directory

| Path | Description |
|---|---|
| `backend/` | Primary FastAPI backend implementing the MemGraph RAG pipeline |
| `traditional_rag/` | Baseline traditional RAG implementation used for benchmarking |
| `frontend/` | React + Vite user interface |
| `doc/` | Documentation files |
| `faiss_indexes/` | FAISS vector index storage for MemGraph |
| `faiss_trad/` | FAISS vector index storage for Traditional RAG |
| `uploads/` | User-uploaded documents awaiting processing |
| `logs/` | Application and evaluation logs (includes Langfuse-exported JSONL benchmark data) |
| `run_memgraph.sh` | Script to start the MemGraph backend server |
| `run_trad.sh` | Script to start the Traditional RAG backend server |

### `doc/`
- `MEMGRAPH_ARCHITECTURE.md` — Full architecture deep-dive (ingestion, memory, retrieval, observability)
- `MemGraph_arch.png` — System architecture diagram
- `file_structure.md` — This document

---

## Backend Directory (`backend/`)

The MemGraph advanced RAG pipeline built on FastAPI, LangChain, and Cohere.

```
backend/
├── main.py                  # FastAPI app entry point
├── config.py                # Environment and API key configuration
├── llm_config.py            # Cohere model configuration (Command-R-Plus, embeddings)
├── api/                     # REST and WebSocket route handlers
├── chat/                    # Conversational logic
│   ├── intent.py            # Intent classifier & query rephraser
│   ├── context_builder.py   # Aggregates and truncates retrieval context (3,500 token window)
│   └── ...
├── db/                      # SQLite setup and session/metadata management
├── observability/           # Langfuse tracing, LLM-as-Judge evaluation logic
├── pipelines/               # Ingestion pipelines
│   ├── ingest.py            # Unstructured.io partitioning (text + table separation)
│   ├── classifier.py        # Chunking strategy classifier (Recursive / Page / Subsection)
│   └── ...
└── retrieval/               # Multi-source retrieval
    ├── retriever.py         # Parallel search across FAISS, Knowledge Graph, Long-Term Memory
    └── ...
```

### Key pipeline components

| Module | Role |
|---|---|
| `classifier.py` | Selects chunking strategy using Cohere LLM analysis |
| `ingest.py` | Splits documents into text chunks and table summaries |
| `intent.py` | Classifies query intent; rewrites follow-up queries |
| `retriever.py` | Fetches Top-K results from FAISS, KG, and memory in parallel |
| `context_builder.py` | Ranks, deduplicates, and truncates context to token budget |
| `observability/` | LLM-as-Judge scoring, Langfuse span tracing |

---

## Traditional RAG Directory (`traditional_rag/`)

Baseline implementation used for benchmarking against MemGraph.

```
traditional_rag/
├── main.py          # FastAPI app entry point
├── websocket.py     # WebSocket handler for chat
├── vector_store.py  # FAISS vector store (single store, no table separation)
├── retriever.py     # Simple Top-K vector retrieval
├── memory.py        # Last-N message memory (no knowledge graph)
└── ingest.py        # Document ingestion (single pipeline)
```

**Differences from MemGraph:** no chunking classifier, no table pipeline, no Knowledge Graph, no LLM-as-Judge loop, flat memory (last N messages only).

---

## Frontend Directory (`frontend/`)

React 18 + Vite single-page application.

```
frontend/
├── vite.config.ts           # Vite build configuration
└── src/
    ├── components/          # Reusable UI components
    │   ├── ChatWindow/      # Message rendering, streaming display
    │   ├── FileUploader/    # Drag & drop upload with ingestion progress
    │   └── ...
    ├── hooks/               # Custom React hooks
    │   └── useChat.ts       # WebSocket chat lifecycle management
    ├── store/               # Global state
    │   └── appStore.ts      # Zustand store (sessions, messages, UI state)
    ├── types/               # TypeScript interfaces and type definitions
    └── lib/                 # Utility functions and library wrappers
```

---

## Benchmark Data (`logs/`)

The `logs/` directory contains JSONL evaluation exports used for the MemGraph vs Traditional RAG benchmark analysis.

| File | Contents |
|---|---|
| `memgraph_eval.jsonl` | 40 query traces from the MemGraph pipeline |
| `traditional_rag_eval.jsonl` | 40 query traces from the Traditional RAG pipeline |

Each record includes: `latency_total_ms`, `tokens` (input/output/total), `confidence` (retrieval score, combined, source count), `judge` (faithfulness, relevance, completeness, coherence, overall), and `spans` (per-stage latency breakdown).

See [MEMGRAPH_ARCHITECTURE.md](MEMGRAPH_ARCHITECTURE.md) for full benchmark results and analysis.
