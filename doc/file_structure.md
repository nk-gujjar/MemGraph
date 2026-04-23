# MemGraph File Structure

This document outlines the high-level file and directory structure of the MemGraph project.

## Root Directory

- `backend/`: The primary backend application (FastAPI) implementing the MemGraph RAG approach.
- `traditional_rag/`: The baseline traditional RAG implementation for comparison against MemGraph.
- `frontend/`: The React-based user interface for interacting with the document assistants.
- `doc/`: Documentation files, including architecture and file structure.
  - `MEMGRAPH_ARCHITECTURE.md`: Detailed architecture design of the MemGraph approach.
  - `file_structure.md`: This document.
- `faiss_indexes/`: Storage directory for FAISS vector indexes used by MemGraph.
- `faiss_trad/`: Storage directory for FAISS vector indexes used by the Traditional RAG.
- `uploads/`: Directory where user-uploaded documents are stored for processing.
- `logs/`: Application and evaluation logs.
- `run_memgraph.sh`: Script to start the MemGraph backend server.
- `run_trad.sh`: Script to start the Traditional RAG backend server.

## Backend Directory (`backend/`)

The `backend` directory contains the FastAPI application for the advanced MemGraph pipeline.

- `main.py`: The entry point for the FastAPI application.
- `config.py` / `llm_config.py`: Configuration files for models and API keys.
- `api/`: API routes including WebSocket handlers for chat.
- `chat/`: Core conversational logic, context building, and intent detection.
- `db/`: Database configuration and SQLite setup.
- `observability/`: Tracing, logging, and LLM-as-Judge evaluation logic.
- `pipelines/`: Document ingestion and table/text processing pipelines.
- `retrieval/`: Components for retrieving data from the vector store, memory, and knowledge graph.

## Traditional RAG Directory (`traditional_rag/`)

The `traditional_rag` directory contains the baseline implementation.

- `main.py`: Entry point for the baseline FastAPI application.
- `websocket.py`: WebSocket handler for the traditional chat interface.
- `vector_store.py`: FAISS-based vector store implementation.
- `retriever.py` / `memory.py`: Simple retrieval and memory mechanisms.
- `ingest.py`: Document ingestion pipeline for the traditional approach.

## Frontend Directory (`frontend/`)

The `frontend` directory is a Vite+React web application.

- `src/`: Source code for the React application.
  - `components/`: Reusable React components (ChatWindow, FileUploader, etc.).
  - `hooks/`: Custom React hooks (e.g., `useChat`).
  - `store/`: Zustand-based state management (`appStore.ts`).
  - `types/`: TypeScript interfaces and type definitions.
  - `lib/`: Utility functions and library wrappers.
- `vite.config.ts`: Vite build configuration.
