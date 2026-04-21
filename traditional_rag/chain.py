"""
Traditional RAG — LLM Chain

Simple prompt structure:
  System: role + instructions
  [Memory context]  ← summary + last N messages from TradMemory
  [Retrieved chunks] ← top-K FAISS results
  Human: user query

No KG, no event memory, no long-term memory, no intent — same model as MemGraph.
"""

from langchain_cohere import ChatCohere
from langchain_core.messages import SystemMessage, HumanMessage

from traditional_rag.config import trad_settings

SYSTEM_PROMPT = """You are a document assistant. You have access to relevant excerpts from the user's uploaded documents and recent conversation history.

RULES:
1. Answer using the provided document context. Cite sources with [Source: filename, page X].
2. Use conversation history to resolve follow-up questions.
3. If the information is not in the context, say so clearly — do not hallucinate.
4. Be concise. Use markdown formatting when it improves clarity.

{memory_context}

[DOCUMENT CONTEXT]
{doc_context}
"""


class TradChain:
    def __init__(self):
        self.llm = ChatCohere(
            cohere_api_key=trad_settings.COHERE_API_KEY,
            model=trad_settings.CHAT_MODEL_QUALITY,
            streaming=True,
        )

    async def stream_response(
        self,
        query: str,
        memory_context: str,
        doc_context: str,
    ):
        """Async generator that yields response tokens."""
        system_content = SYSTEM_PROMPT.format(
            memory_context=memory_context,
            doc_context=doc_context,
        )
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=query),
        ]
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content

    def build_full_prompt(self, query: str, memory_context: str, doc_context: str) -> str:
        """Returns the full prompt string (for token counting)."""
        return (
            SYSTEM_PROMPT.format(
                memory_context=memory_context,
                doc_context=doc_context,
            )
            + f"\nUser: {query}"
        )


trad_chain = TradChain()
