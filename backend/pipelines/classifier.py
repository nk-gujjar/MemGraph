import json
from backend.llm_config import llm_client
from backend.config import settings

class StrategyClassifier:
    def __init__(self):
        self.cohere_client = llm_client.cohere

    def classify(self, content_preview: str, description: str = None) -> str:
        """
        Classify the document into a chunking strategy: 'recursive', 'page', or 'subsection'.
        """
        prompt = f"""You are an expert in document processing and RAG (Retrieval-Augmented Generation).
Analyze the following document preview and description to suggest the best chunking strategy.

STRATEGIES:
- 'recursive': Best for generic text, narratives, or documents without a clear hierarchical structure.
- 'page': Best for visually heavy documents, or research papers/reports where pages represent logical breaks.
- 'subsection': Best for technical documentation, legal documents, or manuals with clear headers and nested sections.

INPUT:
Description: {description if description else "No description provided."}
Content Preview: {content_preview[:2000]}

OUTPUT:
Respond ONLY with a JSON object in this format: {{"strategy": "recursive" | "page" | "subsection", "reason": "brief reason"}}
"""
        try:
            response = self.cohere_client.chat(
                message=prompt,
                model=settings.CHAT_MODEL_FAST
            )
            
            # Extract JSON from response. Simple heuristic: look for { }
            text = response.text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != -1:
                data = json.loads(text[start:end])
                strategy = data.get("strategy", "recursive")
                reason = data.get("reason", "No reason provided")
                print(f"Classifier result: {strategy} (Reason: {reason})")
                
                if strategy in ['recursive', 'page', 'subsection']:
                    return strategy
            
            return "recursive"
        except Exception as e:
            print(f"Classification error: {e}")
            return "recursive"

strategy_classifier = StrategyClassifier()
