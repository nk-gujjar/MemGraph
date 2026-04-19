from langchain_cohere import ChatCohere
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import settings

system_prompt = """You are MemGraph, an intelligent document assistant. You have access to the user's uploaded documents, tables, conversation history, and a knowledge graph of facts.

RULES:
1. Answer questions using the provided context. Cite sources with [Source: filename, page X].
2. For table queries, present data clearly, use markdown tables when appropriate.
3. For follow-up questions, use recent conversation context.
4. If information is not in the context, say so clearly — do not hallucinate.
5. Be concise. Use markdown formatting (headers, bullets, bold) when it improves clarity.
6. For summarization, provide structured summaries with key points.

Context:
{context}
"""

class ChatChain:
    def __init__(self):
        self.llm = ChatCohere(
            cohere_api_key=settings.COHERE_API_KEY,
            model=settings.CHAT_MODEL_QUALITY,
            streaming=True
        )
        
    async def stream_response(self, query: str, context: str):
        prompt = [
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ]
        
        full_response = ""
        first_token = True
        async for chunk in self.llm.astream(prompt):
            content = chunk.content
            if content:
                if first_token:
                    print(f"First token received: '{content[:10]}...'")
                    first_token = False
                full_response += content
                yield content
                
        # Optional: yield something to signify finished?
        # Let's let the websocket endpoint handle it

chat_chain = ChatChain()
