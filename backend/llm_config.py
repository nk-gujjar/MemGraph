import cohere
import os
from backend.config import settings

class LLMConfig:
    def __init__(self):
        # 1. Cohere Client (Primary)
        self.cohere = None
        if settings.COHERE_API_KEY:
            self.cohere = cohere.Client(api_key=settings.COHERE_API_KEY)
        
        # 2. Groq Client (Placeholder - add GROQ_API_KEY to .env to use)
        self.groq = None
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                from groq import Groq
                self.groq = Groq(api_key=groq_key)
            except ImportError:
                print("[LLMConfig] Groq library not installed. Run 'pip install groq'.")

        # 3. Model Names (Centralized for easy updating)
        self.CHAT_MODEL_FAST = settings.CHAT_MODEL_FAST
        self.CHAT_MODEL_QUALITY = settings.CHAT_MODEL_QUALITY
        self.EMBEDDING_MODEL = settings.EMBEDDING_MODEL

    def get_cohere_client(self):
        if not self.cohere:
            raise ValueError("COHERE_API_KEY is not set in environment.")
        return self.cohere

# Singleton instance for the whole project
llm_client = LLMConfig()
