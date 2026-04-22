import cohere
import os
from backend.config import settings

class LLMConfig:
    def __init__(self):
        # 1. Cohere Client (Embeddings & Baseline Chat)
        self.cohere = None
        if settings.COHERE_API_KEY:
            self.cohere = cohere.Client(api_key=settings.COHERE_API_KEY)
        
        # 2. Groq Client (Fast Inference)
        self.groq = None
        if settings.GROQ_API_KEY:
            try:
                from groq import Groq
                self.groq = Groq(api_key=settings.GROQ_API_KEY)
            except ImportError:
                pass

        # 3. Model Names
        self.CHAT_MODEL_FAST = settings.CHAT_MODEL_FAST
        self.CHAT_MODEL_QUALITY = settings.CHAT_MODEL_QUALITY
        self.EMBEDDING_MODEL = settings.EMBEDDING_MODEL

    def is_groq_model(self, model_name: str) -> bool:
        """Returns True if the model name belongs to Groq series."""
        groq_prefixes = ("llama3-", "llama-", "mixtral-", "gemma-")
        return any(model_name.lower().startswith(p) for p in groq_prefixes)

    def get_chat_client(self, model_name: str):
        """Returns either the Groq or Cohere client based on the model name."""
        if self.is_groq_model(model_name):
            if not self.groq:
                print(f"[LLMConfig] Model {model_name} requested but Groq client not initialized.")
                return self.cohere
            return self.groq
        return self.cohere

    def chat(self, message: str, model: str, temperature: float = 0.3):
        """Unified sync chat method that works for both Cohere and Groq."""
        if self.is_groq_model(model):
            if not self.groq:
                return self.cohere.chat(message=message, model=model)
            
            # Groq implementation (OpenAI-compatible)
            response = self.groq.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": message}],
                temperature=temperature
            )
            # Wrap in a simple object that mimics Cohere's response structure
            class MockResponse:
                def __init__(self, text, meta):
                    self.text = text
                    self.meta = meta
            
            # Estimate tokens if metadata not present (Groq returns usage)
            usage = response.usage
            meta = type('obj', (object,), {
                'tokens': type('obj', (object,), {
                    'input_tokens': usage.prompt_tokens,
                    'output_tokens': usage.completion_tokens
                })
            })
            return MockResponse(response.choices[0].message.content, meta)
        else:
            # Cohere implementation
            return self.cohere.chat(message=message, model=model, temperature=temperature)

# Singleton instance for the whole project
llm_client = LLMConfig()
