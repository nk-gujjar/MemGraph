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

    def start_trace(self, name: str, session_id: str, input_data: any = None, tags: list = None):
        if not self.langfuse:
            return None
        return self.langfuse.trace(
            name=name,
            session_id=session_id,
            input=input_data,
            tags=tags or [],
            metadata={"project": "memgraph"}
        )

    def add_span(self, parent, name: str, input_data: any = None):
        if not self.langfuse or not parent:
            return None
        return parent.span(
            name=name,
            input=input_data
        )

    def add_generation(self, parent, name: str, model: str, input_data: any = None, output_data: any = None, usage: dict = None):
        if not self.langfuse or not parent:
            return None
        return parent.generation(
            name=name,
            model=model,
            input=input_data,
            output=output_data,
            usage=usage
        )

    # Legacy method for broad compatibility
    def trace_chat(self, session_id: str, query: str, intent: str, response: str, sources: list, latency_ms: float, input_tokens: int = 0, output_tokens: int = 0):
        if not self.langfuse:
            return
        self.langfuse.trace(
            name="memgraph_chat",
            session_id=session_id,
            input=query,
            output=response,
            metadata={"intent": intent, "retrieval_sources_count": len(sources), "latency_ms": latency_ms},
            usage={"input": input_tokens, "output": output_tokens}
        )

    def trace_ingestion(self, session_id: str, filename: str, text_chunks: int, table_count: int, latency_ms: float):
        if not self.langfuse:
            return
        self.langfuse.trace(
            name="memgraph_ingestion",
            session_id=session_id,
            input={"filename": filename},
            output={"text_chunks": text_chunks, "table_count": table_count},
            metadata={"latency_ms": latency_ms},
            tags=["ingestion"]
        )

    def trace_retrieval(self, session_id: str, query: str, retrieved_count: int, scores: list, latency_ms: float = 0):
        # Compatibility method
        pass

    def trace_retrieval(self, session_id: str, query: str, retrieved_count: int, scores: list, latency_ms: float = 0):
        # Compatibility method for spans
        pass

lf_client = LangfuseObservable()
