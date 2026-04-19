# MemGraph

MemGraph is a production-ready document chat application built with FastAPI, React, and Cohere.
It features dual pipelines for ingestion (text and table separation), Knowledge Graph extraction, dual FAISS vector stores, and structured multi-layer memory.

## Architecture
- **Backend:** FastAPI, LangChain, Cohere (command-r-plus, command-r, embed-english-v3.0), FAISS, NetworkX, SQLite
- **Frontend:** React 18, Vite, TailwindCSS, Zustand
- **Observability:** Langfuse tracing

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
