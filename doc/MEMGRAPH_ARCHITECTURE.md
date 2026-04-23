# MemGraph Backend Architecture

This document provides a technical deep-dive into the architecture of the MemGraph Document Assistant backend, organized by its three core pillars: **Dynamic Ingestion**, **Hybrid Memory**, and **Multi-Stage Retrieval**.

---

## 1. Dynamic Ingestion Pipeline
The ingestion system converts raw documents into searchable, structured knowledge.

### Flow:
1. **API Entry (`/api/sessions/{id}/upload`)**: Files are saved to local storage with metadata (optional user description).
2. **Strategy Classifier (`classifier.py`)**: 
   - Uses **Cohere (Command-R-Plus)** to analyze a preview of the document + user description.
   - Selects the optimal strategy: `RecursiveTextSplitter` (generic), `Page` (visually heavy), or `Subsection` (hierarchical).
   - If no description is provided, it defaults to **Recursive** to save latency.
3. **Partitioning (`ingest.py`)**: Uses **Unstructured.io** to extract text and HTML-formatted tables.
4. **Parallel Processing**:
   - **Text Pipeline**: Segments text based on the strategy and generates `1024-dim` embeddings via **Cohere (embed-english-v3.0)**.
   - **Table Pipeline**: Extracts tables as HTML/Markdown, generates a semantic summary of the table, and embeds only the summary while storing the raw Markdown.
5. **Persistence**:
   - **FAISS**: Stores embeddings in a FlatIP index for cosine similarity.
   - **SQLite**: Stores chunk metadata, raw text, table Markdown, and ingestion status (`processing` -> `completed`).

---

## 2. Hybrid Memory Management
MemGraph uses a tiered memory system to maintain context across varied timescales.

### Components:
- **Short-Term Memory**: A circular buffer of the most recent 10-15 messages stored in SQLite, used for immediate conversational flow.
- **Long-Term Semantic Memory**: Uses the vector store with a special `__memory__` namespace. Insights or user preferences are semantically indexed to be retrieved when relevant.
- **Knowledge Graph (Triples)**: Extracts entities and relationships (Subject -> Predicate -> Object) using LLM-based extraction. This allows for multi-hop reasoning (e.g., "What was the findings of the paper authored by X?").
- **Event Memory**: A timeline-based SQLite store that tracks system events and document updates.

---

## 3. Multi-Stage Retrieval System
Retrieval is the "brain" that gathers context before the LLM generates a response.

### The 4-Step Process:
1. **Intent Detection (`intent.py`)**: 
   - Classifies the query into `chat` (greeting), `rag` (doc query), `table_query`, `summarize`, or `follow_up`.
   - **Fast-Path**: Common greetings (Hi/Hello) skip RAG entirely to prevent irrelevant summaries.
2. **Query Rephrasing**: If a `follow_up` is detected, an LLM turns the query (e.g., "Why?") into a standalone search query (e.g., "Why were the LLM tokens missing in Langfuse?") using recent history.
3. **Multi-Source Fetching (`retriever.py`)**:
   - Performs parallel searches across **FAISS** (Text + Tables), **KG**, and **Long-term Memory**.
   - Filters results by `session_id` to ensure strict data privacy.
4. **Context Building (`context_builder.py`)**:
   - Aggregates all sources and ranks them.
   - Truncates context to fit a **3,500 token window** (prioritizing recent conversation history last to preserve flow).

---

## 4. LLM Generation & Post-Processing
- **Chain Execution**: Uses **Cohere Command-R-Plus** via LangChain. Responses are streamed as tokens via WebSockets for low perceived latency.
- **Citation Injection**: Matches generated text against source metadata to inject citations like `[Source: paper.pdf, page 5]`.
- **Token Accuracy**: After the stream, the **Post-Processor** calculates precise token counts via the Cohere tokenizer and pushes "Stats" updates to the UI.

---

## 5. Observability Layer
Integrated with **Langfuse**, the system provides tracing for:
- **Ingestion**: Tracks chunk counts, table counts, and total processing latency.
- **Retrieval**: Logs query latency and the quality of retrieved sources.
- **Chat**: Captures full conversation traces, including precise cost (input/output tokens) and model performance.

---

## Data Flow Diagram
![MemGraph Architecture](./MemGraph_arch.png)


