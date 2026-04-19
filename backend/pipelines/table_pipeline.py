import inspect
import cohere
from backend.config import settings
from backend.retrieval.vector_store import vstore

prompt_template = "Summarize this table concisely, capturing all key data, column names, and notable values:\n\n{table_markdown}"

class TablePipeline:
    def __init__(self):
        self.cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)

    def process(self, session_id: str, filename: str, elements: list) -> int:
        """
        Process unstructured Table elements. Returns number of tables processed.
        """
        
        summaries = []
        raw_markdowns = []
        metadatas = []
        
        for i, el in enumerate(elements):
            raw_html = getattr(el.metadata, 'text_as_html', str(el))
            # Just fallback to the text representation if html is not there,
            # Ideally unstructured handles Table elements and can convert to markdown, but mostly we get HTML.
            # Convert simple HTML table to markdown or just pass the text representation if we don't have a converter.
            # We'll pass the string representation for simplicity if html doesn't work.
            raw_markdown = str(el) 
            
            # Truncate individual cells if possible, here we'll just truncate the overall markdown if too large
            if len(raw_markdown) > 8000:
                raw_markdown = raw_markdown[:8000] + "\n...(truncated)"
                
            summary_prompt = prompt_template.format(table_markdown=raw_markdown)
            
            try:
                # Need to use command-r-plus to summarize
                response = self.cohere_client.chat(
                    message=summary_prompt,
                    model=settings.CHAT_MODEL_QUALITY
                )
                summary_text = response.text
                
                page_number = el.metadata.page_number if hasattr(el, 'metadata') and hasattr(el.metadata, 'page_number') else None
                
                summaries.append(summary_text)
                raw_markdowns.append(raw_markdown)
                metadatas.append({
                    "filename": filename,
                    "page_number": page_number,
                    "table_index": i
                })
            except Exception as e:
                print(f"Error summarizing table: {e}")
                
        if not summaries:
            return 0
            
        vstore.add_table_summaries(session_id, summaries, raw_markdowns, metadatas)
            
        return len(summaries)

table_pipeline = TablePipeline()
