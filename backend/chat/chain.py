from langchain_cohere import ChatCohere
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import settings

system_prompt = """You are MemGraph, an intelligent document assistant. You have access to the user's uploaded documents, tables, conversation history, and a knowledge graph of facts.

RULES:
 1. Answer questions using the provided context. Cite sources with [Source: filename, page X].
 2. For table queries, present data clearly, use markdown tables when appropriate.
 3. For follow-up questions, use recent conversation context. However, prioritze the user's immediate latest question.
 4. For simple greetings (like "hi" or "hello"), respond naturally and briefly. Do NOT repeat previous summaries unless asked.
 5. If information is not in the context, say so clearly — do not hallucinate.
 6. Be concise. Use markdown formatting (headers, bullets, bold) when it improves clarity.
 7. For summarization, provide structured summaries with key points.

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
        
    async def stream_response(self, query: str, context: str, parent_trace=None):
        prompt = [
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ]
        
        generation = None
        if parent_trace:
            from backend.observability.langfuse_client import lf_client
            generation = lf_client.add_generation(
                parent=parent_trace,
                name="chat_generation",
                model=settings.CHAT_MODEL_QUALITY,
                input_data=system_prompt.format(context=context) + f"\nUser: {query}"
            )

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
        
        if generation:
            try:
                # Estimate tokens or use post_processor client if available
                from backend.chat.post_processor import post_processor
                full_prompt = system_prompt.format(context=context) + f"\nUser: {query}"
                input_tokens = len((await asyncio.to_thread(post_processor.cohere_client.tokenize, text=full_prompt, model=settings.CHAT_MODEL_QUALITY)).tokens)
                output_tokens = len((await asyncio.to_thread(post_processor.cohere_client.tokenize, text=full_response, model=settings.CHAT_MODEL_QUALITY)).tokens)
                
                generation.end(output=full_response, usage={"input": input_tokens, "output": output_tokens})
            except Exception:
                # Fallback to estimation or just output
                generation.end(output=full_response)
                
        # Optional: yield something to signify finished?
        # Let's let the websocket endpoint handle it

chat_chain = ChatChain()
