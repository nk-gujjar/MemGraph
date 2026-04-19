from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.config import settings
from backend.retrieval.vector_store import vstore
from backend.observability.langfuse_client import lf_client
import time

class TextPipeline:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )

    def process(self, session_id: str, filename: str, elements: list) -> int:
        """
        Process unstructured Text elements. Returns number of chunks created.
        """
        # Combine text elements or process them piece by piece
        # elements here are Unstructured elements that are not tables.
        
        # Strategy: iterate through elements, aggregate strings, split into chunks, keeping page numbers if available
        
        texts_to_embed = []
        metadatas = []
        
        current_text = ""
        current_page = None
        
        chunks = []
        
        for el in elements:
            # try to extract page_number
            page_number = el.metadata.page_number if hasattr(el, 'metadata') and hasattr(el.metadata, 'page_number') else None
            
            text = str(el)
            if not text.strip():
                continue
                
            chunks.append({
                "text": text,
                "metadata": {
                    "filename": filename,
                    "page_number": page_number,
                    "chunk_index": len(chunks)
                }
            })
        
        if not chunks:
            return 0
            
        texts = [c["text"] for c in chunks]
        metas = [c["metadata"] for c in chunks]
        
        start_time = time.time()
        vstore.add_texts(session_id, texts, metas)
        
        return len(texts)

text_pipeline = TextPipeline()
