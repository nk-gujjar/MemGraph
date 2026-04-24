# MemGraph

MemGraph is a production-ready document chat application built with FastAPI, React, and Cohere.
It features dual pipelines for ingestion (text and table separation), Knowledge Graph extraction, dual FAISS vector stores, and structured multi-layer memory.

## Architecture
- **Backend:** FastAPI, LangChain, Cohere (command-r-plus, command-r, embed-english-v3.0), FAISS, NetworkX, SQLite
- **Frontend:** React 18, Vite, TailwindCSS, Zustand
- **Observability:** Langfuse tracing

## Documentation
Additional documentation about the system design and project structure can be found in the `doc/` directory:
- [Architecture Details](doc/MEMGRAPH_ARCHITECTURE.md)
- [File Structure](doc/file_structure.md)

---

## Benchmark Results: MemGraph vs Traditional RAG

Evaluated over **39–40 queries** on the same document corpus. Responses scored using an LLM-as-Judge pipeline (0–10 scale) with full Langfuse tracing.

### Performance & Cost

| Metric | MemGraph | Traditional RAG | Difference |
|---|---|---|---|
| Avg total latency | 36,023 ms | 37,501 ms | **−3.9%** |
| Avg input tokens | 683 | 1,512 | **−54.8%** |
| Avg output tokens | 148 | 106 | +39.7% |
| Avg total tokens | 831 | 1,618 | **−48.7%** |
| Avg source count | 6.2 | 8.0 | −22.4% |

> MemGraph uses ~55% fewer input tokens per query — the most significant cost reduction at scale.

### Retrieval Confidence

| Metric | MemGraph | Traditional RAG | Difference |
|---|---|---|---|
| Retrieval score | 0.22 | 0.43 | −48.8% |
| Combined confidence | 0.34 | 0.60 | −43.3% |

> Traditional RAG scores higher on raw vector similarity, but this reflects the nature of graph-expanded retrieval — results are structurally traversed rather than purely similarity-matched. Answer quality tells a different story (see below).

### Answer Quality (LLM-as-Judge, 0–10)

| Metric | MemGraph | Traditional RAG | Difference |
|---|---|---|---|
| Faithfulness | 9.79 | 9.72 | +0.7% |
| Relevance | 9.85 | 9.70 | +1.5% |
| Completeness | **8.90** | **8.47** | **+5.1%** |
| Coherence | 9.82 | 9.75 | +0.7% |
| **Overall** | **9.08** | **9.00** | **+0.9%** |

> Completeness is the standout improvement (+5.1%) — graph-based memory retains relational context that summarization-based approaches lose, leading to more thorough answers.

### Key Takeaway

> Better RAG systems don't retrieve more — they retrieve smarter. MemGraph trades higher raw retrieval similarity scores for structured relational memory, resulting in better answer quality at significantly lower token cost.

---

## Local Development Setup

### Prerequisites
- **Python 3.11+** (with `pip`)
- **Node.js 18+** (with `npm`)

### 1. Clone & Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
- `COHERE_API_KEY` — from [dashboard.cohere.com](https://dashboard.cohere.com)
- `LANGFUSE_SECRET_KEY` / `LANGFUSE_PUBLIC_KEY` — from [cloud.langfuse.com](https://cloud.langfuse.com) (optional)

### 2. Start the Backend

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start the server (from project root)
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Check health at `http://localhost:8000/health`.

### 3. Start the Frontend

Open a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

---

## Usage

1. Open `http://localhost:5173` in your browser.
2. Click **"New Session"** in the left sidebar.
3. Drag & drop a PDF, DOCX, TXT, CSV, XLSX, or MD file into the upload area.
4. Wait for ingestion to complete (you'll see chunk/table counts).
5. Ask questions about your document in the chat input.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Create a new chat session |
| GET | `/api/sessions` | List all sessions |
| DELETE | `/api/sessions/{id}` | Delete a session |
| POST | `/api/sessions/{id}/upload` | Upload documents |
| GET | `/api/sessions/{id}/upload/progress` | SSE ingestion progress |
| GET | `/api/sessions/{id}/sources` | List uploaded files for a session |
| WS | `/ws/{id}` | Real-time chat via WebSocket |
