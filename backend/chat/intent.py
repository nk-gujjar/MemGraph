import cohere
from backend.config import settings

intent_prompt = """
Classify the user query into exactly one intent:
- rag: requires retrieving specific information from uploaded documents
- table_query: specifically asks about tabular data, numbers, or comparisons
- chat: general conversation, greetings, or questions not about the document
- follow_up: references a previous response (uses "it", "that", "the above", etc.)
- summarize: asks for a summary of the document or a section

Reply with ONLY the intent word, nothing else.

Query: {query}
"""

class IntentDetector:
    def __init__(self):
        self.cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)
        self.cache = {}

    def detect(self, session_id: str, query: str, parent_trace=None) -> str:
        # Fast path for common greetings
        greetings = {"hi", "hello", "hey", "hola", "greetings", "good morning", "good afternoon", "good evening", "how are you", "who are you", "what is your name"}
        if query.strip().lower() in greetings:
            return "chat"

        cache_key = f"{session_id}:{query}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        generation = None
        if parent_trace:
            from backend.observability.langfuse_client import lf_client
            generation = lf_client.add_generation(
                parent=parent_trace,
                name="intent_classification",
                model=settings.CHAT_MODEL_FAST,
                input_data=intent_prompt.format(query=query)
            )

        try:
            response = self.cohere_client.chat(
                message=intent_prompt.format(query=query),
                model=settings.CHAT_MODEL_FAST
            )
            intent = response.text.strip().lower()
            
            valid_intents = ["rag", "table_query", "chat", "follow_up", "summarize"]
            if generation:
                usage = {}
                if hasattr(response, 'meta') and hasattr(response.meta, 'tokens'):
                    tokens = response.meta.tokens
                    usage = {
                        "input": tokens.input_tokens if hasattr(tokens, 'input_tokens') else 0,
                        "output": tokens.output_tokens if hasattr(tokens, 'output_tokens') else 0
                    }
                generation.end(output=intent, usage=usage if usage.get("input") or usage.get("output") else None)

            self.cache[cache_key] = intent
            return intent
        except Exception as e:
            if generation:
                generation.end(output=f"Error: {str(e)}")
            print(f"Intent detection error: {e}")
            return "rag"

intent_detector = IntentDetector()
