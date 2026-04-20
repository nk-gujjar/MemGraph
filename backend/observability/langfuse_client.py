from langfuse import Langfuse
from backend.config import settings

class LangfuseObservable:
    def __init__(self):
        self.langfuse = None
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                self.langfuse = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_BASE_URL
                )
            except Exception as e:
                print(f"Warning: Langfuse client initialization failed: {e}")

    def trace_chat(self, session_id: str, query: str, intent: str, response: str, sources: list, latency_ms: float, input_tokens: int = 0, output_tokens: int = 0):
        if not self.langfuse:
            return
            
        trace = self.langfuse.trace(
            name="memgraph_chat",
            session_id=session_id,
            input=query,
            output=response,
            metadata={
                "intent": intent,
                "retrieval_sources_count": len(sources),
                "latency_ms": latency_ms,
                "project": "memgraph"
            },
            usage={
                "input": input_tokens,
                "output": output_tokens
            },
            tags=["chat", f"intent:{intent}"]
        )

    def trace_ingestion(self, session_id: str, filename: str, text_chunks: int, table_count: int, latency_ms: float):
        if not self.langfuse:
            return
            
        self.langfuse.trace(
            name="memgraph_ingestion",
            session_id=session_id,
            input={"filename": filename},
            output={"text_chunks": text_chunks, "table_count": table_count},
            metadata={
                "project": "memgraph",
                "latency_ms": latency_ms
            },
            tags=["ingestion"]
        )

    def trace_retrieval(self, session_id: str, query: str, retrieved_count: int, scores: list, latency_ms: float = 0, input_tokens: int = 0):
        if not self.langfuse:
            return
            
        self.langfuse.trace(
            name="memgraph_retrieval",
            session_id=session_id,
            input=query,
            metadata={
                "retrieved_count": retrieved_count,
                "scores": scores,
                "latency_ms": latency_ms,
                "project": "memgraph"
            },
            usage={
                "input": input_tokens
            },
            tags=["retrieval"]
        )
        
    def get_client(self):
        return self.langfuse

lf_client = LangfuseObservable()
